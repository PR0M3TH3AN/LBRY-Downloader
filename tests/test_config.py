"""Tests for configuration loading."""

import pytest
from pathlib import Path
import tempfile
import os

from config_loader import load_config, ConfigError, create_default_config
from models import Config


class TestLoadConfig:
    def test_missing_config_file(self):
        with pytest.raises(ConfigError) as exc_info:
            load_config("/nonexistent/path/config.yaml")

        assert "not found" in str(exc_info.value)

    def test_empty_channels_list(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
lbrynet:
  api_url: "http://127.0.0.1:5279"

general:
  base_dir: "~/test"

channels: []
""")

        with pytest.raises(ConfigError) as exc_info:
            load_config(str(config_file))

        assert "at least one channel" in str(exc_info.value)

    def test_all_channels_disabled(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
lbrynet:
  api_url: "http://127.0.0.1:5279"

general:
  base_dir: "~/test"

channels:
  - input: "https://odysee.com/@Test:1"
    enabled: false
""")

        with pytest.raises(ConfigError) as exc_info:
            load_config(str(config_file))

        assert "at least one channel" in str(exc_info.value).lower()

    def test_valid_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
lbrynet:
  api_url: "http://127.0.0.1:5279"
  timeout_seconds: 120

general:
  base_dir: "~/Documents/lbry-downloads"
  max_workers: 3
  log_level: "DEBUG"

channels:
  - input: "https://odysee.com/@Test:1"
    enabled: true
    tags_include: ["tech"]
    tags_exclude: ["spam"]
""")

        config = load_config(str(config_file))

        assert isinstance(config, Config)
        assert config.lbrynet.api_url == "http://127.0.0.1:5279"
        assert config.lbrynet.timeout_seconds == 120
        assert config.general.max_workers == 3
        assert config.general.log_level == "DEBUG"
        assert len(config.channels) == 1
        assert config.channels[0].input == "https://odysee.com/@Test:1"
        assert config.channels[0].tags_include == ["tech"]

    def test_invalid_log_level(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
lbrynet:
  api_url: "http://127.0.0.1:5279"

general:
  base_dir: "~/test"
  log_level: "INVALID"

channels:
  - input: "https://odysee.com/@Test:1"
    enabled: true
""")

        with pytest.raises(ConfigError) as exc_info:
            load_config(str(config_file))

        assert "log_level" in str(exc_info.value)

    def test_invalid_filename_mode(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
lbrynet:
  api_url: "http://127.0.0.1:5279"

general:
  base_dir: "~/test"
  filename_mode: "invalid"

channels:
  - input: "https://odysee.com/@Test:1"
    enabled: true
""")

        with pytest.raises(ConfigError) as exc_info:
            load_config(str(config_file))

        assert "filename_mode" in str(exc_info.value)

    def test_valid_direct_retry_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
general:
  base_dir: "~/test"
  direct_base_urls:
    - "https://odysee.com/"
    - "https://mirror.example/"
  direct_max_retries_per_url: 3
  direct_retry_backoff_seconds: 1.5
  direct_auto_fallback_to_p2p: true

channels:
  - input: "https://odysee.com/@Test:1"
    enabled: true
""")

        config = load_config(str(config_file))

        assert config.general.direct_base_urls == [
            "https://odysee.com",
            "https://mirror.example",
        ]
        assert config.general.direct_max_retries_per_url == 3
        assert config.general.direct_retry_backoff_seconds == 1.5
        assert config.general.direct_auto_fallback_to_p2p is True

    def test_offline_site_defaults_to_base_dir_site(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
general:
  base_dir: "~/test-archive"

channels:
  - input: "https://odysee.com/@Test:1"
    enabled: true
""")

        config = load_config(str(config_file))

        assert config.general.build_offline_site is True
        assert config.general.fetch_missing_metadata_assets is True
        assert config.general.offline_site_dir.endswith("/test-archive/site")

    def test_invalid_direct_retry_backoff(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
general:
  base_dir: "~/test"
  direct_retry_backoff_seconds: 0

channels:
  - input: "https://odysee.com/@Test:1"
    enabled: true
""")

        with pytest.raises(ConfigError) as exc_info:
            load_config(str(config_file))

        assert "direct_retry_backoff_seconds" in str(exc_info.value)


class TestDefaultConfig:
    def test_create_default_config(self):
        config = create_default_config()

        assert "lbrynet:" in config
        assert "general:" in config
        assert "channels:" in config
        assert "http://127.0.0.1:5279" in config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
