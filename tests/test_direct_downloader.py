"""Tests for the direct Odysee downloader."""

import logging
from pathlib import Path
from types import SimpleNamespace

import requests
from direct_downloader import DirectDownloader
from models import Config, DownloadAction


def make_action(**metadata_overrides):
    metadata = {
        "normalized_name": "veritasium-trailer",
        "name": "veritasium-trailer",
        "source_name": "veritasium-trailer.mp4",
    }
    metadata.update(metadata_overrides)

    return DownloadAction(
        claim_id="19201da2f75357d70b151f7d87ddd94227884126",
        claim_name="veritasium-trailer",
        channel_claim_id="fb364ef587872515f545a5b4b3182b58073f230f",
        version_token="sd_deadbeefdeadbeef",
        action="download_new",
        uri="lbry://veritasium-trailer#19201da2f75357d70b151f7d87ddd94227884126",
        target_dir="/tmp/lbry-test",
        metadata=metadata,
    )


class TestDirectDownloader:
    def test_build_stream_url_uses_normalized_name(self):
        downloader = DirectDownloader(Config(), Path("/tmp"))
        action = make_action()

        assert (
            downloader.build_stream_url(action)
            == "https://odysee.com/$/stream/veritasium-trailer/"
            "19201da2f75357d70b151f7d87ddd94227884126"
        )

    def test_build_stream_url_quotes_special_slug(self):
        downloader = DirectDownloader(Config(), Path("/tmp"))
        action = make_action(normalized_name="Title With Spaces & Symbols")

        assert downloader.build_stream_url(action).startswith(
            "https://odysee.com/$/stream/Title%20With%20Spaces%20%26%20Symbols/"
        )

    def test_build_download_url_uses_claim_id(self):
        downloader = DirectDownloader(Config(), Path("/tmp"))
        action = make_action()

        assert (
            downloader.build_download_url(action)
            == "https://odysee.com/$/download/veritasium-trailer/"
            "19201da2f75357d70b151f7d87ddd94227884126"
        )

    def test_file_claims_prefer_download_endpoint(self):
        downloader = DirectDownloader(Config(), Path("/tmp"))
        action = make_action(
            source_name="archive.zip",
            source_media_type="application/zip",
            stream_type="binary",
        )

        assert downloader.build_candidate_urls(action) == [
            "https://odysee.com/$/download/veritasium-trailer/"
            "19201da2f75357d70b151f7d87ddd94227884126",
            "https://odysee.com/$/stream/veritasium-trailer/"
            "19201da2f75357d70b151f7d87ddd94227884126",
        ]

    def test_video_claims_prefer_stream_endpoint(self):
        downloader = DirectDownloader(Config(), Path("/tmp"))
        action = make_action(
            source_media_type="video/mp4",
            stream_type="video",
        )

        assert downloader.build_candidate_urls(action) == [
            "https://odysee.com/$/stream/veritasium-trailer/"
            "19201da2f75357d70b151f7d87ddd94227884126",
            "https://odysee.com/$/download/veritasium-trailer/"
            "19201da2f75357d70b151f7d87ddd94227884126",
        ]

    def test_candidate_urls_include_configured_mirrors(self):
        config = Config()
        config.general.direct_base_urls = [
            "https://odysee.com",
            "https://mirror.example",
        ]
        downloader = DirectDownloader(config, Path("/tmp"))
        action = make_action(
            source_media_type="video/mp4",
            stream_type="video",
        )

        assert downloader.build_candidate_urls(action) == [
            "https://odysee.com/$/stream/veritasium-trailer/"
            "19201da2f75357d70b151f7d87ddd94227884126",
            "https://odysee.com/$/download/veritasium-trailer/"
            "19201da2f75357d70b151f7d87ddd94227884126",
            "https://mirror.example/$/stream/veritasium-trailer/"
            "19201da2f75357d70b151f7d87ddd94227884126",
            "https://mirror.example/$/download/veritasium-trailer/"
            "19201da2f75357d70b151f7d87ddd94227884126",
        ]

    def test_429_retries_use_backoff_budget(self, monkeypatch, tmp_path):
        config = Config()
        config.general.direct_max_retries_per_url = 2
        config.general.direct_retry_backoff_seconds = 0.01
        downloader = DirectDownloader(config, Path("/tmp"))
        file_path = tmp_path / "retry-test.mp4"

        calls = {"count": 0}
        sleeps = []

        class FakeResponse:
            headers = {}

            def raise_for_status(self):
                http_error = requests.exceptions.HTTPError("429")
                http_error.response = SimpleNamespace(status_code=429)
                raise http_error

        def fake_get(*args, **kwargs):
            calls["count"] += 1
            return FakeResponse()

        monkeypatch.setattr(downloader.session, "get", fake_get)
        monkeypatch.setattr("direct_downloader.time.sleep", lambda seconds: sleeps.append(seconds))

        success, reason = downloader._download_file(
            "https://odysee.com/$/download/test/abc",
            file_path,
            "retry-test",
        )

        assert success is False
        assert "rate-limited" in reason.lower()
        assert calls["count"] == 3
        assert sleeps == [0.01, 0.02]

    def test_skip_existing_logs_existing_file_path(self, caplog):
        downloader = DirectDownloader(Config(), Path("/tmp"))
        action = make_action(
            existing_file_relpath="channels/test/claims/item/versions/sd/file.zip",
        )
        action.action = "skip_existing"

        with caplog.at_level(logging.INFO):
            success = downloader.download(action)

        assert success is True
        assert "Skipping existing file" in caplog.text
        assert "/tmp/channels/test/claims/item/versions/sd/file.zip" in caplog.text

    def test_download_logs_destination_path(self, monkeypatch, caplog, tmp_path):
        downloader = DirectDownloader(Config(), Path("/tmp"))
        action = make_action()
        action.target_dir = str(tmp_path)

        monkeypatch.setattr(
            downloader,
            "_download_file",
            lambda url, file_path, claim_name: (True, None),
        )
        monkeypatch.setattr(downloader, "_write_metadata", lambda *args, **kwargs: None)
        monkeypatch.setattr(downloader, "_write_checksum", lambda *args, **kwargs: None)
        target_file = tmp_path / "veritasium-trailer.mp4"
        target_file.write_bytes(b"data")

        with caplog.at_level(logging.INFO):
            success = downloader.download(action)

        assert success is True
        assert "Saving to:" in caplog.text
        assert str(target_file) in caplog.text
