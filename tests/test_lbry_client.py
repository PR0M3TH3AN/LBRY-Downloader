"""Tests for LBRY client helper behavior."""

from lbry_client import LbryClient


def test_create_odysee_proxy_client_defaults():
    client = LbryClient.create_odysee_proxy(timeout=42)

    assert client.api_url == LbryClient.ODYSEE_PROXY_URL
    assert client.timeout == 42
    assert client.backend_name == "Odysee public proxy"
    assert client.supports_file_ops is False


def test_find_controlling_channel_uses_claim_search(monkeypatch):
    client = LbryClient.create_odysee_proxy()
    captured = {}

    def fake_claim_search(**kwargs):
        captured.update(kwargs)
        return {"items": [{"claim_id": "control123", "name": "@example"}]}

    monkeypatch.setattr(client, "claim_search", fake_claim_search)

    result = client.find_controlling_channel("@example")

    assert result == {"claim_id": "control123", "name": "@example"}
    assert captured["name"] == "@example"
    assert captured["claim_type"] == ["channel"]
    assert captured["is_controlling"] is True
    assert captured["order_by"] == ["effective_amount"]
    assert captured["page"] == 1
    assert captured["page_size"] == 1

