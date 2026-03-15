"""Tests for utility functions."""

import pytest
from pathlib import Path

from utils import (
    sanitize_filename,
    slugify,
    generate_version_token,
    expand_path,
    is_downloadable_claim,
    normalize_odysee_url,
)


class TestSanitizeFilename:
    def test_basic_sanitization(self):
        assert sanitize_filename("hello/world") == "hello_world"
        assert sanitize_filename("file:name") == "file_name"
        assert sanitize_filename('file"name') == "file_name"

    def test_whitespace_collapse(self):
        assert sanitize_filename("hello   world") == "hello world"

    def test_trailing_cleanup(self):
        assert sanitize_filename("hello.") == "hello"
        assert sanitize_filename("hello ") == "hello"

    def test_length_limit(self):
        long_name = "a" * 200
        result = sanitize_filename(long_name)
        assert len(result) <= 120

    def test_extension_preservation(self):
        result = sanitize_filename("my/file:name.txt")
        assert result.endswith(".txt")


class TestSlugify:
    def test_basic_slug(self):
        assert slugify("Hello World") == "hello-world"
        assert slugify("Test!!!") == "test"

    def test_special_chars_removed(self):
        assert slugify("hello@world#123") == "helloworld123"

    def test_multiple_dashes_collapsed(self):
        assert slugify("hello---world") == "hello-world"


class TestGenerateVersionToken:
    def test_sd_hash_priority(self):
        token = generate_version_token(
            sd_hash="abc123", stream_hash="def456", txid="ghi789", nout=0
        )
        assert token.startswith("sd_")

    def test_stream_hash_fallback(self):
        token = generate_version_token(stream_hash="def456", txid="ghi789", nout=0)
        assert token.startswith("stream_")

    def test_txid_fallback(self):
        token = generate_version_token(txid="ghi789", nout=5)
        assert token.startswith("tx_")

    def test_metadata_fallback(self):
        token = generate_version_token(metadata={"name": "test", "id": 123})
        assert token.startswith("meta_")


class TestExpandPath:
    def test_home_expansion(self):
        path = expand_path("~/test")
        assert not str(path).startswith("~")
        assert path.is_absolute()


class TestIsDownloadableClaim:
    def test_stream_claim_with_source(self):
        claim = {"value_type": "stream", "value": {"source": {"sd_hash": "abc123"}}}
        assert is_downloadable_claim(claim) is True

    def test_stream_claim_with_stream_hash(self):
        claim = {"value_type": "stream", "value": {}, "stream_hash": "abc123"}
        assert is_downloadable_claim(claim) is True

    def test_non_stream_claim(self):
        claim = {"value_type": "channel"}
        assert is_downloadable_claim(claim) is False

    def test_stream_without_source(self):
        claim = {"value_type": "stream", "value": {}}
        assert is_downloadable_claim(claim) is False


class TestNormalizeOdyseeUrl:
    def test_https_odysee(self):
        result = normalize_odysee_url("https://odysee.com/@Channel:1")
        assert result == "lbry://@Channel:1"

    def test_http_odysee(self):
        result = normalize_odysee_url("http://odysee.com/@Channel:1")
        assert result == "lbry://@Channel:1"

    def test_already_lbry(self):
        result = normalize_odysee_url("lbry://@Channel:1")
        assert result == "lbry://@Channel:1"

    def test_short_form(self):
        result = normalize_odysee_url("@Channel:1")
        assert result == "lbry://@Channel:1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
