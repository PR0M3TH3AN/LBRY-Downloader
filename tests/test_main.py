"""Tests for main module channel resolution behavior."""

from main import resolve_channel


class FakeProxyClient:
    """Minimal client stub for proxy-backed channel resolution tests."""

    supports_file_ops = False

    def resolve(self, urls):
        uri = urls[0]
        return {
            uri: {
                "claim_id": "vanity123",
                "name": "@veritasium",
                "value_type": "channel",
                "value": {"title": "Veritasium"},
                "permanent_url": "lbry://@veritasium#1",
                "short_url": "lbry://@veritasium#1",
            }
        }

    def find_controlling_channel(self, channel_name):
        assert channel_name == "@veritasium"
        return {
            "claim_id": "control999",
            "name": "@veritasium",
            "value_type": "channel",
            "value": {"title": "Veritasium"},
            "permanent_url": "lbry://@veritasium#f",
            "short_url": "lbry://@veritasium#f",
        }


class FakeDaemonClient:
    """Minimal client stub for daemon-backed resolution tests."""

    supports_file_ops = True

    def resolve(self, urls):
        uri = urls[0]
        return {
            uri: {
                "claim_id": "daemon123",
                "name": "@example",
                "value_type": "channel",
                "value": {"title": "Example"},
                "permanent_url": "lbry://@example#1",
                "short_url": "lbry://@example#1",
            }
        }


def test_resolve_channel_uses_controlling_claim_for_proxy_client():
    channel = resolve_channel(FakeProxyClient(), "https://odysee.com/@veritasium:1")

    assert channel is not None
    assert channel.channel_claim_id == "control999"
    assert channel.channel_name == "@veritasium"


def test_resolve_channel_keeps_daemon_claim_id():
    channel = resolve_channel(FakeDaemonClient(), "https://odysee.com/@example:1")

    assert channel is not None
    assert channel.channel_claim_id == "daemon123"
    assert channel.channel_name == "@example"

