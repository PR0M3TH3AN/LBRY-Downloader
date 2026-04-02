"""Planner module - decides what to download based on state."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from models import (
    Channel,
    Claim,
    ClaimVersion,
    Config,
    DownloadAction,
    StateDatabase,
)
from utils import (
    create_channel_folder_name,
    create_claim_folder_name,
    extract_claim_metadata,
    generate_version_token,
    is_downloadable_claim,
)


logger = logging.getLogger(__name__)


class Planner:
    """Plans download actions by comparing discovered claims with state."""

    def __init__(self, config: Config, state: StateDatabase, base_dir: str):
        self.config = config
        self.state = state
        self.base_dir = Path(base_dir)

    def process_channel_claims(
        self,
        channel: Channel,
        claims_data: List[Dict],
    ) -> List[DownloadAction]:
        """
        Process claims from a channel and decide what to do with each.

        Args:
            channel: The channel these claims belong to.
            claims_data: List of claim metadata from daemon.

        Returns:
            List of planned download actions.
        """
        actions = []

        for claim_data in claims_data:
            action = self._process_single_claim(channel, claim_data)
            if action:
                actions.append(action)

        return actions

    def _process_single_claim(
        self,
        channel: Channel,
        claim_data: Dict,
    ) -> Optional[DownloadAction]:
        """
        Process a single claim and decide what action to take.

        Args:
            channel: The channel this claim belongs to.
            claim_data: Claim metadata from daemon.

        Returns:
            DownloadAction or None if claim should be skipped.
        """
        # Handle wrapped response format
        if "claim" in claim_data:
            claim_value = claim_data["claim"]
        else:
            claim_value = claim_data

        # Check if this is a downloadable claim
        if not is_downloadable_claim(claim_value):
            logger.debug(f"Skipping non-downloadable claim")
            return None

        # Extract metadata
        try:
            metadata = extract_claim_metadata(claim_value)
        except Exception as e:
            logger.warning(f"Failed to extract metadata for claim: {e}")
            return None

        claim_id = metadata["claim_id"]
        claim_name = metadata["name"]

        # Skip reposts if not enabled
        value_type = claim_value.get("value_type", "").lower()
        if value_type == "repost" and not self.config.general.include_reposts:
            logger.debug(f"Skipping repost claim {claim_name}")
            return None

        # Generate version token
        version_token = generate_version_token(
            sd_hash=metadata.get("sd_hash"),
            stream_hash=metadata.get("stream_hash"),
            txid=metadata.get("txid"),
            nout=metadata.get("nout"),
            metadata=metadata,
        )

        # Build paths
        channel_folder = create_channel_folder_name(
            channel.channel_name, channel.channel_claim_id
        )
        claim_folder = create_claim_folder_name(claim_name, claim_id)

        # Use custom download path if provided, otherwise use base_dir
        if channel.download_path:
            download_base = Path(channel.download_path)
        else:
            download_base = self.base_dir / "channels"

        version_dir = (
            download_base
            / channel_folder
            / "claims"
            / claim_folder
            / "versions"
            / version_token
        )

        # Check state for this claim
        existing_claim = self.state.claims.get(claim_id)

        if existing_claim is None:
            # New claim
            action = DownloadAction(
                claim_id=claim_id,
                claim_name=claim_name,
                channel_claim_id=channel.channel_claim_id,
                version_token=version_token,
                action="download_new",
                uri=metadata["permanent_url"],
                target_dir=str(version_dir),
                metadata=metadata,
            )
            logger.info(f"New claim: {claim_name} ({action.action})")
            return action

        # Check if this is a new version
        if version_token in existing_claim.versions:
            # We know about this version
            version = existing_claim.versions[version_token]

            if version.downloaded:
                # Check if file still exists
                if self.config.general.verify_existing_files:
                    if version.file_relpath:
                        expected_path = self.base_dir / version.file_relpath
                        if not expected_path.exists():
                            # File is missing - need to redownload
                            action = DownloadAction(
                                claim_id=claim_id,
                                claim_name=claim_name,
                                channel_claim_id=channel.channel_claim_id,
                                version_token=version_token,
                                action="redownload_missing",
                                uri=metadata["permanent_url"],
                                target_dir=str(version_dir),
                                metadata=metadata,
                            )
                            logger.info(f"Redownload missing: {claim_name}")
                            return action

                # File exists - skip
                action = DownloadAction(
                    claim_id=claim_id,
                    claim_name=claim_name,
                    channel_claim_id=channel.channel_claim_id,
                    version_token=version_token,
                    action="skip_existing",
                    uri=metadata["permanent_url"],
                    target_dir=str(version_dir),
                    metadata=metadata,
                )
                if version.file_relpath:
                    action.metadata["existing_file_relpath"] = version.file_relpath
                logger.debug(f"Skipping existing: {claim_name}")
                return action
            else:
                # Version exists but not downloaded - download it
                action = DownloadAction(
                    claim_id=claim_id,
                    claim_name=claim_name,
                    channel_claim_id=channel.channel_claim_id,
                    version_token=version_token,
                    action="download_new_version",
                    uri=metadata["permanent_url"],
                    target_dir=str(version_dir),
                    metadata=metadata,
                )
                logger.info(f"Download incomplete: {claim_name}")
                return action
        else:
            # New version of existing claim
            action = DownloadAction(
                claim_id=claim_id,
                claim_name=claim_name,
                channel_claim_id=channel.channel_claim_id,
                version_token=version_token,
                action="download_new_version",
                uri=metadata["permanent_url"],
                target_dir=str(version_dir),
                metadata=metadata,
            )
            logger.info(f"New version: {claim_name}")
            return action

    def update_state_from_action(self, action: DownloadAction, success: bool) -> None:
        """
        Update the state database based on a completed action.

        Args:
            action: The action that was executed.
            success: Whether the action succeeded.
        """
        if not success:
            return

        now = datetime.now(timezone.utc).isoformat()

        # Get or create claim record
        claim = self.state.claims.get(action.claim_id)
        if claim is None:
            channel_folder = create_channel_folder_name(
                action.channel_claim_id[:20],  # We don't have channel name here
                action.channel_claim_id,
            )
            claim_folder = create_claim_folder_name(action.claim_name, action.claim_id)

            claim = Claim(
                claim_id=action.claim_id,
                channel_claim_id=action.channel_claim_id,
                name=action.claim_name,
                permanent_url=action.uri,
                claim_folder=f"channels/{channel_folder}/claims/{claim_folder}",
                first_seen=now,
                last_seen=now,
                versions={},
            )
            self.state.claims[action.claim_id] = claim

        # Update claim metadata
        claim.last_seen = now
        claim.latest_version_token = action.version_token

        # Get or create version record
        if action.version_token not in claim.versions:
            metadata = action.metadata
            claim.versions[action.version_token] = ClaimVersion(
                version_token=action.version_token,
                txid=metadata.get("txid", ""),
                nout=metadata.get("nout", 0),
                sd_hash=metadata.get("sd_hash"),
                stream_hash=metadata.get("stream_hash"),
                published_at=metadata.get("release_time"),
            )

        # Update version record
        version = claim.versions[action.version_token]
        if success:
            version.downloaded = True
            # File path will be set by downloader
