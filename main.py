#!/usr/bin/env python3
"""
LBRY Downloader - Incrementally sync LBRY/Odysee channel content.

This tool downloads all downloadable file claims from configured channels,
maintaining persistent state to avoid re-downloading unchanged content.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

from config_loader import ConfigError, ensure_directories, load_config
from downloader import DownloadError, Downloader
from lbry_client import LbryClient, LbryClientError, check_daemon_health
from models import Channel, Config, DownloadAction
from planner import Planner
from state_db import StateDb
from utils import (
    create_channel_folder_name,
    expand_path,
    format_summary,
    normalize_odysee_url,
)


def setup_logging(log_level: str) -> None:
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def resolve_channel(
    client: LbryClient,
    channel_input: str,
) -> Optional[Channel]:
    """
    Resolve a channel input to a Channel object.

    Args:
        client: Lbry client instance.
        channel_input: URL, URI, or claim ID.

    Returns:
        Resolved Channel or None if resolution failed.
    """
    logger = logging.getLogger(__name__)

    # Normalize input
    if channel_input.startswith("http"):
        uri = normalize_odysee_url(channel_input)
    elif not channel_input.startswith("lbry://"):
        uri = f"lbry://{channel_input}"
    else:
        uri = channel_input

    try:
        logger.debug(f"Resolving: {uri}")
        result = client.resolve([uri])

        if not result or uri not in result:
            logger.error(f"Could not resolve channel: {channel_input}")
            return None

        resolved = result[uri]

        # Check if it's a channel
        if "claim" in resolved:
            claim = resolved["claim"]
        else:
            claim = resolved

        value_type = claim.get("value_type", "").lower()
        if value_type != "channel":
            logger.error(f"Resolved claim is not a channel: {channel_input}")
            return None

        channel_claim_id = claim.get("claim_id")
        channel_name = claim.get("name")

        if not channel_claim_id:
            logger.error(f"No claim_id in resolved channel: {channel_input}")
            return None

        # Create folder name
        folder = create_channel_folder_name(channel_name, channel_claim_id)

        value = claim.get("value", {})

        channel = Channel(
            input=channel_input,
            normalized_uri=uri,
            channel_claim_id=channel_claim_id,
            channel_name=channel_name,
            folder=folder,
            display_name=value.get("title"),
            permanent_url=claim.get("permanent_url"),
            short_url=claim.get("short_url"),
        )

        logger.info(f"Resolved channel: {channel_name} ({channel_claim_id})")
        return channel

    except LbryClientError as e:
        logger.error(f"Failed to resolve channel {channel_input}: {e}")
        return None


def enumerate_channel_claims(
    client: LbryClient,
    channel: Channel,
    config: Config,
) -> List[dict]:
    """
    Enumerate all downloadable claims from a channel.

    Args:
        client: Lbry client.
        channel: Channel to enumerate.
        config: Application config.

    Returns:
        List of claim metadata.
    """
    logger = logging.getLogger(__name__)
    all_claims = []
    page = 1

    logger.info(f"Scanning channel: {channel.channel_name}")

    while True:
        try:
            result = client.get_channel_claims(
                channel_claim_id=channel.channel_claim_id,
                page=page,
                page_size=config.general.channel_page_size,
                include_reposts=config.general.include_reposts,
            )

            items = result.get("items", [])
            if not items:
                break

            all_claims.extend(items)
            logger.debug(f"  Page {page}: {len(items)} claims")

            # Check if we've reached the end
            total_pages = result.get("total_pages", 1)
            if page >= total_pages:
                break

            page += 1

        except LbryClientError as e:
            logger.error(f"Failed to enumerate page {page}: {e}")
            break

    logger.info(f"  Total claims found: {len(all_claims)}")
    return all_claims


def run_sync(config: Config, dry_run: bool = False, direct: bool = False) -> dict:
    """
    Run the main synchronization process.

    Args:
        config: Application configuration.
        dry_run: If True, don't actually download.
        direct: If True, use Odysee CDN instead of P2P.

    Returns:
        Statistics dictionary.
    """
    logger = logging.getLogger(__name__)
    stats = {
        "channels_scanned": 0,
        "claims_examined": 0,
        "new_downloads": 0,
        "new_versions": 0,
        "skipped_existing": 0,
        "redownloaded_missing": 0,
        "failures": 0,
    }

    # Load state
    state_db = StateDb(config.general.state_file)
    state_db.load()

    # Initialize planner and downloader
    base_path = Path(config.general.base_dir)
    planner = Planner(config, state_db.data, str(base_path))

    # Initialize LBRY client (needed for channel/claim resolution in both modes)
    client = LbryClient(
        api_url=config.lbrynet.api_url,
        timeout=config.lbrynet.timeout_seconds,
    )

    # Check daemon health (needed for metadata even in direct mode)
    logger.info(f"Checking daemon at {config.lbrynet.api_url}")
    try:
        check_daemon_health(client)
        logger.info("Daemon is healthy")
    except LbryClientError as e:
        logger.error(str(e))
        logger.error(
            "Daemon is required for channel/claim resolution even in --direct mode"
        )
        return stats

    if direct:
        logger.info("Using DIRECT mode (Odysee CDN for downloads)")
        from direct_downloader import DirectDownloader

        downloader = DirectDownloader(config, base_path)
    else:
        logger.info("Using P2P mode (LBRY network)")
        downloader = Downloader(client, config, base_path)

    # Process each enabled channel
    enabled_channels = [c for c in config.channels if c.enabled]

    for channel_config in enabled_channels:
        stats["channels_scanned"] += 1

        # Resolve channel
        channel = resolve_channel(client, channel_config.input)
        if not channel:
            stats["failures"] += 1
            continue

        # Set custom download path if provided in config
        if channel_config.download_path:
            channel.download_path = channel_config.download_path

        # Check if we already have this channel in state
        existing = state_db.get_channel(channel.channel_claim_id)
        if existing:
            # Update with new info but keep folder and download_path
            channel.folder = existing.folder
            if existing.download_path:
                channel.download_path = existing.download_path

        # Enumerate claims
        claims = enumerate_channel_claims(client, channel, config)

        # Plan downloads
        actions = planner.process_channel_claims(channel, claims)

        # Apply download limit if configured
        # Separate skip actions from download actions
        skip_actions = [a for a in actions if a.action == "skip_existing"]
        download_actions = [a for a in actions if a.action != "skip_existing"]

        # Sort download actions by release_time (most recent first)
        # Claims without release_time will be at the end
        download_actions.sort(
            key=lambda a: a.metadata.get("release_time") or 0, reverse=True
        )

        # Apply limit: 0 means "all" (no limit), otherwise limit to download_limit
        if (
            config.general.download_limit > 0
            and len(download_actions) > config.general.download_limit
        ):
            skipped_due_to_limit = download_actions[config.general.download_limit :]
            download_actions = download_actions[: config.general.download_limit]

            logger.info(
                f"Download limit ({config.general.download_limit}) reached. "
                f"Skipping {len(skipped_due_to_limit)} older items."
            )

            # Mark skipped items in stats
            for action in skipped_due_to_limit:
                stats["skipped_existing"] += 1

        # Recombine actions
        actions = skip_actions + download_actions
        stats["claims_examined"] += len(actions)

        # Execute downloads
        for action in actions:
            if action.action == "skip_existing":
                stats["skipped_existing"] += 1
            elif action.action == "redownload_missing":
                stats["redownloaded_missing"] += 1
            elif action.action in ("download_new", "download_new_version"):
                if action.action == "download_new":
                    stats["new_downloads"] += 1
                else:
                    stats["new_versions"] += 1

            try:
                success = downloader.download(action, dry_run=dry_run)

                if success and not dry_run and action.action not in ("skip_existing",):
                    # Update state
                    planner.update_state_from_action(action, success=True)

                    # Log to history
                    history_file = base_path / "state" / "run-history.jsonl"
                    state_db.log_run_history(
                        str(history_file),
                        channel.channel_claim_id,
                        action.claim_id,
                        action.action,
                        action.version_token,
                        "success" if success else "failure",
                    )

            except DownloadError as e:
                logger.error(f"Download failed: {e}")
                stats["failures"] += 1

                # Log failure
                history_file = base_path / "state" / "run-history.jsonl"
                state_db.log_run_history(
                    str(history_file),
                    channel.channel_claim_id,
                    action.claim_id,
                    action.action,
                    action.version_token,
                    "failure",
                    str(e),
                )

        # Update channel last scan time
        from datetime import datetime, timezone

        channel.last_scan = datetime.now(timezone.utc).isoformat()
        state_db.set_channel(channel)

    # Save state
    if not dry_run:
        state_db.update_last_run()
        state_db.save()
        logger.info("State saved")

    return stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="LBRY/Odysee Channel Downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Run with default config (P2P mode)
  python main.py --config ./config.yaml  # Use custom config
  python main.py --dry-run          # Plan actions but don't download
  python main.py --direct           # Download from Odysee CDN (more reliable)
        """,
    )

    parser.add_argument(
        "--config",
        "-c",
        help="Path to configuration file (default: ~/Documents/lbry-downloads/config.yaml)",
    )

    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be downloaded without actually downloading",
    )

    parser.add_argument(
        "--direct",
        "-d",
        action="store_true",
        help="Download directly from Odysee CDN instead of using P2P network",
    )

    args = parser.parse_args()

    try:
        # Load config
        config = load_config(args.config)

        # Setup logging
        setup_logging(config.general.log_level)
        logger = logging.getLogger(__name__)

        logger.info("LBRY Downloader starting")

        # Ensure directories exist
        ensure_directories(config)

        # Run sync
        stats = run_sync(config, dry_run=args.dry_run, direct=args.direct)

        # Print summary
        summary = format_summary(
            channels_scanned=stats["channels_scanned"],
            claims_examined=stats["claims_examined"],
            new_downloads=stats["new_downloads"],
            new_versions=stats["new_versions"],
            skipped_existing=stats["skipped_existing"],
            redownloaded_missing=stats["redownloaded_missing"],
            failures=stats["failures"],
        )
        print("\n" + summary)

        # Exit with error code if there were failures
        if stats["failures"] > 0:
            sys.exit(1)

    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
