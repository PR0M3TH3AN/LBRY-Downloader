"""Direct downloader module - downloads from Odysee's direct web endpoints."""

import json
import logging
import time
from pathlib import Path
from typing import Dict
from urllib.parse import quote

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
    """Downloads content directly from Odysee's web-exposed endpoints."""

    stream_path = "/$/stream"
    download_path = "/$/download"

    def __init__(self, config: Config, base_dir: Path):
        self.config = config
        self.base_dir = base_dir
        self.direct_base_urls = [
            base_url.rstrip("/") for base_url in config.general.direct_base_urls
        ]
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"
                )
            }
        )

    def _claim_slug(self, action: DownloadAction) -> str:
        """Choose the best available slug for Odysee URLs."""
        slug = (
            action.metadata.get("normalized_name")
            or action.metadata.get("name")
            or action.claim_name
        )
        return slug

    def build_stream_url(self, action: DownloadAction, base_url: str | None = None) -> str:
        """Build Odysee's public direct-stream URL for a claim."""
        slug = self._claim_slug(action)
        chosen_base = (base_url or self.direct_base_urls[0]).rstrip("/")
        return f"{chosen_base}{self.stream_path}/{quote(slug, safe='')}/{action.claim_id}"

    def build_download_url(self, action: DownloadAction, base_url: str | None = None) -> str:
        """Build Odysee's public download-entry URL for a claim."""
        slug = self._claim_slug(action)
        chosen_base = (base_url or self.direct_base_urls[0]).rstrip("/")
        return (
            f"{chosen_base}{self.download_path}/{quote(slug, safe='')}/{action.claim_id}"
        )

    def _is_streaming_media(self, action: DownloadAction) -> bool:
        """Return True when the claim looks like audio/video media."""
        stream_type = (action.metadata.get("stream_type") or "").lower()
        media_type = (action.metadata.get("source_media_type") or "").lower()

        if stream_type in {"video", "audio"}:
            return True
        if media_type.startswith("video/") or media_type.startswith("audio/"):
            return True
        return False

    def build_candidate_urls(self, action: DownloadAction) -> list[str]:
        """Build Odysee direct-download URL candidates in priority order."""
        candidate_urls = []
        for base_url in self.direct_base_urls:
            stream_url = self.build_stream_url(action, base_url=base_url)
            download_url = self.build_download_url(action, base_url=base_url)
            if self._is_streaming_media(action):
                candidate_urls.extend([stream_url, download_url])
            else:
                candidate_urls.extend([download_url, stream_url])
        return candidate_urls

    def download(self, action: DownloadAction, dry_run: bool = False) -> bool:
        """
        Download a claim directly from Odysee.

        Args:
            action: The download action.
            dry_run: If True, don't actually download.

        Returns:
            True if download succeeded.
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
            logger.info(f"[DRY-RUN] Would download from Odysee: {action.claim_name}")
            return True

        version_dir = Path(action.target_dir)
        version_dir.mkdir(parents=True, exist_ok=True)

        file_name = action.metadata.get("source_name") or f"{action.claim_name}.bin"
        file_path = version_dir / file_name

        logger.info(f"Downloading from Odysee: {action.claim_name}")
        logger.info(f"Saving to: {file_path}")

        try:
            last_error = None
            for index, download_url in enumerate(
                self.build_candidate_urls(action), start=1
            ):
                logger.info(f"Direct URL candidate {index}: {download_url}")
                success, failure_reason = self._download_file(
                    download_url, file_path, action.claim_name
                )
                if success:
                    break
                last_error = failure_reason
            else:
                raise DirectDownloadError(last_error or "Odysee direct download failed")

            logger.info(f"Downloaded: {action.claim_name} -> {file_path.name}")

            file_info = {
                "download_path": str(file_path),
                "file_name": file_path.name,
                "size": file_path.stat().st_size,
            }
            self._write_metadata(version_dir, action, file_info)

            if self.config.general.write_checksums:
                self._write_checksum(version_dir, file_path)

            try:
                rel_path = file_path.relative_to(self.base_dir)
                action.metadata["local_file_path"] = str(rel_path)
            except ValueError:
                action.metadata["local_file_path"] = str(file_path)

            return True

        except DirectDownloadError:
            raise
        except Exception as e:
            logger.error(f"Direct download failed for {action.claim_name}: {e}")
            raise DirectDownloadError(f"Download failed: {e}")

    def _download_file(
        self, url: str, file_path: Path, claim_name: str
    ) -> tuple[bool, str | None]:
        """
        Download file from URL with progress display.

        Args:
            url: Download URL.
            file_path: Target file path.
            claim_name: Name of the claim for display.

        Returns:
            Tuple of success flag and optional failure reason.
        """
        attempts = self.config.general.direct_max_retries_per_url + 1
        for attempt in range(1, attempts + 1):
            try:
                print(f"\n  Downloading: {claim_name}")
                print(f"   Filename: {file_path.name}")
                print(f"   Saving to: {file_path}")
                print(f"   Source: {url}")

                response = self.session.get(
                    url,
                    stream=True,
                    timeout=300,
                    headers={"Referer": "https://odysee.com/"},
                )
                response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                if "text/html" in content_type:
                    logger.warning("Got HTML response instead of file content")
                    return False, "Got HTML response instead of file content"

                total_size = int(response.headers.get("content-length", 0))
                if total_size > 0:
                    size_mb = total_size / (1024 * 1024)
                    print(f"   Size: {size_mb:.2f} MB")
                else:
                    print("   Size: Unknown")
                print()

                start_time = time.time()
                last_update = start_time
                downloaded = 0

                with open(file_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

                            current_time = time.time()
                            if current_time - last_update >= 0.5:
                                self._print_progress_bar(
                                    downloaded, total_size, start_time
                                )
                                last_update = current_time

                    self._print_progress_bar(
                        downloaded, total_size, start_time, final=True
                    )
                    print()

                if file_path.exists() and file_path.stat().st_size > 0:
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    elapsed = time.time() - start_time
                    speed_mbps = (size_mb / elapsed) if elapsed > 0 else 0
                    print(f"   Complete: {size_mb:.2f} MB @ {speed_mbps:.2f} MB/s\n")
                    return True, None

                if file_path.exists():
                    file_path.unlink()
                print("   Error: Downloaded file is empty\n")
                return False, "Downloaded file is empty"

            except requests.exceptions.HTTPError as e:
                status_code = getattr(e.response, "status_code", None)
                if status_code == 401:
                    logger.error(f"HTTP 401 downloading file: {e}")
                    reason = "Odysee CDN rejected this direct URL as unauthorized"
                elif status_code == 429:
                    logger.error(f"HTTP 429 downloading file: {e}")
                    if file_path.exists():
                        file_path.unlink()
                    if attempt < attempts:
                        backoff = (
                            self.config.general.direct_retry_backoff_seconds
                            * (2 ** (attempt - 1))
                        )
                        logger.warning(
                            "HTTP 429 downloading %s. Retrying in %.1fs (%s/%s)",
                            claim_name,
                            backoff,
                            attempt,
                            attempts - 1,
                        )
                        time.sleep(backoff)
                        continue
                    reason = (
                        "Odysee CDN rate-limited the direct download request after retries"
                    )
                else:
                    logger.error(f"HTTP error downloading file: {e}")
                    reason = f"HTTP error: {e}"
                if file_path.exists():
                    file_path.unlink()
                return False, reason
            except Exception as e:
                logger.error(f"Error downloading file: {e}")
                if file_path.exists():
                    file_path.unlink()
                return False, str(e)
        return False, "Direct download failed"

    def _print_progress_bar(
        self,
        downloaded: int,
        total_size: int,
        start_time: float,
        final: bool = False,
    ) -> None:
        """Print a progress bar to the console."""
        if total_size > 0:
            percent = min(100, int((downloaded / total_size) * 100))
            filled = int(50 * percent / 100)
            bar = "\u2588" * filled + "\u2591" * (50 - filled)

            elapsed = time.time() - start_time
            speed_mbps = 0
            if elapsed > 0:
                speed_mbps = (downloaded / (1024 * 1024)) / elapsed
                speed_str = f"{speed_mbps:.2f} MB/s"
            else:
                speed_str = "calculating..."

            if not final and speed_mbps > 0:
                remaining = (total_size - downloaded) / (1024 * 1024)
                eta = remaining / speed_mbps
                eta_str = f"ETA: {int(eta)}s"
            else:
                eta_str = ""

            print(
                f"\r   [{bar}] {percent}% | {speed_str} | {eta_str}",
                end="",
                flush=True,
            )
        else:
            downloaded_mb = downloaded / (1024 * 1024)
            print(f"\r   Downloaded: {downloaded_mb:.2f} MB", end="", flush=True)

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
            "download_source": (
                "odysee_stream" if self._is_streaming_media(action) else "odysee_download"
            ),
            "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "file_name": file_info.get("file_name"),
            "file_size": file_info.get("size"),
            "stream_type": action.metadata.get("stream_type"),
            "source_media_type": action.metadata.get("source_media_type"),
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
