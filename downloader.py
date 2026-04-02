"""Downloader module - executes downloads and writes metadata."""

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Dict, Optional

from lbry_client import LbryClient
from models import Config, DownloadAction
from utils import compute_sha256

try:
    import requests
except ImportError:
    requests = None


logger = logging.getLogger(__name__)


class DownloadError(Exception):
    """Raised when a download fails."""

    pass


class Downloader:
    """Handles downloading claims and writing metadata."""

    def __init__(self, client: LbryClient, config: Config, base_dir: Path):
        self.client = client
        self.config = config
        self.base_dir = base_dir

    def download(self, action: DownloadAction, dry_run: bool = False) -> bool:
        """
        Execute a download action.

        Args:
            action: The download action to execute.
            dry_run: If True, don't actually download.

        Returns:
            True if download succeeded or was skipped in dry-run.

        Raises:
            DownloadError: If the download fails.
        """
        if action.action == "skip_existing":
            existing_path = action.metadata.get("existing_file_relpath")
            if existing_path:
                logger.info(
                    "Skipping existing file: %s (%s)",
                    action.claim_name,
                    self.base_dir / existing_path,
                )
            else:
                logger.info(f"Skipping existing file: {action.claim_name}")
            return True

        if dry_run:
            logger.info(f"[DRY-RUN] Would download: {action.claim_name}")
            return True

        # Create directories
        version_dir = Path(action.target_dir)
        version_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Downloading: {action.claim_name}")
        logger.info(f"Saving to directory: {version_dir}")

        try:
            # Call daemon to start P2P download
            logger.info(f"Starting download: {action.claim_name}")
            result = self.client.get(
                uri=action.uri,
                download_directory=str(version_dir),
            )

            claim_id = result.get("claim_id") or action.claim_id
            sd_hash = result.get("sd_hash") or action.metadata.get("sd_hash")

            # Wait for download to complete - this can take time
            logger.info(f"Waiting for download to complete...")
            file_info = self._wait_for_download(claim_id, version_dir, timeout=60)

            if not file_info:
                logger.info(
                    f"P2P download incomplete, trying daemon streaming endpoint..."
                )
                # Try streaming endpoint if P2P fails
                target_file = version_dir / (
                    action.metadata.get("source_name") or f"{action.claim_name}.zip"
                )
                if sd_hash and self._download_via_streaming(
                    sd_hash, target_file, result, action
                ):
                    file_info = {
                        "download_path": str(target_file),
                        "file_name": target_file.name,
                        "size": target_file.stat().st_size,
                        "media_type": result.get("mime_type"),
                    }
                else:
                    logger.warning(
                        f"Download failed for {action.claim_name} - P2P peers not available"
                    )
                    # Write metadata even if download didn't complete
                    self._write_metadata(
                        version_dir,
                        action,
                        {"download_path": None, "file_name": action.claim_name},
                    )
                    self._write_download_json(version_dir, result)
                    return False

            download_path_str = file_info.get("download_path") or file_info.get(
                "file_name"
            )
            if not download_path_str:
                raise DownloadError("Download path is empty")

            downloaded_path = Path(download_path_str)

            # Check if file exists
            if not downloaded_path.exists():
                logger.warning(f"File not found at expected path: {downloaded_path}")
                # Try to find it in the version_dir
                files = [f for f in version_dir.glob("*") if f.is_file() and f.suffix]
                if files:
                    downloaded_path = files[0]
                    logger.info(f"Found file in version dir: {downloaded_path.name}")
                else:
                    raise DownloadError(f"Downloaded file not found")

            # If file was downloaded to a different location, move it
            if downloaded_path.parent != version_dir:
                target_path = version_dir / downloaded_path.name
                shutil.move(str(downloaded_path), str(target_path))
                downloaded_path = target_path

            # Write metadata files
            self._write_metadata(version_dir, action, file_info)
            self._write_download_json(version_dir, result)

            # Write checksum if enabled
            if self.config.general.write_checksums and downloaded_path.exists():
                self._write_checksum(version_dir, downloaded_path)

            # Update action metadata with file path
            try:
                rel_path = downloaded_path.relative_to(self.base_dir)
                action.metadata["local_file_path"] = str(rel_path)
            except ValueError:
                # If not relative to base_dir, store absolute path
                action.metadata["local_file_path"] = str(downloaded_path)

            logger.info(f"Downloaded: {action.claim_name} -> {downloaded_path.name}")
            return True

        except Exception as e:
            logger.error(f"Download failed for {action.claim_name}: {e}")
            raise DownloadError(f"Download failed: {e}")

    def _extract_file_info(
        self, result: Dict, claim_id: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Extract file information from download result.

        The result structure varies depending on daemon version and
        whether the file was already downloaded.
        """
        # Direct file result
        if "download_path" in result and result["download_path"]:
            return result

        # Nested in outputs
        if "outputs" in result and result["outputs"]:
            output = result["outputs"][0]
            if "value" in output:
                value = output["value"]
                if isinstance(value, dict) and "source" in value:
                    source = value["source"]
                    return {
                        "download_path": source.get("name"),
                        "file_name": source.get("name"),
                        "media_type": source.get("media_type"),
                    }

        # Try to get from file_list
        if claim_id:
            try:
                file_list = self.client.file_list(claim_id=claim_id)
                if "items" in file_list and file_list["items"]:
                    return file_list["items"][0]
            except Exception as e:
                logger.debug(f"Could not get file list: {e}")

        return None

    def _wait_for_download(
        self, claim_id: str, version_dir: Path, timeout: int = 300
    ) -> Optional[Dict]:
        """
        Wait for download to complete and return file info.

        Args:
            claim_id: The claim ID to wait for
            version_dir: Directory where file should appear
            timeout: Maximum time to wait in seconds

        Returns:
            File info dict if download completes, None otherwise
        """
        start_time = time.time()
        check_interval = 5  # Check every 5 seconds

        logger.info(f"Waiting up to {timeout}s for download to complete...")

        while time.time() - start_time < timeout:
            # Check if file appeared in version_dir
            files = [
                f for f in version_dir.glob("*") if f.is_file() and f.stat().st_size > 0
            ]
            if files:
                file_path = files[0]
                logger.info(f"File appeared: {file_path.name}")
                return {
                    "download_path": str(file_path),
                    "file_name": file_path.name,
                    "size": file_path.stat().st_size,
                }

            # Check daemon's file list
            try:
                file_list = self.client.file_list(claim_id=claim_id)
                if "items" in file_list and file_list["items"]:
                    file_info = file_list["items"][0]
                    download_path = file_info.get("download_path") or file_info.get(
                        "file_name"
                    )
                    if download_path:
                        path = Path(download_path)
                        if path.exists() and path.stat().st_size > 0:
                            logger.info(f"Download complete via file_list: {path.name}")
                            return file_info
                        elif path.exists():
                            logger.debug(
                                f"File exists but size is 0, still downloading..."
                            )
                        else:
                            logger.debug(f"File not yet at path: {path}")
            except Exception as e:
                logger.debug(f"Could not check file_list: {e}")

            # Wait before checking again
            time.sleep(check_interval)
            elapsed = int(time.time() - start_time)
            if elapsed % 30 == 0:  # Log every 30 seconds
                logger.info(f"Still waiting for download... ({elapsed}s elapsed)")

        logger.warning(f"Download timed out after {timeout}s")
        return None

    def _download_via_streaming(
        self, sd_hash: str, target_path: Path, file_info: Dict, action: DownloadAction
    ) -> bool:
        """
        Download file using daemon's streaming endpoint.

        This is more reliable than P2P when peers are unavailable.
        The daemon fetches the content and serves it via local HTTP.

        Args:
            sd_hash: The SD hash from the claim
            target_path: Where to save the file
            file_info: File metadata from daemon
            action: Download action

        Returns:
            True if download succeeded
        """
        if not sd_hash or not requests:
            return False

        # Build streaming URL from daemon API URL
        streaming_url = f"http://localhost:5280/stream/{sd_hash}"

        logger.info(f"Downloading via daemon streaming endpoint...")
        logger.info(f"Streaming destination: {target_path}")

        try:
            response = requests.get(streaming_url, stream=True, timeout=300)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0
            chunk_size = 8192

            print(f"\n📥 Downloading: {action.claim_name}")
            print(f"   Saving to: {target_path}")
            print(f"   Size: {total_size / (1024 * 1024):.2f} MB")
            print()

            with open(target_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        if total_size > 0:
                            percent = min(100, int((downloaded / total_size) * 100))
                            filled = int(40 * percent / 100)
                            bar = "█" * filled + "░" * (40 - filled)
                            print(f"\r   [{bar}] {percent}%", end="", flush=True)

            print()  # New line after progress
            print(f"   ✅ Download complete: {target_path.name}")

            # Update file_info with actual path
            file_info["download_path"] = str(target_path)
            file_info["file_name"] = target_path.name
            file_info["written_bytes"] = target_path.stat().st_size

            return True

        except Exception as e:
            logger.warning(f"Streaming download failed: {e}")
            return False

    def _write_metadata(
        self,
        version_dir: Path,
        action: DownloadAction,
        file_info: Dict,
    ) -> None:
        """
        Write normalized metadata.json for the download.

        Args:
            version_dir: Directory to write metadata to.
            action: The download action.
            file_info: File information from daemon.
        """
        metadata = {
            "claim_id": action.claim_id,
            "channel_claim_id": action.channel_claim_id,
            "name": action.claim_name,
            "title": action.metadata.get("title"),
            "version_token": action.version_token,
            "permanent_url": action.uri,
            "downloaded_at": file_info.get("added_on"),
            "file_name": file_info.get("file_name")
            or file_info.get("download_path", "").split("/")[-1],
            "media_type": file_info.get("media_type"),
            "file_size": file_info.get("written_bytes"),
            "sd_hash": action.metadata.get("sd_hash"),
            "stream_hash": action.metadata.get("stream_hash"),
            "txid": action.metadata.get("txid"),
            "nout": action.metadata.get("nout"),
            "tags": action.metadata.get("tags", []),
            "languages": action.metadata.get("languages", []),
        }

        metadata_path = version_dir / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2, default=str)

        logger.debug(f"Wrote metadata: {metadata_path}")

    def _write_download_json(
        self,
        version_dir: Path,
        result: Dict,
    ) -> None:
        """
        Write raw daemon response to download.json.

        Args:
            version_dir: Directory to write to.
            result: Raw daemon response.
        """
        download_path = version_dir / "download.json"
        with open(download_path, "w") as f:
            json.dump(result, f, indent=2, default=str)

        logger.debug(f"Wrote download metadata: {download_path}")

    def _write_checksum(self, version_dir: Path, file_path: Path) -> None:
        """
        Write SHA256 checksum for the downloaded file.

        Args:
            version_dir: Directory to write checksum to.
            file_path: Path to the downloaded file.
        """
        if not file_path.exists():
            logger.warning(f"Cannot write checksum - file not found: {file_path}")
            return

        try:
            checksum = compute_sha256(file_path)
            checksums_path = version_dir / "checksums.txt"

            with open(checksums_path, "w") as f:
                f.write(f"SHA256({file_path.name})= {checksum}\n")

            logger.debug(f"Wrote checksum: {checksums_path}")
        except Exception as e:
            logger.warning(f"Failed to compute checksum: {e}")
