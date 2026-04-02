"""Tests for transport mode selection."""

from main import resolve_transport_mode


def test_transport_mode_defaults_to_direct():
    assert resolve_transport_mode() == (True, "direct")


def test_transport_mode_p2p_override_wins():
    assert resolve_transport_mode(p2p=True) == (False, "p2p")


def test_transport_mode_explicit_direct():
    assert resolve_transport_mode(direct=True) == (True, "direct")
