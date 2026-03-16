"""Direct downloader module - downloads from Odysee CDN instead of P2P."""

import json
import logging
import re
import shutil
import time
from pathlib import Path
from typing import Dict, Optional

try:
    import requests
except ImportError:
    raise ImportError("requests is required. Install with: pip install requests")

from models import Config, DownloadAction
from utils import compute_sha256

logger = logging.getLogger(__name__)


class DirectDownloadError(Exception):
    """Raised when direct download fails."""

    pass


class DirectDownloader:
    """Downloads content directly from Odysee CDN."""

    def __init__(self, config: Config, base_dir: Path):
        self.config = config
        self.base_dir = base_dir
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
        )

    def download(self, action: DownloadAction, dry_run: bool = False) -> bool:
        """
        Download a claim directly from Odysee CDN.

        Args:
            action: The download action
            dry_run: If True, don't actually download

        Returns:
            True if download succeeded
        """
        if action.action == "skip_existing":
            logger.debug(f"Skipping already downloaded: {action.claim_name}")
            return True

        if dry_run:
            logger.info(f"[DRY-RUN] Would download from CDN: {action.claim_name}")
            return True

        # Create directories
        version_dir = Path(action.target_dir)
        version_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Downloading from CDN: {action.claim_name}")

        try:
            # Get download URL from Odysee
            download_url = self._get_download_url(action.uri)
            if not download_url:
                raise DirectDownloadError("Could not get download URL from Odysee")

            logger.info(f"Download URL: {download_url}")

            # Download the file
            file_path = self._download_file(
                download_url, version_dir, action.claim_name
            )
            if not file_path:
                raise DirectDownloadError("File download failed")

            logger.info(f"Downloaded: {action.claim_name} -> {file_path.name}")

            # Write metadata
            file_info = {
                "download_path": str(file_path),
                "file_name": file_path.name,
                "size": file_path.stat().st_size,
            }
            self._write_metadata(version_dir, action, file_info)

            # Write checksum if enabled
            if self.config.general.write_checksums:
                self._write_checksum(version_dir, file_path)

            # Update action metadata
            try:
                rel_path = file_path.relative_to(self.base_dir)
                action.metadata["local_file_path"] = str(rel_path)
            except ValueError:
                action.metadata["local_file_path"] = str(file_path)

            return True

        except Exception as e:
            logger.error(f"Direct download failed for {action.claim_name}: {e}")
            raise DirectDownloadError(f"Download failed: {e}")

    def _get_download_url(self, lbry_uri: str) -> Optional[str]:
        """
        Get direct download URL from Odysee API.

        Args:
            lbry_uri: LBRY URI like lbry://@channel/claim#claim_id

        Returns:
            Direct download URL or None
        """
        try:
            # First, resolve the claim to get the permanent URL
            # Odysee API endpoint for streaming
            api_url = "https://api.lbry.tv/api/v1/proxy"

            # Get the claim info
            claim_name = lbry_uri.split("/")[-1].split("#")[0]

            # Try to get streaming URL from Odysee
            # This uses their API to get CDN links
            headers = {
                "Content-Type": "application/json",
            }

            # Method 1: Try to get via Odysee's API
            payload = {
                "jsonrpc": "2.0",
                "method": "get",
                "params": {
                    "uri": lbry_uri,
                    "save_file": False,
                },
                "id": 1,
            }

            logger.debug(f"Querying Odysee API for: {lbry_uri}")
            response = self.session.post(
                api_url, json=payload, headers=headers, timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if "result" in data and data["result"]:
                    result = data["result"]

                    # Try to get streaming_url
                    if "streaming_url" in result and result["streaming_url"]:
                        return result["streaming_url"]

                    # Try to get download URL from value
                    if "download_path" in result:
                        return result["download_path"]

                    # Try to construct from lbry.tv
                    if "permanent_url" in result:
                        claim_id = result.get("claim_id", "")
                        if claim_id:
                            # Construct Odysee direct URL
                            return f"https://player.odycdn.com/v6/streams/{claim_id}/"

            # Method 2: Try using lbry.tv player URL directly
            # Extract claim info from URI
            claim_parts = lbry_uri.replace("lbry://", "").split("/")
            if len(claim_parts) >= 2:
                claim_name_encoded = claim_parts[-1].split("#")[0]
                # Try to construct direct download URL
                # This is an educated guess based on Odysee's URL structure
                odysee_url = f"https://odysee.com/{lbry_uri.replace('lbry://', '').replace('#', ':')}"
                logger.debug(f"Trying Odysee URL: {odysee_url}")

                # Get the page to find the download link
                page_response = self.session.get(odysee_url, timeout=30)
                if page_response.status_code == 200:
                    # Look for download URL in page
                    # Odysee embeds this in their JavaScript
                    match = re.search(r'"download_url":"([^"]+)"', page_response.text)
                    if match:
                        url = match.group(1).replace("\\u0026", "&")
                        return url

                    # Look for streaming URL
                    match = re.search(r'"streaming_url":"([^"]+)"', page_response.text)
                    if match:
                        url = match.group(1).replace("\\u0026", "&")
                        return url

            logger.warning(f"Could not extract download URL for: {lbry_uri}")
            return None

        except Exception as e:
            logger.error(f"Error getting download URL: {e}")
            return None

    def _download_file(
        self, url: str, version_dir: Path, claim_name: str
    ) -> Optional[Path]:
        """
        Download file from URL to version directory with progress bar.

        Args:
            url: Download URL
            version_dir: Target directory
            claim_name: Name of the claim

        Returns:
            Path to downloaded file or None
        """
        try:
            # Determine filename from URL or claim name
            filename = self._extract_filename(url, claim_name)
            file_path = version_dir / filename

            # Print clear message with filename
            print(f"\n📥 Downloading: {claim_name}")
            print(f"   Filename: {filename}")
            print(f"   Destination: {file_path.parent}")

            # Stream download with progress
            response = self.session.get(url, stream=True, timeout=300)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))

            if total_size > 0:
                size_mb = total_size / (1024 * 1024)
                print(f"   Size: {size_mb:.2f} MB")
            else:
                print(f"   Size: Unknown")
            print()

            start_time = time.time()
            last_update = start_time
            downloaded = 0
            chunk_size = 8192

            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Update progress bar every 0.5 seconds
                        current_time = time.time()
                        if current_time - last_update >= 0.5:
                            self._print_progress_bar(
                                downloaded, total_size, start_time, claim_name
                            )
                            last_update = current_time

                # Final progress update
                self._print_progress_bar(
                    downloaded, total_size, start_time, claim_name, final=True
                )
                print()  # New line after progress bar

            # Verify file was downloaded
            if file_path.exists() and file_path.stat().st_size > 0:
                size_mb = file_path.stat().st_size / (1024 * 1024)
                elapsed = time.time() - start_time
                speed_mbps = (size_mb / elapsed) if elapsed > 0 else 0
                print(f"✅ Complete: {size_mb:.2f} MB @ {speed_mbps:.2f} MB/s\n")
                return file_path
            else:
                print(f"❌ Error: Downloaded file is empty\n")
                return None

        except Exception as e:
            print(f"❌ Error downloading {claim_name}: {e}\n")
            logger.error(f"Error downloading file: {e}")
            return None

    def _print_progress_bar(
        self,
        downloaded: int,
        total_size: int,
        start_time: float,
        claim_name: str,
        final: bool = False,
    ):
        """Print a progress bar to the console."""
        if total_size > 0:
            percent = min(100, int((downloaded / total_size) * 100))
            filled = int(50 * percent / 100)
            bar = "█" * filled + "░" * (50 - filled)

            # Calculate speed
            elapsed = time.time() - start_time
            if elapsed > 0:
                speed_mbps = (downloaded / (1024 * 1024)) / elapsed
                speed_str = f"{speed_mbps:.2f} MB/s"
            else:
                speed_str = "calculating..."

            # Calculate ETA
            if not final and speed_mbps > 0:
                remaining = (total_size - downloaded) / (1024 * 1024)
                eta = remaining / speed_mbps
                eta_str = f"ETA: {int(eta)}s"
            else:
                eta_str = ""

            # Clear line and print progress
            print(
                f"\r   [{bar}] {percent}% | {speed_str} | {eta_str}", end="", flush=True
            )
        else:
            # Unknown size, just show downloaded amount
            downloaded_mb = downloaded / (1024 * 1024)
            print(f"\r   Downloaded: {downloaded_mb:.2f} MB", end="", flush=True)

    def _extract_filename(self, url: str, claim_name: str) -> str:
        """Extract filename from URL or use claim name."""
        # Try to get from URL
        if "." in url.split("/")[-1].split("?")[0]:
            filename = url.split("/")[-1].split("?")[0]
            # Sanitize
            filename = re.sub(r'[<>"|?*]', "_", filename)
            return filename[:255]  # Max filename length

        # Use claim name with extension
        return f"{claim_name}.mp4"  # Default to mp4

    def _write_metadata(
        self, version_dir: Path, action: DownloadAction, file_info: Dict
    ) -> None:
        """Write metadata.json for the download."""
        metadata = {
            "claim_id": action.claim_id,
            "channel_claim_id": action.channel_claim_id,
            "name": action.claim_name,
            "title": action.metadata.get("title"),
            "version_token": action.version_token,
            "permanent_url": action.uri,
            "download_source": "odysee_cdn",
            "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "file_name": file_info.get("file_name"),
            "file_size": file_info.get("size"),
        }

        metadata_path = version_dir / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2, default=str)

        logger.debug(f"Wrote metadata: {metadata_path}")

    def _write_checksum(self, version_dir: Path, file_path: Path) -> None:
        """Write SHA256 checksum for the file."""
        try:
            checksum = compute_sha256(file_path)
            checksums_path = version_dir / "checksums.txt"

            with open(checksums_path, "w") as f:
                f.write(f"SHA256({file_path.name})= {checksum}\n")

            logger.debug(f"Wrote checksum: {checksums_path}")
        except Exception as e:
            logger.warning(f"Failed to compute checksum: {e}")
