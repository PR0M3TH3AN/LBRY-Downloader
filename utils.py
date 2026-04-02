"""Utility functions for LBRY Downloader."""

import hashlib
import json
import re
from urllib.parse import urlparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def sanitize_filename(name: str, max_length: int = 120) -> str:
    r"""
    Sanitize a string for use as a filesystem name.

    Rules:
    - Replace /, \, :, *, ?, ", <, >, | with underscore
    - Collapse repeated whitespace
    - Trim trailing periods/spaces
    - Limit length
    """
    # Replace invalid characters
    sanitized = re.sub(r'[\\/*?:"<>|]', "_", name)

    # Collapse whitespace
    sanitized = re.sub(r"\s+", " ", sanitized)

    # Trim trailing periods and spaces
    sanitized = sanitized.rstrip(". ")

    # Limit length while preserving extension
    if len(sanitized) > max_length:
        # Try to preserve extension
        parts = sanitized.rsplit(".", 1)
        if len(parts) == 2 and len(parts[1]) <= 10:
            name_part, ext = parts
            available = max_length - len(ext) - 1
            sanitized = name_part[:available] + "." + ext
        else:
            sanitized = sanitized[:max_length]

    return sanitized


def slugify(text: str) -> str:
    """
    Create a URL-safe slug from text.
    Lowercase, replace spaces with dashes, remove special chars.
    """
    # Lowercase
    text = text.lower()

    # Replace spaces with dashes
    text = re.sub(r"\s+", "-", text)

    # Remove non-alphanumeric except dashes
    text = re.sub(r"[^a-z0-9-]", "", text)

    # Collapse multiple dashes
    text = re.sub(r"-+", "-", text)

    # Trim dashes
    text = text.strip("-")

    return text


def generate_version_token(
    sd_hash: Optional[str] = None,
    stream_hash: Optional[str] = None,
    txid: Optional[str] = None,
    nout: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generate a deterministic version token for a claim version.

    Priority order:
    1. sd_hash
    2. stream_hash
    3. txid:nout
    4. hash of normalized metadata JSON
    """
    if sd_hash:
        return f"sd_{sd_hash[:16]}"

    if stream_hash:
        return f"stream_{stream_hash[:16]}"

    if txid is not None and nout is not None:
        return f"tx_{txid[:16]}_{nout}"

    if metadata:
        # Sort keys for deterministic hash
        metadata_str = json.dumps(metadata, sort_keys=True)
        hash_val = hashlib.sha256(metadata_str.encode()).hexdigest()[:16]
        return f"meta_{hash_val}"

    # Fallback to timestamp-based (should not happen in practice)
    ts = datetime.now(timezone.utc).isoformat()
    hash_val = hashlib.sha256(ts.encode()).hexdigest()[:16]
    return f"fallback_{hash_val}"


def compute_sha256(filepath: Path) -> str:
    """Compute SHA256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def expand_path(path: str) -> Path:
    """Expand ~ and environment variables in a path."""
    import os

    expanded = os.path.expandvars(path)
    return Path(expanded).expanduser().resolve()


def format_timestamp(dt: Optional[datetime] = None) -> str:
    """Format a timestamp in ISO format with timezone."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.isoformat()


def parse_timestamp(ts: str) -> datetime:
    """Parse an ISO format timestamp."""
    return datetime.fromisoformat(ts)


def create_channel_folder_name(channel_name: str, channel_claim_id: str) -> str:
    """Create a folder name for a channel."""
    sanitized = sanitize_filename(channel_name.replace("@", ""))
    # Truncate channel name portion if needed
    max_name_len = 50
    if len(sanitized) > max_name_len:
        sanitized = sanitized[:max_name_len]
    return f"{sanitized}__{channel_claim_id}"


def create_claim_folder_name(claim_name: str, claim_id: str) -> str:
    """Create a folder name for a claim."""
    sanitized = sanitize_filename(claim_name)
    # Truncate claim name portion if needed
    max_name_len = 50
    if len(sanitized) > max_name_len:
        sanitized = sanitized[:max_name_len]
    return f"{sanitized}__{claim_id}"


def is_downloadable_claim(claim_value: Dict[str, Any]) -> bool:
    """
    Determine if a claim represents downloadable content.

    Returns True if the claim has stream/source data that can be downloaded.
    """
    value_type = claim_value.get("value_type", "").lower()

    # Must be a stream type claim
    if value_type != "stream":
        return False

    value = claim_value.get("value", {})

    # Check for source information
    source = value.get("source", {})
    if source:
        # Has source info - likely downloadable
        sd_hash = source.get("sd_hash")
        if sd_hash:
            return True

    # Check for stream hash as fallback
    stream_hash = claim_value.get("stream_hash")
    if stream_hash:
        return True

    return False


def normalize_odysee_url(url: str) -> str:
    """
    Convert an Odysee URL to a LBRY URI format.

    Examples:
    - https://odysee.com/@SomeChannel:1 -> lbry://@SomeChannel#1
    - @SomeChannel:1 -> lbry://@SomeChannel#1
    """
    # Remove https://odysee.com/ prefix if present
    if url.startswith("https://odysee.com/"):
        url = url[len("https://odysee.com/") :]
    elif url.startswith("http://odysee.com/"):
        url = url[len("http://odysee.com/") :]

    # Ensure lbry:// prefix
    if not url.startswith("lbry://"):
        url = f"lbry://{url}"

    return url


def extract_channel_info(resolved_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract normalized channel information from a resolve response.
    """
    claim = resolved_data

    # Handle wrapped response format
    if "claim" in resolved_data:
        claim = resolved_data["claim"]

    value = claim.get("value", {})

    return {
        "claim_id": claim.get("claim_id"),
        "name": claim.get("name"),
        "normalized_name": claim.get("normalized_name"),
        "permanent_url": claim.get("permanent_url"),
        "short_url": claim.get("short_url"),
        "canonical_url": claim.get("canonical_url"),
        "value_type": claim.get("value_type"),
        "title": value.get("title"),
        "description": value.get("description"),
        "thumbnail_url": extract_asset_url(value.get("thumbnail")),
        "cover_url": extract_asset_url(value.get("cover")),
        "website_url": value.get("website_url"),
        "email": value.get("email"),
        "tags": value.get("tags", []),
        "languages": value.get("languages", []),
        "links": extract_links(value),
    }


def extract_claim_metadata(claim_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract normalized metadata from a claim response.
    """
    # Handle different response formats
    if "claim" in claim_data:
        claim = claim_data["claim"]
    else:
        claim = claim_data

    value = claim.get("value", {})
    source = value.get("source", {})

    # Get fee info if present
    fee = None
    if "fee" in value:
        fee = value["fee"]

    # Determine file name from source
    file_name = source.get("name")

    # Get media type
    source_media_type = source.get("media_type")

    return {
        "claim_id": claim.get("claim_id"),
        "name": claim.get("name"),
        "normalized_name": claim.get("normalized_name"),
        "claim_type": claim.get("claim_type"),
        "value_type": claim.get("value_type"),
        "stream_type": value.get("stream_type"),
        "permanent_url": claim.get("permanent_url"),
        "short_url": claim.get("short_url"),
        "canonical_url": claim.get("canonical_url"),
        "timestamp": claim.get("timestamp"),
        "release_time": value.get("release_time"),
        "title": value.get("title"),
        "description": value.get("description"),
        "thumbnail_url": extract_asset_url(value.get("thumbnail")),
        "sd_hash": source.get("sd_hash"),
        "stream_hash": claim.get("stream_hash"),
        "txid": claim.get("txid"),
        "nout": claim.get("nout"),
        "tags": value.get("tags", []),
        "languages": value.get("languages", []),
        "links": extract_links(value),
        "fee": fee,
        "source_name": source.get("name"),
        "source_media_type": source_media_type,
        "file_name": file_name,
    }


def extract_asset_url(asset_data: Any) -> Optional[str]:
    """Extract a URL from a thumbnail/cover field when present."""
    if isinstance(asset_data, str):
        return asset_data
    if isinstance(asset_data, dict):
        for key in ("url", "uri", "src", "href"):
            value = asset_data.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def extract_links(value: Dict[str, Any]) -> list[Dict[str, str]]:
    """Extract any presentation links from a claim value."""
    links = []

    website_url = value.get("website_url")
    if isinstance(website_url, str) and website_url:
        links.append({"label": "Website", "url": website_url})

    for key in ("locations", "links"):
        raw_items = value.get(key)
        if isinstance(raw_items, dict):
            raw_items = [raw_items]
        if not isinstance(raw_items, list):
            continue

        for item in raw_items:
            if not isinstance(item, dict):
                continue
            url = None
            for field in ("url", "uri", "href"):
                candidate = item.get(field)
                if isinstance(candidate, str) and candidate:
                    url = candidate
                    break
            if not url:
                continue
            label = item.get("label") or item.get("title") or item.get("name") or _host_label(url)
            links.append({"label": str(label), "url": url})

    deduped = []
    seen = set()
    for link in links:
        key = (link["label"], link["url"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(link)
    return deduped


def _host_label(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc:
        return parsed.netloc
    return "Link"


def format_summary(
    channels_scanned: int,
    claims_examined: int,
    new_downloads: int,
    new_versions: int,
    skipped_existing: int,
    redownloaded_missing: int,
    failures: int,
) -> str:
    """Format a run summary string."""
    lines = [
        "Run complete.",
        f"Channels scanned: {channels_scanned}",
        f"Claims examined: {claims_examined}",
        f"New downloads: {new_downloads}",
        f"New versions: {new_versions}",
        f"Skipped existing: {skipped_existing}",
    ]

    if redownloaded_missing > 0:
        lines.append(f"Redownloaded missing: {redownloaded_missing}")

    lines.append(f"Failures: {failures}")

    return "\n".join(lines)
