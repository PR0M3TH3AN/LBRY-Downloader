"""Tests for planner module."""

import pytest
from pathlib import Path
import tempfile
import shutil

from planner import Planner
from models import Channel, Config, GeneralConfig, StateDatabase, Claim, ClaimVersion
from utils import create_channel_folder_name, create_claim_folder_name


class TestPlanner:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = Config()
        self.config.general = GeneralConfig()
        self.config.general.verify_existing_files = True
        self.state = StateDatabase()
        self.planner = Planner(self.config, self.state, self.temp_dir)

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_new_claim_action(self):
        channel = Channel(
            input="test",
            normalized_uri="lbry://@Test#1",
            channel_claim_id="channel123",
            channel_name="@Test",
            folder="Test__channel123",
        )

        claim_data = {
            "claim_id": "claim456",
            "name": "my-video",
            "value_type": "stream",
            "value": {"source": {"sd_hash": "abc123"}, "title": "My Video"},
            "permanent_url": "lbry://@Test#1/my-video#claim456",
            "txid": "tx789",
            "nout": 0,
        }

        actions = self.planner.process_channel_claims(channel, [claim_data])

        assert len(actions) == 1
        assert actions[0].action == "download_new"
        assert actions[0].claim_id == "claim456"

    def test_skip_existing_claim(self):
        channel = Channel(
            input="test",
            normalized_uri="lbry://@Test#1",
            channel_claim_id="channel123",
            channel_name="@Test",
            folder="Test__channel123",
        )

        # Add existing claim to state
        claim_folder = create_claim_folder_name("my-video", "claim456")
        claim = Claim(
            claim_id="claim456",
            channel_claim_id="channel123",
            name="my-video",
            permanent_url="lbry://@Test#1/my-video#claim456",
            claim_folder=f"channels/Test__channel123/claims/{claim_folder}",
        )

        # Create version token matching the claim data
        from utils import generate_version_token

        version_token = generate_version_token(sd_hash="abc123")

        claim.versions[version_token] = ClaimVersion(
            version_token=version_token,
            txid="tx789",
            nout=0,
            sd_hash="abc123",
            downloaded=True,
            file_relpath=f"channels/Test__channel123/claims/{claim_folder}/versions/{version_token}/video.mp4",
        )

        self.state.claims["claim456"] = claim

        # Create the "downloaded" file
        version_dir = (
            Path(self.temp_dir)
            / f"channels/Test__channel123/claims/{claim_folder}/versions/{version_token}"
        )
        version_dir.mkdir(parents=True)
        (version_dir / "video.mp4").touch()

        claim_data = {
            "claim_id": "claim456",
            "name": "my-video",
            "value_type": "stream",
            "value": {"source": {"sd_hash": "abc123"}, "title": "My Video"},
            "permanent_url": "lbry://@Test#1/my-video#claim456",
            "txid": "tx789",
            "nout": 0,
        }

        actions = self.planner.process_channel_claims(channel, [claim_data])

        assert len(actions) == 1
        assert actions[0].action == "skip_existing"
        assert (
            actions[0].metadata["existing_file_relpath"]
            == f"channels/Test__channel123/claims/{claim_folder}/versions/{version_token}/video.mp4"
        )

    def test_new_version_detected(self):
        channel = Channel(
            input="test",
            normalized_uri="lbry://@Test#1",
            channel_claim_id="channel123",
            channel_name="@Test",
            folder="Test__channel123",
        )

        # Add existing claim with old version
        claim_folder = create_claim_folder_name("my-video", "claim456")
        claim = Claim(
            claim_id="claim456",
            channel_claim_id="channel123",
            name="my-video",
            permanent_url="lbry://@Test#1/my-video#claim456",
            claim_folder=f"channels/Test__channel123/claims/{claim_folder}",
        )

        old_version_token = "sd_oldhash123"
        claim.versions[old_version_token] = ClaimVersion(
            version_token=old_version_token,
            txid="tx789",
            nout=0,
            sd_hash="oldhash123",
            downloaded=True,
        )

        self.state.claims["claim456"] = claim

        # New claim data with different sd_hash
        claim_data = {
            "claim_id": "claim456",
            "name": "my-video",
            "value_type": "stream",
            "value": {
                "source": {"sd_hash": "newhash456"},  # Different!
                "title": "My Video Updated",
            },
            "permanent_url": "lbry://@Test#1/my-video#claim456",
            "txid": "tx999",
            "nout": 0,
        }

        actions = self.planner.process_channel_claims(channel, [claim_data])

        assert len(actions) == 1
        assert actions[0].action == "download_new_version"

    def test_non_downloadable_claim_skipped(self):
        channel = Channel(
            input="test",
            normalized_uri="lbry://@Test#1",
            channel_claim_id="channel123",
            channel_name="@Test",
            folder="Test__channel123",
        )

        # Channel type claim (not downloadable)
        claim_data = {
            "claim_id": "claim456",
            "name": "@SomeChannel",
            "value_type": "channel",
            "value": {},
            "permanent_url": "lbry://@SomeChannel#claim456",
        }

        actions = self.planner.process_channel_claims(channel, [claim_data])

        assert len(actions) == 0

    def test_custom_download_path(self):
        """Test that custom download_path is used for channel."""
        custom_path = "/custom/download/location"
        channel = Channel(
            input="test",
            normalized_uri="lbry://@Test#1",
            channel_claim_id="channel123",
            channel_name="@Test",
            folder="Test__channel123",
            download_path=custom_path,
        )

        claim_data = {
            "claim_id": "claim456",
            "name": "my-video",
            "value_type": "stream",
            "value": {"source": {"sd_hash": "abc123"}, "title": "My Video"},
            "permanent_url": "lbry://@Test#1/my-video#claim456",
            "txid": "tx789",
            "nout": 0,
        }

        actions = self.planner.process_channel_claims(channel, [claim_data])

        assert len(actions) == 1
        assert actions[0].action == "download_new"
        # Check that target_dir uses custom path
        assert custom_path in actions[0].target_dir
        assert "Test__channel123" in actions[0].target_dir


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
