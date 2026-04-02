"""Data models for LBRY Downloader."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ChannelConfig:
    """Configuration for a channel to sync."""

    input: str
    enabled: bool = True
    download_path: Optional[str] = None
    content_mode: str = "all"
    tags_include: List[str] = field(default_factory=list)
    tags_exclude: List[str] = field(default_factory=list)


@dataclass
class GeneralConfig:
    """General application configuration."""

    base_dir: str = "~/Documents/lbry-downloads"
    state_file: str = "~/Documents/lbry-downloads/state/database.json"
    max_workers: int = 2
    log_level: str = "INFO"
    dry_run: bool = False
    verify_existing_files: bool = True
    write_checksums: bool = True
    filename_mode: str = "original"
    include_reposts: bool = False
    channel_page_size: int = 50
    keep_missing_claim_records: bool = True
    download_limit: int = (
        10  # Number of most recent downloads per channel, or "all" (0)
    )
    direct_base_urls: List[str] = field(
        default_factory=lambda: ["https://odysee.com"]
    )
    direct_max_retries_per_url: int = 2
    direct_retry_backoff_seconds: float = 2.0
    direct_auto_fallback_to_p2p: bool = False


@dataclass
class LbrynetConfig:
    """LBRY daemon configuration."""

    api_url: str = "http://127.0.0.1:5279"
    timeout_seconds: int = 60


@dataclass
class Config:
    """Complete application configuration."""

    lbrynet: LbrynetConfig = field(default_factory=LbrynetConfig)
    general: GeneralConfig = field(default_factory=GeneralConfig)
    channels: List[ChannelConfig] = field(default_factory=list)


@dataclass
class Channel:
    """A resolved LBRY channel."""

    input: str
    normalized_uri: str
    channel_claim_id: str
    channel_name: str
    folder: str
    download_path: Optional[str] = None
    display_name: Optional[str] = None
    permanent_url: Optional[str] = None
    short_url: Optional[str] = None
    last_scan: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input": self.input,
            "normalized_uri": self.normalized_uri,
            "channel_claim_id": self.channel_claim_id,
            "channel_name": self.channel_name,
            "folder": self.folder,
            "download_path": self.download_path,
            "display_name": self.display_name,
            "permanent_url": self.permanent_url,
            "short_url": self.short_url,
            "last_scan": self.last_scan,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Channel":
        return cls(
            input=data["input"],
            normalized_uri=data["normalized_uri"],
            channel_claim_id=data["channel_claim_id"],
            channel_name=data["channel_name"],
            folder=data["folder"],
            download_path=data.get("download_path"),
            display_name=data.get("display_name"),
            permanent_url=data.get("permanent_url"),
            short_url=data.get("short_url"),
            last_scan=data.get("last_scan"),
        )


@dataclass
class ClaimVersion:
    """A specific version of a claim."""

    version_token: str
    txid: str
    nout: int
    sd_hash: Optional[str] = None
    stream_hash: Optional[str] = None
    published_at: Optional[str] = None
    downloaded: bool = False
    file_relpath: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_token": self.version_token,
            "txid": self.txid,
            "nout": self.nout,
            "sd_hash": self.sd_hash,
            "stream_hash": self.stream_hash,
            "published_at": self.published_at,
            "downloaded": self.downloaded,
            "file_relpath": self.file_relpath,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClaimVersion":
        return cls(
            version_token=data["version_token"],
            txid=data["txid"],
            nout=data["nout"],
            sd_hash=data.get("sd_hash"),
            stream_hash=data.get("stream_hash"),
            published_at=data.get("published_at"),
            downloaded=data.get("downloaded", False),
            file_relpath=data.get("file_relpath"),
        )


@dataclass
class Claim:
    """A LBRY claim (downloadable content)."""

    claim_id: str
    channel_claim_id: str
    name: str
    permanent_url: str
    claim_folder: str
    title: Optional[str] = None
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    latest_version_token: Optional[str] = None
    versions: Dict[str, ClaimVersion] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "channel_claim_id": self.channel_claim_id,
            "name": self.name,
            "title": self.title,
            "permanent_url": self.permanent_url,
            "claim_folder": self.claim_folder,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "latest_version_token": self.latest_version_token,
            "versions": {k: v.to_dict() for k, v in self.versions.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Claim":
        versions = {
            k: ClaimVersion.from_dict(v) for k, v in data.get("versions", {}).items()
        }
        return cls(
            claim_id=data["claim_id"],
            channel_claim_id=data["channel_claim_id"],
            name=data["name"],
            title=data.get("title"),
            permanent_url=data["permanent_url"],
            claim_folder=data["claim_folder"],
            first_seen=data.get("first_seen"),
            last_seen=data.get("last_seen"),
            latest_version_token=data.get("latest_version_token"),
            versions=versions,
        )


@dataclass
class DownloadAction:
    """Represents a planned download action."""

    claim_id: str
    claim_name: str
    channel_claim_id: str
    version_token: str
    action: str  # 'download_new', 'download_new_version', 'redownload_missing', 'skip_existing'
    uri: str
    target_dir: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StateDatabase:
    """In-memory representation of the state database."""

    schema_version: int = 1
    channels: Dict[str, Channel] = field(default_factory=dict)
    claims: Dict[str, Claim] = field(default_factory=dict)
    downloads: Dict[str, Any] = field(default_factory=dict)
    last_run: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "channels": {k: v.to_dict() for k, v in self.channels.items()},
            "claims": {k: v.to_dict() for k, v in self.claims.items()},
            "downloads": self.downloads,
            "last_run": self.last_run,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateDatabase":
        channels = {
            k: Channel.from_dict(v) for k, v in data.get("channels", {}).items()
        }
        claims = {k: Claim.from_dict(v) for k, v in data.get("claims", {}).items()}
        return cls(
            schema_version=data.get("schema_version", 1),
            channels=channels,
            claims=claims,
            downloads=data.get("downloads", {}),
            last_run=data.get("last_run"),
        )


@dataclass
class NormalizedMetadata:
    """Normalized claim metadata for storage."""

    claim_id: str
    channel_claim_id: str
    name: str
    title: Optional[str]
    claim_type: str
    value_type: str
    version_token: str
    sd_hash: Optional[str]
    stream_hash: Optional[str]
    txid: str
    nout: int
    permanent_url: str
    short_url: Optional[str]
    canonical_url: Optional[str]
    timestamp: int
    release_time: Optional[int]
    fee: Optional[Dict]
    tags: List[str]
    languages: List[str]
    source_name: Optional[str]
    source_media_type: Optional[str]
    file_name: Optional[str]
    download_path: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "channel_claim_id": self.channel_claim_id,
            "name": self.name,
            "title": self.title,
            "claim_type": self.claim_type,
            "value_type": self.value_type,
            "version_token": self.version_token,
            "sd_hash": self.sd_hash,
            "stream_hash": self.stream_hash,
            "txid": self.txid,
            "nout": self.nout,
            "permanent_url": self.permanent_url,
            "short_url": self.short_url,
            "canonical_url": self.canonical_url,
            "timestamp": self.timestamp,
            "release_time": self.release_time,
            "fee": self.fee,
            "tags": self.tags,
            "languages": self.languages,
            "source_name": self.source_name,
            "source_media_type": self.source_media_type,
            "file_name": self.file_name,
            "download_path": self.download_path,
        }
