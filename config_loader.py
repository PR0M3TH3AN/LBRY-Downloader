"""Configuration loading and validation."""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install PyYAML")
    sys.exit(1)

from models import Config, ChannelConfig, GeneralConfig, LbrynetConfig
from utils import expand_path


class ConfigError(Exception):
    """Raised when configuration is invalid."""

    pass


VALID_CONTENT_MODES = {"all", "video_only", "non_video_only"}


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load and validate the configuration file.

    Args:
        config_path: Path to config file. If None, uses default location.

    Returns:
        Validated Config object.

    Raises:
        ConfigError: If config is missing, invalid, or has errors.
    """
    if config_path is None:
        config_path = "~/Documents/lbry-downloads/config.yaml"

    config_file = expand_path(config_path)

    if not config_file.exists():
        raise ConfigError(
            f"Config file not found: {config_file}\n"
            f"Create one at this location or specify a different path with --config"
        )

    try:
        with open(config_file, "r") as f:
            raw_config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse YAML config: {e}")
    except Exception as e:
        raise ConfigError(f"Failed to read config file: {e}")

    if raw_config is None:
        raw_config = {}

    return _parse_config(raw_config)


def _parse_config(raw: Dict[str, Any]) -> Config:
    """Parse raw config dict into Config object."""
    config = Config()

    # Parse lbrynet section
    if "lbrynet" in raw:
        lbrynet_raw = raw["lbrynet"]
        config.lbrynet = LbrynetConfig(
            api_url=lbrynet_raw.get("api_url", config.lbrynet.api_url),
            timeout_seconds=lbrynet_raw.get(
                "timeout_seconds", config.lbrynet.timeout_seconds
            ),
        )

    # Parse general section
    if "general" in raw:
        general_raw = raw["general"]
        config.general = GeneralConfig(
            base_dir=general_raw.get("base_dir", config.general.base_dir),
            state_file=general_raw.get("state_file", config.general.state_file),
            max_workers=general_raw.get("max_workers", config.general.max_workers),
            log_level=general_raw.get("log_level", config.general.log_level),
            dry_run=general_raw.get("dry_run", config.general.dry_run),
            verify_existing_files=general_raw.get(
                "verify_existing_files", config.general.verify_existing_files
            ),
            write_checksums=general_raw.get(
                "write_checksums", config.general.write_checksums
            ),
            filename_mode=general_raw.get(
                "filename_mode", config.general.filename_mode
            ),
            include_reposts=general_raw.get(
                "include_reposts", config.general.include_reposts
            ),
            channel_page_size=general_raw.get(
                "channel_page_size", config.general.channel_page_size
            ),
            keep_missing_claim_records=general_raw.get(
                "keep_missing_claim_records", config.general.keep_missing_claim_records
            ),
            download_limit=general_raw.get(
                "download_limit", config.general.download_limit
            ),
            direct_base_urls=general_raw.get(
                "direct_base_urls", config.general.direct_base_urls
            ),
            direct_max_retries_per_url=general_raw.get(
                "direct_max_retries_per_url",
                config.general.direct_max_retries_per_url,
            ),
            direct_retry_backoff_seconds=general_raw.get(
                "direct_retry_backoff_seconds",
                config.general.direct_retry_backoff_seconds,
            ),
            direct_auto_fallback_to_p2p=general_raw.get(
                "direct_auto_fallback_to_p2p",
                config.general.direct_auto_fallback_to_p2p,
            ),
            build_offline_site=general_raw.get(
                "build_offline_site", config.general.build_offline_site
            ),
            offline_site_dir=general_raw.get(
                "offline_site_dir", config.general.offline_site_dir
            ),
            fetch_missing_metadata_assets=general_raw.get(
                "fetch_missing_metadata_assets",
                config.general.fetch_missing_metadata_assets,
            ),
        )

    # Validate and expand paths
    config.general.base_dir = str(expand_path(config.general.base_dir))
    config.general.state_file = str(expand_path(config.general.state_file))
    if config.general.offline_site_dir:
        config.general.offline_site_dir = str(expand_path(config.general.offline_site_dir))
    else:
        config.general.offline_site_dir = str(
            expand_path(f"{config.general.base_dir}/site")
        )

    # Validate max_workers
    if config.general.max_workers < 1:
        raise ConfigError("max_workers must be at least 1")
    if config.general.max_workers > 10:
        # Warn but don't fail - user might know what they're doing
        print(
            f"Warning: max_workers is set to {config.general.max_workers}, which is high"
        )

    # Validate download_limit
    # 0 means "all" (no limit), negative values are not allowed
    if config.general.download_limit < 0:
        raise ConfigError("download_limit must be 0 (for all) or a positive number")
    if config.general.direct_max_retries_per_url < 0:
        raise ConfigError("direct_max_retries_per_url must be 0 or a positive number")
    if config.general.direct_retry_backoff_seconds <= 0:
        raise ConfigError("direct_retry_backoff_seconds must be greater than 0")
    if not isinstance(config.general.direct_base_urls, list):
        raise ConfigError("direct_base_urls must be a list")
    if not config.general.direct_base_urls:
        raise ConfigError("direct_base_urls must contain at least one base URL")
    normalized_direct_base_urls = []
    for idx, base_url in enumerate(config.general.direct_base_urls, start=1):
        if not isinstance(base_url, str) or not base_url.strip():
            raise ConfigError(
                f"direct_base_urls entry {idx} must be a non-empty string"
            )
        normalized_direct_base_urls.append(base_url.rstrip("/"))
    config.general.direct_base_urls = normalized_direct_base_urls

    # Validate log_level
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if config.general.log_level.upper() not in valid_levels:
        raise ConfigError(f"log_level must be one of: {', '.join(valid_levels)}")
    config.general.log_level = config.general.log_level.upper()

    # Validate filename_mode
    valid_modes = ["original", "safe"]
    if config.general.filename_mode not in valid_modes:
        raise ConfigError(f"filename_mode must be one of: {', '.join(valid_modes)}")

    # Parse channels section
    if "channels" not in raw or not raw["channels"]:
        raise ConfigError("Config must contain at least one channel in 'channels' list")

    channels_raw = raw["channels"]
    if not isinstance(channels_raw, list):
        raise ConfigError("'channels' must be a list")

    config.channels = _parse_channels(channels_raw)

    # Check that at least one channel is enabled
    enabled_channels = [c for c in config.channels if c.enabled]
    if not enabled_channels:
        raise ConfigError("At least one channel must be enabled")

    return config


def _parse_channels(channels_raw: List[Dict[str, Any]]) -> List[ChannelConfig]:
    """Parse channel configurations."""
    channels = []

    for i, channel_raw in enumerate(channels_raw):
        if not isinstance(channel_raw, dict):
            raise ConfigError(f"Channel {i + 1} must be a dictionary")

        if "input" not in channel_raw:
            raise ConfigError(f"Channel {i + 1} is missing required 'input' field")

        input_val = channel_raw["input"]
        if not input_val or not isinstance(input_val, str):
            raise ConfigError(f"Channel {i + 1} has invalid 'input' value")

        # Parse download_path if provided
        download_path = channel_raw.get("download_path")
        if download_path:
            download_path = str(expand_path(download_path))

        channel = ChannelConfig(
            input=input_val,
            enabled=channel_raw.get("enabled", True),
            download_path=download_path,
            content_mode=channel_raw.get("content_mode", "all"),
            tags_include=channel_raw.get("tags_include", []),
            tags_exclude=channel_raw.get("tags_exclude", []),
        )

        if channel.content_mode not in VALID_CONTENT_MODES:
            raise ConfigError(
                f"Channel {i + 1} has invalid content_mode "
                f"'{channel.content_mode}'. Must be one of: "
                f"{', '.join(sorted(VALID_CONTENT_MODES))}"
            )

        channels.append(channel)

    return channels


def create_default_config() -> str:
    """Generate a default configuration file content."""
    return """# LBRY Downloader Configuration
# Place this file at ~/Documents/lbry-downloads/config.yaml

lbrynet:
  # URL of the local LBRY daemon (lbrynet)
  # Only used when running with --p2p
  api_url: "http://127.0.0.1:5279"
  # Timeout for daemon requests in seconds
  # Only used when running with --p2p
  timeout_seconds: 60

general:
  # Base directory for all downloads and state
  base_dir: "~/Documents/lbry-downloads"
  # Path to the state database
  state_file: "~/Documents/lbry-downloads/state/database.json"
  # Number of concurrent downloads
  max_workers: 2
  # Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
  log_level: "INFO"
  # If true, show what would be downloaded without actually downloading
  dry_run: false
  # Verify that previously downloaded files still exist
  verify_existing_files: true
  # Write SHA256 checksums for downloaded files
  write_checksums: true
  # Filename handling: 'original' or 'safe'
  filename_mode: "original"
  # Include reposts in downloads
  include_reposts: false
  # Number of claims to fetch per page
  channel_page_size: 50
  # Keep records of claims even if they disappear from the channel
  keep_missing_claim_records: true
  # Direct download bases to try in order
  direct_base_urls:
    - "https://odysee.com"
  # Retries per direct URL after HTTP 429
  direct_max_retries_per_url: 2
  # Base backoff in seconds after HTTP 429 (uses exponential backoff)
  direct_retry_backoff_seconds: 2.0
  # If true, direct-mode runs will try the local node after repeated 429s
  direct_auto_fallback_to_p2p: false
  # Build a static offline browseable site from the archive after each run
  build_offline_site: true
  # Where to write the generated offline site
  offline_site_dir: "~/Documents/lbry-downloads/site"
  # Fetch missing channel/claim images and metadata assets on reruns
  fetch_missing_metadata_assets: true
  # Download limit: Number of most recent matching downloads per channel (0 = all)
  download_limit: 10

channels:
  # Add your channels here. Examples:
  # - input: "https://odysee.com/@SomeChannel:1"
  #   enabled: true
  #   content_mode: "non_video_only"
  #   tags_include: []
  #   tags_exclude: []
  # - input: "lbry://@AnotherChannel#5"
  #   enabled: true
  #   content_mode: "all"
"""


def ensure_directories(config: Config) -> None:
    """
    Create necessary base directories if they don't exist.

    Args:
        config: Validated configuration object.
    """
    base_path = Path(config.general.base_dir)
    base_path.mkdir(parents=True, exist_ok=True)

    # Create state directory
    state_path = base_path / "state"
    state_path.mkdir(exist_ok=True)

    # Create channels directory
    channels_path = base_path / "channels"
    channels_path.mkdir(exist_ok=True)

    if config.general.build_offline_site:
        Path(config.general.offline_site_dir).mkdir(parents=True, exist_ok=True)
