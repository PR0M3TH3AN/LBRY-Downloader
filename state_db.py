"""State database management with atomic writes."""

import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from models import StateDatabase, Channel, Claim


logger = logging.getLogger(__name__)


class StateDbError(Exception):
    """Raised when state database operations fail."""

    pass


class StateDb:
    """Manages the persistent state database."""

    def __init__(self, state_file: str):
        """
        Initialize state database.

        Args:
            state_file: Path to the state database JSON file.
        """
        self.state_file = Path(state_file)
        self.data = StateDatabase()
        self._loaded = False

    def load(self) -> StateDatabase:
        """
        Load state from disk or initialize new state.

        Returns:
            Loaded StateDatabase instance.
        """
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    raw_data = json.load(f)

                self.data = StateDatabase.from_dict(raw_data)
                self._loaded = True
                logger.debug(f"Loaded state from {self.state_file}")

                # Validate schema version
                if self.data.schema_version != 1:
                    logger.warning(
                        f"State database schema version is {self.data.schema_version}, "
                        f"expected 1. You may need to migrate."
                    )

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse state database: {e}")
                raise StateDbError(f"State database is corrupted: {e}")
            except Exception as e:
                logger.error(f"Failed to load state database: {e}")
                raise StateDbError(f"Failed to load state database: {e}")
        else:
            # Initialize new state
            self.data = StateDatabase()
            self._loaded = True
            logger.debug(f"Initialized new state database at {self.state_file}")

        return self.data

    def save(self) -> None:
        """
        Save state to disk atomically.

        Writes to a temporary file first, then renames to ensure
        the database is never in a partially written state.
        """
        if not self._loaded:
            raise StateDbError("Cannot save state before loading")

        # Ensure parent directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Write to temporary file
        temp_file = self.state_file.with_suffix(".tmp")

        try:
            with open(temp_file, "w") as f:
                json.dump(self.data.to_dict(), f, indent=2, default=str)
                f.flush()
                os.fsync(f.fileno())

            # Atomic rename
            shutil.move(str(temp_file), str(self.state_file))

            logger.debug(f"Saved state to {self.state_file}")

        except Exception as e:
            # Clean up temp file on failure
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass
            raise StateDbError(f"Failed to save state database: {e}")

    def get_channel(self, channel_claim_id: str) -> Optional[Channel]:
        """Get a channel by its claim ID."""
        return self.data.channels.get(channel_claim_id)

    def set_channel(self, channel: Channel) -> None:
        """Store or update a channel record."""
        self.data.channels[channel.channel_claim_id] = channel

    def get_claim(self, claim_id: str) -> Optional[Claim]:
        """Get a claim by its claim ID."""
        return self.data.claims.get(claim_id)

    def set_claim(self, claim: Claim) -> None:
        """Store or update a claim record."""
        self.data.claims[claim.claim_id] = claim

    def update_last_run(self) -> None:
        """Update the last run timestamp."""
        self.data.last_run = datetime.now(timezone.utc).isoformat()

    def log_run_history(
        self,
        run_history_file: str,
        channel_claim_id: str,
        claim_id: str,
        action: str,
        version_token: str,
        status: str,
        message: Optional[str] = None,
    ) -> None:
        """
        Append an entry to the run history log.

        Args:
            run_history_file: Path to the run history JSONL file.
            channel_claim_id: Channel claim ID.
            claim_id: Claim ID.
            action: Action taken (e.g., 'download_new', 'skip_existing').
            version_token: Version token.
            status: Status (e.g., 'success', 'failure').
            message: Optional message.
        """
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "channel_claim_id": channel_claim_id,
            "claim_id": claim_id,
            "action": action,
            "version_token": version_token,
            "status": status,
        }

        if message:
            entry["message"] = message

        history_path = Path(run_history_file)
        history_path.parent.mkdir(parents=True, exist_ok=True)

        with open(history_path, "a") as f:
            json.dump(entry, f)
            f.write("\n")

    def get_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        total_versions = sum(len(claim.versions) for claim in self.data.claims.values())
        downloaded_versions = sum(
            1
            for claim in self.data.claims.values()
            for version in claim.versions.values()
            if version.downloaded
        )

        return {
            "channels": len(self.data.channels),
            "claims": len(self.data.claims),
            "total_versions": total_versions,
            "downloaded_versions": downloaded_versions,
        }
