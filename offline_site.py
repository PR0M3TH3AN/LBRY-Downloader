"""Metadata backfill and offline site generation for the archive."""

import html
import json
import logging
import mimetypes
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    requests = None

from models import Channel, Config, DownloadAction


logger = logging.getLogger(__name__)


class ArchiveSiteManager:
    """Maintains archive metadata sidecars and builds a static offline site."""

    def __init__(self, config: Config, base_dir: Path):
        self.config = config
        self.base_dir = base_dir
        self.channels_root = self.base_dir / "channels"
        self.site_root = Path(config.general.offline_site_dir)
        self.session = requests.Session() if requests else None
        if self.session:
            self.session.headers.update(
                {
                    "User-Agent": (
                        "Mozilla/5.0 (X11; Linux x86_64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/123.0.0.0 Safari/537.36"
                    )
                }
            )

    def ensure_channel_artifacts(self, channel: Channel) -> None:
        """Write channel metadata and fetch any missing channel assets."""
        channel_dir = self._channel_dir(channel)
        channel_dir.mkdir(parents=True, exist_ok=True)

        channel_payload = {
            "channel_claim_id": channel.channel_claim_id,
            "channel_name": channel.channel_name,
            "display_name": channel.display_name,
            "input": channel.input,
            "normalized_uri": channel.normalized_uri,
            "permanent_url": channel.permanent_url,
            "short_url": channel.short_url,
            "canonical_url": channel.canonical_url,
            "description": channel.description,
            "thumbnail_url": channel.thumbnail_url,
            "cover_url": channel.cover_url,
            "website_url": channel.website_url,
            "email": channel.email,
            "tags": channel.tags,
            "languages": channel.languages,
            "links": channel.links,
            "folder": channel.folder,
            "download_path": channel.download_path,
            "last_scan": channel.last_scan,
        }

        self._write_json(channel_dir / "channel.json", channel_payload)

        if self.config.general.fetch_missing_metadata_assets:
            if channel.thumbnail_url:
                self._ensure_remote_asset(
                    channel.thumbnail_url,
                    channel_dir,
                    basename="channel-profile",
                )
            if channel.cover_url:
                self._ensure_remote_asset(
                    channel.cover_url,
                    channel_dir,
                    basename="channel-cover",
                )

    def ensure_claim_artifacts(self, channel: Channel, action: DownloadAction) -> None:
        """Write/update claim- and version-level metadata for a claim."""
        version_dir = Path(action.target_dir)
        claim_dir = version_dir.parent.parent
        claim_dir.mkdir(parents=True, exist_ok=True)
        version_dir.mkdir(parents=True, exist_ok=True)

        file_path = self._resolve_action_file_path(action, version_dir)
        file_size = file_path.stat().st_size if file_path and file_path.exists() else None

        claim_payload = {
            "claim_id": action.claim_id,
            "channel_claim_id": action.channel_claim_id,
            "name": action.claim_name,
            "title": action.metadata.get("title"),
            "permanent_url": action.uri,
            "short_url": action.metadata.get("short_url"),
            "canonical_url": action.metadata.get("canonical_url"),
            "description": action.metadata.get("description"),
            "thumbnail_url": action.metadata.get("thumbnail_url"),
            "tags": action.metadata.get("tags", []),
            "languages": action.metadata.get("languages", []),
            "links": action.metadata.get("links", []),
            "release_time": action.metadata.get("release_time"),
            "timestamp": action.metadata.get("timestamp"),
            "stream_type": action.metadata.get("stream_type"),
            "source_media_type": action.metadata.get("source_media_type"),
            "source_name": action.metadata.get("source_name"),
            "claim_folder": self._path_label(claim_dir),
            "latest_version_token": action.version_token,
            "channel_folder": channel.folder,
        }
        self._write_json(claim_dir / "claim.json", claim_payload)

        version_payload = {
            "claim_id": action.claim_id,
            "channel_claim_id": action.channel_claim_id,
            "name": action.claim_name,
            "title": action.metadata.get("title"),
            "description": action.metadata.get("description"),
            "version_token": action.version_token,
            "permanent_url": action.uri,
            "short_url": action.metadata.get("short_url"),
            "canonical_url": action.metadata.get("canonical_url"),
            "download_source": self._download_source_label(action),
            "file_name": file_path.name if file_path else action.metadata.get("file_name"),
            "file_size": file_size,
            "stream_type": action.metadata.get("stream_type"),
            "source_media_type": action.metadata.get("source_media_type"),
            "thumbnail_url": action.metadata.get("thumbnail_url"),
            "tags": action.metadata.get("tags", []),
            "languages": action.metadata.get("languages", []),
            "links": action.metadata.get("links", []),
            "release_time": action.metadata.get("release_time"),
            "timestamp": action.metadata.get("timestamp"),
        }
        self._write_json(version_dir / "metadata.json", version_payload)

        if action.metadata.get("thumbnail_url") and self.config.general.fetch_missing_metadata_assets:
            self._ensure_remote_asset(
                action.metadata["thumbnail_url"],
                claim_dir,
                basename="claim-thumbnail",
            )

    def build_site(self, channel_index: Optional[Dict[str, Channel]] = None) -> None:
        """Build a static offline site from the archive metadata."""
        self.site_root.mkdir(parents=True, exist_ok=True)
        self._write_text(self.site_root / "assets" / "style.css", self._site_css())

        channels = self._collect_channel_records(channel_index=channel_index)
        self._write_text(
            self.site_root / "index.html",
            self._render_index_page(channels),
        )

        channels_site_root = self.site_root / "channels"
        for channel in channels:
            channel_page_dir = channels_site_root / channel["folder"]
            channel_page_dir.mkdir(parents=True, exist_ok=True)
            self._write_text(
                channel_page_dir / "index.html",
                self._render_channel_page(channel, channel_page_dir),
            )

            for claim in channel["claims"]:
                claim_page_dir = channel_page_dir / "claims" / claim["folder"]
                claim_page_dir.mkdir(parents=True, exist_ok=True)
                self._write_text(
                    claim_page_dir / "index.html",
                    self._render_claim_page(channel, claim, claim_page_dir),
                )

    def _channel_dir(self, channel: Channel) -> Path:
        if channel.download_path:
            return Path(channel.download_path) / channel.folder
        return self.channels_root / channel.folder

    def _resolve_action_file_path(
        self, action: DownloadAction, version_dir: Path
    ) -> Optional[Path]:
        local_file_path = action.metadata.get("local_file_path")
        if local_file_path:
            path = Path(local_file_path)
            if not path.is_absolute():
                path = self.base_dir / path
            if path.exists():
                return path

        existing_relpath = action.metadata.get("existing_file_relpath")
        if existing_relpath:
            path = self.base_dir / existing_relpath
            if path.exists():
                return path

        source_name = action.metadata.get("source_name") or action.metadata.get("file_name")
        if source_name:
            path = version_dir / source_name
            if path.exists():
                return path

        candidates = [
            item
            for item in version_dir.iterdir()
            if item.is_file() and item.name not in {"metadata.json", "download.json", "checksums.txt"}
        ] if version_dir.exists() else []
        return candidates[0] if candidates else None

    def _download_source_label(self, action: DownloadAction) -> str:
        media_type = (action.metadata.get("source_media_type") or "").lower()
        if media_type.startswith("video/") or media_type.startswith("audio/"):
            return "odysee_stream"
        return "odysee_download"

    def _ensure_remote_asset(self, url: str, target_dir: Path, basename: str) -> Optional[Path]:
        if not self.session:
            return None

        existing = self._existing_asset(target_dir, basename)
        if existing:
            return existing[0]

        try:
            response = self.session.get(url, timeout=60, stream=True)
            response.raise_for_status()
            with tempfile.NamedTemporaryFile(dir=target_dir, delete=False) as handle:
                shutil.copyfileobj(response.raw, handle)
                temp_path = Path(handle.name)

            suffix = self._suffix_for_response(url, response.headers.get("Content-Type"), temp_path)
            target_path = target_dir / f"{basename}{suffix}"
            temp_path.replace(target_path)
            return target_path
        except Exception as exc:
            logger.warning("Failed to fetch metadata asset %s: %s", url, exc)
            temp_path = locals().get("temp_path")
            if temp_path and Path(temp_path).exists():
                Path(temp_path).unlink()
            return None

    def _suffix_for_url(self, url: str) -> str:
        parsed = urlparse(url)
        suffix = Path(parsed.path).suffix
        if suffix:
            return suffix
        mime_guess, _ = mimetypes.guess_type(url)
        return mimetypes.guess_extension(mime_guess or "") or ".bin"

    def _suffix_for_response(
        self, url: str, content_type: Optional[str], downloaded_path: Path
    ) -> str:
        suffix = self._suffix_for_content_type(content_type)
        if suffix:
            return suffix

        suffix = self._suffix_for_image_bytes(downloaded_path)
        if suffix:
            return suffix

        return self._suffix_for_url(url)

    def _suffix_for_content_type(self, content_type: Optional[str]) -> Optional[str]:
        if not content_type:
            return None
        mime = content_type.split(";", 1)[0].strip().lower()
        if mime == "image/jpeg":
            return ".jpg"
        if mime == "image/png":
            return ".png"
        if mime == "image/webp":
            return ".webp"
        guessed = mimetypes.guess_extension(mime)
        return guessed

    def _suffix_for_image_bytes(self, path: Path) -> Optional[str]:
        try:
            header = path.read_bytes()[:16]
        except OSError:
            return None

        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return ".png"
        if header.startswith(b"\xff\xd8\xff"):
            return ".jpg"
        if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
            return ".webp"
        return None

    def _existing_asset(self, directory: Path, basename: str) -> List[Path]:
        normalized = []
        for asset_path in sorted(directory.glob(f"{basename}.*")):
            normalized.append(self._normalize_asset_extension(asset_path))
        return normalized

    def _normalize_asset_extension(self, path: Path) -> Path:
        actual_suffix = self._suffix_for_image_bytes(path)
        if not actual_suffix or path.suffix.lower() == actual_suffix:
            return path

        corrected_path = path.with_suffix(actual_suffix)
        if corrected_path.exists():
            path.unlink()
            return corrected_path

        path.rename(corrected_path)
        return corrected_path

    def _collect_channel_records(
        self, channel_index: Optional[Dict[str, Channel]] = None
    ) -> List[Dict[str, Any]]:
        channel_dirs: Dict[Path, Path] = {}
        if self.channels_root.exists():
            for channel_dir in self.channels_root.iterdir():
                if channel_dir.is_dir():
                    channel_dirs[channel_dir.resolve()] = channel_dir

        for channel in (channel_index or {}).values():
            channel_dir = self._channel_dir(channel)
            if channel_dir.exists():
                channel_dirs[channel_dir.resolve()] = channel_dir

        channels = []
        for channel_dir in sorted(channel_dirs.values()):

            channel_data = self._read_json(channel_dir / "channel.json") or {
                "folder": channel_dir.name,
                "channel_name": channel_dir.name,
                "display_name": channel_dir.name,
                "description": None,
                "links": [],
            }
            channel_data["folder"] = channel_dir.name
            channel_data["path"] = channel_dir
            channel_data["profile_asset"] = self._find_asset(channel_dir, "channel-profile")
            channel_data["cover_asset"] = self._find_asset(channel_dir, "channel-cover")
            claims = self._collect_claim_records(channel_dir)
            channel_data["claims"] = claims
            channel_data["claim_count"] = len(claims)
            channel_data["version_count"] = sum(len(claim["versions"]) for claim in claims)
            channels.append(channel_data)

        channels.sort(
            key=lambda item: (item.get("display_name") or item.get("channel_name") or "").lower()
        )
        channels.sort(key=lambda item: item.get("last_scan") or "", reverse=True)
        return channels

    def _collect_claim_records(self, channel_dir: Path) -> List[Dict[str, Any]]:
        claims_root = channel_dir / "claims"
        claims = []
        for claim_dir in sorted(claims_root.iterdir()) if claims_root.exists() else []:
            if not claim_dir.is_dir():
                continue

            claim_data = self._read_json(claim_dir / "claim.json") or {
                "name": claim_dir.name,
                "title": claim_dir.name,
                "description": None,
                "links": [],
            }
            versions = self._collect_versions(claim_dir)
            latest_version = versions[0] if versions else {}
            claim_data["folder"] = claim_dir.name
            claim_data["path"] = claim_dir
            claim_data["thumbnail_asset"] = self._find_asset(claim_dir, "claim-thumbnail")
            if not claim_data["thumbnail_asset"]:
                claim_data["thumbnail_asset"] = self._extract_video_thumbnail(claim_dir, versions)
            claim_data["thumbnail_url"] = claim_data.get("thumbnail_url") or latest_version.get(
                "thumbnail_url"
            )
            claim_data["title"] = claim_data.get("title") or latest_version.get("title")
            claim_data["description"] = claim_data.get("description") or latest_version.get(
                "description"
            )
            claim_data["release_time"] = claim_data.get("release_time") or latest_version.get(
                "release_time"
            )
            claim_data["versions"] = versions
            claims.append(claim_data)

        claims.sort(
            key=lambda item: (
                -self._numeric_sort_value(item.get("release_time")),
                (item.get("title") or item.get("name") or "").lower(),
            )
        )
        return claims

    def _collect_versions(self, claim_dir: Path) -> List[Dict[str, Any]]:
        versions_root = claim_dir / "versions"
        versions = []
        for version_dir in sorted(versions_root.iterdir()) if versions_root.exists() else []:
            if not version_dir.is_dir():
                continue

            version_data = self._read_json(version_dir / "metadata.json") or {
                "version_token": version_dir.name
            }
            version_data["path"] = version_dir
            version_data["version_token"] = version_data.get("version_token") or version_dir.name
            file_path = self._find_primary_file(version_dir)
            version_data["file_path"] = file_path
            versions.append(version_data)

        versions.sort(
            key=lambda item: (
                -self._numeric_sort_value(item.get("release_time")),
                item["version_token"],
            )
        )
        return versions

    def _extract_video_thumbnail(
        self, claim_dir: Path, versions: List[Dict[str, Any]]
    ) -> Optional[Path]:
        for version in versions:
            file_path = version.get("file_path")
            if not file_path or not self._is_video_version(version, file_path):
                continue

            target_path = claim_dir / "claim-thumbnail.jpg"
            if self._run_ffmpeg_thumbnail(file_path, target_path):
                return target_path

        return None

    def _is_video_version(self, version: Dict[str, Any], file_path: Path) -> bool:
        media_type = self._version_media_type(version, file_path).lower()
        return media_type.startswith("video/")

    def _run_ffmpeg_thumbnail(self, input_path: Path, output_path: Path) -> bool:
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            "1",
            "-i",
            str(input_path),
            "-frames:v",
            "1",
            "-vf",
            "scale='min(960,iw)':-2",
            str(output_path),
        ]
        try:
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return output_path.exists() and output_path.stat().st_size > 0
        except (OSError, subprocess.CalledProcessError):
            if output_path.exists():
                output_path.unlink()
            return False

    def _find_primary_file(self, version_dir: Path) -> Optional[Path]:
        metadata_name = {"metadata.json", "download.json", "checksums.txt"}
        files = [item for item in version_dir.iterdir() if item.is_file() and item.name not in metadata_name]
        return files[0] if files else None

    def _find_asset(self, directory: Path, basename: str) -> Optional[Path]:
        matches = self._existing_asset(directory, basename)
        return matches[0] if matches else None

    def _numeric_sort_value(self, value: Any) -> int:
        """Convert mixed metadata values into a safe descending sort key."""
        if value is None or value == "":
            return 0
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return 0
            try:
                return int(stripped)
            except ValueError:
                try:
                    return int(float(stripped))
                except ValueError:
                    logger.debug("Non-numeric release_time value in archive metadata: %r", value)
                    return 0
        return 0

    def _render_index_page(self, channels: List[Dict[str, Any]]) -> str:
        cards = []
        for channel in channels:
            title = channel.get("display_name") or channel.get("channel_name") or channel["folder"]
            description = channel.get("description") or ""
            profile = self._image_tag(
                channel.get("profile_asset"),
                self.site_root,
                css_class="avatar",
                mirror_key=f"channels/{channel['folder']}/channel-profile",
            )
            link = f"channels/{channel['folder']}/index.html"
            cards.append(
                f"""
                <article class="card channel-card">
                  <a class="card-link" href="{html.escape(link)}">
                    {profile}
                    <div class="card-body">
                      <h2>{html.escape(title)}</h2>
                      <p class="muted">{html.escape(channel.get('channel_name') or '')}</p>
                      <p>{html.escape(self._truncate(description, 220))}</p>
                      <p class="meta">{channel['claim_count']} claims | {channel['version_count']} versions</p>
                    </div>
                  </a>
                </article>
                """
            )

        body = "\n".join(cards) or "<p>No channels found.</p>"
        return self._page(
            title="LBRY Archive",
            body=f"""
            <header class="hero">
              <div>
                <p class="eyebrow">Offline Archive</p>
                <h1>LBRY / Odysee Archive</h1>
                <p class="lede">Browse downloaded channels, claims, metadata, and local files without needing the live site.</p>
              </div>
            </header>
            <section class="grid">{body}</section>
            """,
            root=self.site_root,
        )

    def _render_channel_page(self, channel: Dict[str, Any], page_dir: Path) -> str:
        title = channel.get("display_name") or channel.get("channel_name") or channel["folder"]
        cover = self._image_tag(
            channel.get("cover_asset"),
            page_dir,
            css_class="cover",
            mirror_key=f"channels/{channel['folder']}/channel-cover",
        )
        profile = self._image_tag(
            channel.get("profile_asset"),
            page_dir,
            css_class="avatar large",
            mirror_key=f"channels/{channel['folder']}/channel-profile",
        )
        claims_html = []
        for claim in channel["claims"]:
            claim_title = claim.get("title") or claim.get("name") or claim["folder"]
            thumb = self._image_tag(
                claim.get("thumbnail_asset"),
                page_dir,
                css_class="thumb",
                fallback_url=claim.get("thumbnail_url"),
                mirror_key=f"channels/{channel['folder']}/claims/{claim['folder']}/claim-thumbnail",
            )
            link = f"claims/{claim['folder']}/index.html"
            claims_html.append(
                f"""
                <article class="card claim-card">
                  <a class="card-link" href="{html.escape(link)}">
                    {thumb}
                    <div class="card-body">
                      <h2>{html.escape(claim_title)}</h2>
                      <p>{html.escape(self._truncate(claim.get('description') or '', 180))}</p>
                      <p class="meta">{len(claim['versions'])} version(s)</p>
                    </div>
                  </a>
                </article>
                """
            )
        links = self._render_links(channel.get("links", []))
        return self._page(
            title=title,
            body=f"""
            <nav class="breadcrumbs"><a href="../../index.html">Archive</a></nav>
            {cover}
            <header class="channel-header">
              {profile}
              <div>
                <p class="eyebrow">Channel</p>
                <h1>{html.escape(title)}</h1>
                <p class="muted">{html.escape(channel.get('channel_name') or '')}</p>
                <p>{html.escape(channel.get('description') or '')}</p>
                {links}
              </div>
            </header>
            <section class="grid">{''.join(claims_html) or '<p>No claims found.</p>'}</section>
            """,
            root=page_dir,
        )

    def _render_claim_page(self, channel: Dict[str, Any], claim: Dict[str, Any], page_dir: Path) -> str:
        title = claim.get("title") or claim.get("name") or claim["folder"]
        thumb = self._image_tag(
            claim.get("thumbnail_asset"),
            page_dir,
            css_class="hero-thumb",
            fallback_url=claim.get("thumbnail_url"),
            mirror_key=f"channels/{channel['folder']}/claims/{claim['folder']}/claim-thumbnail",
        )
        versions = []
        for version in claim["versions"]:
            file_link = ""
            media_preview = ""
            if version.get("file_path"):
                href = self._rel_href(page_dir, version["file_path"])
                file_name = version["file_path"].name
                file_link = f'<p><a href="{html.escape(href)}">Open local file: {html.escape(file_name)}</a></p>'
                media_preview = self._render_version_preview(version, page_dir, href)
            versions.append(
                f"""
                <article class="version">
                  <h2>{html.escape(version.get('version_token') or 'version')}</h2>
                  <p class="meta">{html.escape(version.get('source_media_type') or version.get('stream_type') or '')}</p>
                  <p>{html.escape(version.get('description') or '')}</p>
                  {media_preview}
                  {file_link}
                </article>
                """
            )
        links = self._render_links(claim.get("links", []))
        return self._page(
            title=title,
            body=f"""
            <nav class="breadcrumbs">
              <a href="../../../../index.html">Archive</a>
              <a href="../../index.html">{html.escape(channel.get('display_name') or channel.get('channel_name') or channel['folder'])}</a>
            </nav>
            <header class="claim-header">
              {thumb}
              <div>
                <p class="eyebrow">Claim</p>
                <h1>{html.escape(title)}</h1>
                <p>{html.escape(claim.get('description') or '')}</p>
                {links}
              </div>
            </header>
            <section class="versions">{''.join(versions) or '<p>No versions found.</p>'}</section>
            """,
            root=page_dir,
        )

    def _image_tag(
        self,
        image_path: Optional[Path],
        page_dir: Path,
        css_class: str,
        fallback_url: Optional[str] = None,
        mirror_key: Optional[str] = None,
    ) -> str:
        if image_path:
            site_path = self._mirror_site_asset(image_path, mirror_key)
            href = self._rel_href(page_dir, site_path)
        elif fallback_url:
            href = fallback_url
        else:
            return ""
        return f'<img class="{html.escape(css_class)}" src="{html.escape(href)}" alt="" loading="lazy">'

    def _render_version_preview(self, version: Dict[str, Any], page_dir: Path, href: str) -> str:
        file_path = version.get("file_path")
        if not file_path:
            return ""

        media_type = self._version_media_type(version, file_path)
        if media_type.startswith("video/"):
            poster = self._poster_attribute(version, page_dir)
            return (
                f'<video class="media-player" controls preload="metadata"{poster}>'
                f'<source src="{html.escape(href)}" type="{html.escape(media_type)}">'
                "Your browser does not support embedded video playback."
                "</video>"
            )

        if media_type.startswith("audio/"):
            return (
                f'<audio class="audio-player" controls preload="metadata">'
                f'<source src="{html.escape(href)}" type="{html.escape(media_type)}">'
                "Your browser does not support embedded audio playback."
                "</audio>"
            )

        return ""

    def _version_media_type(self, version: Dict[str, Any], file_path: Path) -> str:
        media_type = version.get("source_media_type")
        if media_type:
            return str(media_type)
        guessed, _ = mimetypes.guess_type(file_path.name)
        return guessed or ""

    def _poster_attribute(self, version: Dict[str, Any], page_dir: Path) -> str:
        claim_dir = Path(version["path"]).parent.parent
        thumbnail_asset = self._find_asset(claim_dir, "claim-thumbnail")
        if thumbnail_asset:
            claim_folder = claim_dir.name
            channel_folder = claim_dir.parent.parent.name
            site_path = self._mirror_site_asset(
                thumbnail_asset,
                f"channels/{channel_folder}/claims/{claim_folder}/claim-thumbnail",
            )
            return f' poster="{html.escape(self._rel_href(page_dir, site_path))}"'
        thumbnail_url = version.get("thumbnail_url")
        if thumbnail_url:
            return f' poster="{html.escape(thumbnail_url)}"'
        return ""

    def _mirror_site_asset(self, source_path: Path, mirror_key: Optional[str] = None) -> Path:
        source = Path(source_path)
        if mirror_key:
            target = self.site_root / "_assets" / f"{mirror_key}{source.suffix.lower()}"
        else:
            target = self.site_root / "_assets" / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(source, target)
        return target

    def _render_links(self, links: List[Dict[str, str]]) -> str:
        if not links:
            return ""
        rendered = []
        for link in links:
            label = link.get("label") or link.get("url") or "Link"
            url = link.get("url")
            if not url:
                continue
            rendered.append(
                f'<a class="pill" href="{html.escape(url)}">{html.escape(label)}</a>'
            )
        if not rendered:
            return ""
        return f'<div class="pill-row">{"".join(rendered)}</div>'

    def _page(self, *, title: str, body: str, root: Path) -> str:
        stylesheet = self._rel_href(root, self.site_root / "assets" / "style.css")
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="{html.escape(stylesheet)}">
</head>
<body>
  <main class="shell">
    {body}
  </main>
</body>
</html>
"""

    def _rel_href(self, page_dir: Path, target: Path) -> str:
        return os.path.relpath(Path(target).resolve(), start=Path(page_dir).resolve())

    def _path_label(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.base_dir))
        except ValueError:
            return str(path)

    def _write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)

    def _read_json(self, path: Path) -> Optional[Dict[str, Any]]:
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_text(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def _truncate(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[: limit - 3].rstrip() + "..."

    def _site_css(self) -> str:
        return """
:root {
  --bg: #f5f1e8;
  --ink: #1d1b19;
  --muted: #6b6257;
  --card: #fffaf1;
  --line: #d9cfbf;
  --accent: #9c4a1a;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background:
    radial-gradient(circle at top, rgba(156,74,26,.14), transparent 35%),
    linear-gradient(180deg, #f8f4ec 0%, var(--bg) 100%);
  color: var(--ink);
  font: 16px/1.5 Georgia, "Times New Roman", serif;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.shell { max-width: 1180px; margin: 0 auto; padding: 2rem 1.25rem 4rem; }
.hero, .channel-header, .claim-header {
  display: grid;
  gap: 1rem;
  align-items: start;
  margin-bottom: 2rem;
}
.hero {
  min-height: 12rem;
  border: 1px solid var(--line);
  background: rgba(255,250,241,.8);
  padding: 1.5rem;
}
.eyebrow, .meta, .muted, .breadcrumbs { color: var(--muted); }
.breadcrumbs { margin-bottom: 1rem; display: flex; gap: .75rem; flex-wrap: wrap; }
.grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}
.card, .version {
  border: 1px solid var(--line);
  background: var(--card);
}
.card-link { display: block; color: inherit; height: 100%; }
.card-body { padding: 1rem; }
.avatar {
  width: 72px;
  height: 72px;
  object-fit: cover;
  border-radius: 999px;
  border: 1px solid var(--line);
  margin: 1rem 1rem 0;
}
.avatar.large { width: 112px; height: 112px; margin: 0; }
.cover {
  width: 100%;
  max-height: 240px;
  object-fit: cover;
  border: 1px solid var(--line);
  margin-bottom: 1rem;
}
.thumb, .hero-thumb {
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
  border-bottom: 1px solid var(--line);
}
.hero-thumb { max-width: 420px; border: 1px solid var(--line); }
.pill-row {
  display: flex;
  gap: .5rem;
  flex-wrap: wrap;
  margin-top: .75rem;
}
.pill {
  display: inline-block;
  border: 1px solid var(--line);
  padding: .35rem .65rem;
  border-radius: 999px;
  background: #fff;
}
.versions {
  display: grid;
  gap: 1rem;
}
.version { padding: 1rem; }
.media-player, .audio-player {
  width: 100%;
  margin: .75rem 0;
}
.media-player {
  max-width: 100%;
  aspect-ratio: 16 / 9;
  background: #000;
}
@media (min-width: 860px) {
  .channel-header, .claim-header {
    grid-template-columns: auto 1fr;
  }
}
"""
