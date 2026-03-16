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
            logger.debug(f"Skipping already downloaded: {action.claim_name}")
            return True

        if dry_run:
            logger.info(f"[DRY-RUN] Would download: {action.claim_name}")
            return True

        # Create directories
        version_dir = Path(action.target_dir)
        version_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Downloading: {action.claim_name}")

        try:
            # Call daemon to download
            result = self.client.get(
                uri=action.uri,
                download_directory=str(version_dir),
            )

            # Wait a moment for download to start and get file info
            import time

            time.sleep(2)

            # Try to find the downloaded file - daemon may return different structures
            file_info = None
            claim_id = result.get("claim_id") or action.claim_id

            # Try multiple times to get file info
            for attempt in range(5):
                file_info = self._extract_file_info(result, claim_id)
                if file_info and file_info.get("download_path"):
                    break
                # Wait and try file_list
                time.sleep(1)
                if claim_id:
                    file_info = self._extract_file_info({}, claim_id)
                    if file_info and file_info.get("download_path"):
                        break

            if not file_info or not file_info.get("download_path"):
                logger.warning(
                    f"Could not get file path for {action.claim_name}, using metadata only"
                )
                # Write what we have even without the file
                self._write_metadata(
                    version_dir,
                    action,
                    {"download_path": None, "file_name": action.claim_name},
                )
                self._write_download_json(version_dir, result)
                return True

            download_path_str = file_info["download_path"]
            if not download_path_str:
                raise DownloadError("Download path is empty")

            downloaded_path = Path(download_path_str)

            # Check if file exists
            if not downloaded_path.exists():
                logger.warning(f"File not found at expected path: {downloaded_path}")
                # Try to find it in the version_dir
                files = list(version_dir.glob("*"))
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
