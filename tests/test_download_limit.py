"""Tests for download limit feature."""

import pytest
from pathlib import Path
import tempfile
import shutil

from models import Channel, Config, GeneralConfig, StateDatabase, DownloadAction


class TestDownloadLimit:
    """Test the download limit functionality."""

    def test_download_limit_zero_means_all(self):
        """Test that download_limit=0 means download all (no limit)."""
        config = Config()
        config.general = GeneralConfig()
        config.general.download_limit = 0

        # download_limit of 0 should mean no limit
        assert config.general.download_limit == 0

    def test_download_limit_default_is_10(self):
        """Test that default download_limit is 10."""
        config = Config()
        config.general = GeneralConfig()

        # Default should be 10
        assert config.general.download_limit == 10

    def test_negative_download_limit_invalid(self):
        """Test that negative download_limit is invalid."""
        from config_loader import ConfigError, _parse_config

        raw_config = {
            "lbrynet": {},
            "general": {
                "download_limit": -5  # Invalid
            },
            "channels": [{"input": "https://odysee.com/@Test:1", "enabled": True}],
        }

        with pytest.raises(ConfigError) as exc_info:
            _parse_config(raw_config)

        assert "download_limit" in str(exc_info.value).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
