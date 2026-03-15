"""Tests for state database."""

import json
import pytest
from pathlib import Path
import tempfile
import shutil

from state_db import StateDb
from models import Channel, Claim, ClaimVersion


class TestStateDb:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = Path(self.temp_dir) / "test_state.json"

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_new_database(self):
        db = StateDb(str(self.state_file))
        state = db.load()

        assert state.schema_version == 1
        assert state.channels == {}
        assert state.claims == {}

    def test_save_and_load(self):
        db = StateDb(str(self.state_file))
        db.load()

        # Add a channel
        channel = Channel(
            input="https://odysee.com/@Test:1",
            normalized_uri="lbry://@Test#1",
            channel_claim_id="abc123",
            channel_name="@Test",
            folder="Test__abc123",
        )
        db.set_channel(channel)
        db.save()

        # Load fresh
        db2 = StateDb(str(self.state_file))
        state = db2.load()

        assert "abc123" in state.channels
        assert state.channels["abc123"].channel_name == "@Test"

    def test_channel_operations(self):
        db = StateDb(str(self.state_file))
        db.load()

        channel = Channel(
            input="test",
            normalized_uri="lbry://@Test#1",
            channel_claim_id="xyz789",
            channel_name="@Test",
            folder="Test__xyz789",
        )

        db.set_channel(channel)
        retrieved = db.get_channel("xyz789")

        assert retrieved is not None
        assert retrieved.channel_name == "@Test"
        assert db.get_channel("nonexistent") is None

    def test_claim_operations(self):
        db = StateDb(str(self.state_file))
        db.load()

        claim = Claim(
            claim_id="claim123",
            channel_claim_id="channel456",
            name="my-video",
            permanent_url="lbry://@Test#1/my-video#claim123",
            claim_folder="channels/Test__channel456/claims/my-video__claim123",
        )

        db.set_claim(claim)
        retrieved = db.get_claim("claim123")

        assert retrieved is not None
        assert retrieved.name == "my-video"

    def test_run_history_logging(self):
        db = StateDb(str(self.state_file))
        db.load()

        history_file = Path(self.temp_dir) / "history.jsonl"

        db.log_run_history(
            str(history_file),
            "channel123",
            "claim456",
            "download_new",
            "sd_abc123",
            "success",
        )

        assert history_file.exists()

        with open(history_file) as f:
            line = json.loads(f.readline())
            assert line["action"] == "download_new"
            assert line["status"] == "success"

    def test_get_stats(self):
        db = StateDb(str(self.state_file))
        db.load()

        # Add test data
        claim = Claim(
            claim_id="c1",
            channel_claim_id="ch1",
            name="video1",
            permanent_url="lbry://test",
            claim_folder="test",
        )
        claim.versions["v1"] = ClaimVersion(
            version_token="v1", txid="tx1", nout=0, downloaded=True
        )

        db.set_claim(claim)

        stats = db.get_stats()
        assert stats["claims"] == 1
        assert stats["total_versions"] == 1
        assert stats["downloaded_versions"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
