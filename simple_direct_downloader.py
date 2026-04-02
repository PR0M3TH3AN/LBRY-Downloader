"""Simple direct downloader - uses Odysee's public API."""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Optional

try:
    import requests
except ImportError:
    raise ImportError("requests is required")

from models import Config, DownloadAction

logger = logging.getLogger(__name__)


class SimpleDirectDownloader:
    """Simple downloader that gets files from Odysee CDN."""

    def __init__(self, config: Config, base_dir: Path):
        self.config = config
        self.base_dir = base_dir
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"
            }
        )

    def download(self, action: DownloadAction, dry_run: bool = False) -> bool:
        """Download a file from Odysee."""
        if action.action == "skip_existing":
            return True

        if dry_run:
            print(f"[DRY-RUN] Would download: {action.claim_name}")
            return True

        version_dir = Path(action.target_dir)
        version_dir.mkdir(parents=True, exist_ok=True)

        try:
            print(f"\n📥 Downloading: {action.claim_name}")

            # Get the Odysee URL from the LBRY URI
            odysee_url = self._get_odysee_url(action.uri)
            print(f"   URL: {odysee_url}")

            # Method 1: Try to get the download link from the page
            download_url = self._get_download_link_from_page(odysee_url)

            if not download_url:
                # Method 2: Try API
                download_url = self._get_from_api(action.uri)

            if not download_url:
                print(f"   ⚠️ Could not find download URL")
                return False

            print(f"   Download URL found!")

            # Download the file
            return self._download_file(
                download_url, version_dir, action.claim_name, action
            )

        except Exception as e:
            print(f"   ❌ Error: {e}")
            logger.error(f"Download failed: {e}")
            return False

    def _get_odysee_url(self, lbry_uri: str) -> str:
        """Convert LBRY URI to Odysee URL."""
        # lbry://@channel/claim#id -> https://odysee.com/@channel:claim
        uri = lbry_uri.replace("lbry://", "")
        parts = uri.split("/")
        if len(parts) >= 2:
            channel = parts[0].replace("#", ":")
            claim = parts[1].split("#")[0]
            return f"https://odysee.com/{channel}/{claim}"
        return f"https://odysee.com/{uri.replace('#', ':')}"

    def _get_download_link_from_page(self, odysee_url: str) -> Optional[str]:
        """Try to extract download link from Odysee page."""
        try:
            response = self.session.get(odysee_url, timeout=30)
            if response.status_code == 200:
                # Look for various patterns
                patterns = [
                    r'"content\":\{\"url\":\"([^\"]+)\"',
                    r'"streaming_url\":\"([^\"]+)\"',
                    r'"download_url\":\"([^\"]+)\"',
                    r'"url\":\"(https://player\.odycdn\.com/[^\"]+)\"',
                ]

                for pattern in patterns:
                    match = re.search(pattern, response.text)
                    if match:
                        url = match.group(1).replace("\\u0026", "&")
                        if url.startswith("http"):
                            return url

            return None
        except Exception as e:
            logger.debug(f"Could not get from page: {e}")
            return None

    def _get_from_api(self, lbry_uri: str) -> Optional[str]:
        """Try to get download URL from Odysee API."""
        try:
            api_url = "https://api.lbry.tv/api/v1/proxy"

            payload = {
                "jsonrpc": "2.0",
                "method": "resolve",
                "params": {"urls": [lbry_uri]},
                "id": 1,
            }

            response = self.session.post(api_url, json=payload, timeout=30)

            if response.status_code == 200:
                data = response.json()
                result = data.get("result", {}).get(lbry_uri, {})

                # Get claim ID
                claim_id = result.get("claim_id", "")
                if claim_id:
                    # Try common Odysee CDN patterns
                    urls_to_try = [
                        f"https://player.odycdn.com/v6/streams/{claim_id}",
                        f"https://player.odycdn.com/v6/streams/{claim_id}/",
                        f"https://cdn.lbryplayer.xyz/content/claims/{claim_id}/stream",
                    ]

                    for url in urls_to_try:
                        # Test if URL works
                        head_response = self.session.head(
                            url, timeout=10, allow_redirects=True
                        )
                        if head_response.status_code == 200:
                            return url

            return None
        except Exception as e:
            logger.debug(f"API error: {e}")
            return None

    def _download_file(
        self, url: str, version_dir: Path, claim_name: str, action: DownloadAction
    ) -> bool:
        """Download the file with progress."""
        try:
            # Try to determine filename
            filename = f"{claim_name}.mp4"  # Default

            response = self.session.get(url, stream=True, timeout=300)

            # Try to get filename from headers
            cd_header = response.headers.get("content-disposition", "")
            if "filename=" in cd_header:
                import re

                fname_match = re.search(r'filename="?([^"]+)"?', cd_header)
                if fname_match:
                    filename = fname_match.group(1)

            file_path = version_dir / filename

            total_size = int(response.headers.get("content-length", 0))

            if total_size > 0:
                size_mb = total_size / (1024 * 1024)
                print(f"   Size: {size_mb:.2f} MB")

            print(f"   Saving to: {filename}")
            print()

            # Download with progress
            downloaded = 0
            start_time = time.time()
            last_update = start_time

            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        current_time = time.time()
                        if current_time - last_update >= 0.5:
                            self._print_progress(downloaded, total_size, start_time)
                            last_update = current_time

            self._print_progress(downloaded, total_size, start_time, final=True)
            print()

            # Verify
            if file_path.exists() and file_path.stat().st_size > 0:
                size_mb = file_path.stat().st_size / (1024 * 1024)
                elapsed = time.time() - start_time
                speed = size_mb / elapsed if elapsed > 0 else 0
                print(f"   ✅ Complete: {size_mb:.2f} MB @ {speed:.2f} MB/s")

                # Write metadata
                self._write_metadata(version_dir, action, file_path)
                return True
            else:
                print(f"   ❌ Download failed")
                return False

        except Exception as e:
            print(f"   ❌ Error: {e}")
            return False

    def _print_progress(
        self, downloaded: int, total: int, start_time: float, final: bool = False
    ):
        """Print progress bar."""
        if total > 0:
            percent = min(100, int((downloaded / total) * 100))
            filled = int(40 * percent / 100)
            bar = "█" * filled + "░" * (40 - filled)

            elapsed = time.time() - start_time
            if elapsed > 0:
                speed = (downloaded / (1024 * 1024)) / elapsed
                print(f"\r   [{bar}] {percent}% | {speed:.2f} MB/s", end="", flush=True)
        else:
            mb = downloaded / (1024 * 1024)
            print(f"\r   Downloaded: {mb:.2f} MB", end="", flush=True)

    def _write_metadata(
        self, version_dir: Path, action: DownloadAction, file_path: Path
    ):
        """Write metadata file."""
        metadata = {
            "claim_id": action.claim_id,
            "claim_name": action.claim_name,
            "version_token": action.version_token,
            "uri": action.uri,
            "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "file_name": file_path.name,
            "file_size": file_path.stat().st_size,
            "download_source": "odysee_direct",
        }

        meta_path = version_dir / "metadata.json"
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Wrote metadata: {meta_path}")
