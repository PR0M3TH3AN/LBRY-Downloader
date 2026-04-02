"""Tests for per-channel content mode config and resolution."""

import pytest

from config_loader import ConfigError, _parse_config
from main import resolve_content_filter_mode
from models import ChannelConfig


def test_channel_content_mode_parses_from_config():
    config = _parse_config(
        {
            "channels": [
                {
                    "input": "https://odysee.com/@Files:1",
                    "enabled": True,
                    "content_mode": "non_video_only",
                }
            ]
        }
    )

    assert config.channels[0].content_mode == "non_video_only"


def test_invalid_channel_content_mode_is_rejected():
    with pytest.raises(ConfigError) as exc_info:
        _parse_config(
            {
                "channels": [
                    {
                        "input": "https://odysee.com/@Files:1",
                        "enabled": True,
                        "content_mode": "zip_only",
                    }
                ]
            }
        )

    assert "content_mode" in str(exc_info.value)


def test_channel_content_mode_defaults_to_all():
    channel_config = ChannelConfig(input="https://odysee.com/@Mixed:1")

    assert resolve_content_filter_mode(channel_config) == (
        False,
        False,
        "all content",
    )


def test_channel_content_mode_applies_when_no_cli_override():
    channel_config = ChannelConfig(
        input="https://odysee.com/@Videos:1",
        content_mode="video_only",
    )

    assert resolve_content_filter_mode(channel_config) == (
        True,
        False,
        "video-only (channel config)",
    )


def test_cli_override_beats_channel_content_mode():
    channel_config = ChannelConfig(
        input="https://odysee.com/@Files:1",
        content_mode="non_video_only",
    )

    assert resolve_content_filter_mode(channel_config, video_only=True) == (
        True,
        False,
        "video-only (CLI override)",
    )
