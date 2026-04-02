"""Tests for offline site generation and metadata backfill."""

import json

from models import Channel, Config, DownloadAction
from offline_site import ArchiveSiteManager


WEBP_STUB = b"RIFF\x1a\x00\x00\x00WEBPVP8 " + b"\x00" * 10


def test_offline_site_builds_from_archive_metadata(tmp_path):
    config = Config()
    config.general.base_dir = str(tmp_path)
    config.general.offline_site_dir = str(tmp_path / "site")
    config.general.fetch_missing_metadata_assets = False

    manager = ArchiveSiteManager(config, tmp_path)

    channel = Channel(
        input="https://odysee.com/@example:1",
        normalized_uri="lbry://@example#1",
        channel_claim_id="chan123",
        channel_name="@example",
        folder="example__chan123",
        display_name="Example Channel",
        description="Channel description",
        links=[{"label": "Website", "url": "https://example.com"}],
    )
    manager.ensure_channel_artifacts(channel)

    version_dir = (
        tmp_path
        / "channels"
        / channel.folder
        / "claims"
        / "my-claim__claim123"
        / "versions"
        / "sd_abc123"
    )
    version_dir.mkdir(parents=True)
    file_path = version_dir / "video.mp4"
    file_path.write_bytes(b"video-data")
    thumbnail_path = version_dir.parent.parent / "claim-thumbnail.jpg"
    thumbnail_path.write_bytes(b"thumb")

    action = DownloadAction(
        claim_id="claim123",
        claim_name="my-claim",
        channel_claim_id=channel.channel_claim_id,
        version_token="sd_abc123",
        action="skip_existing",
        uri="lbry://@example#1/my-claim#claim123",
        target_dir=str(version_dir),
        metadata={
            "title": "My Claim",
            "description": "Claim description",
            "source_media_type": "video/mp4",
            "stream_type": "video",
            "source_name": "video.mp4",
            "local_file_path": str(file_path.relative_to(tmp_path)),
            "thumbnail_url": "https://example.com/thumb.jpg",
            "release_time": 1234567890,
            "links": [
                {
                    "label": "External",
                    "url": "https://odysee.com/@example:1/my-claim",
                }
            ],
        },
    )
    manager.ensure_claim_artifacts(channel, action)
    manager.build_site(channel_index={channel.channel_claim_id: channel})

    channel_json = tmp_path / "channels" / channel.folder / "channel.json"
    claim_json = version_dir.parent.parent / "claim.json"
    metadata_json = version_dir / "metadata.json"
    site_index = tmp_path / "site" / "index.html"
    channel_page = tmp_path / "site" / "channels" / channel.folder / "index.html"
    claim_page = (
        tmp_path
        / "site"
        / "channels"
        / channel.folder
        / "claims"
        / "my-claim__claim123"
        / "index.html"
    )

    assert channel_json.exists()
    assert claim_json.exists()
    assert metadata_json.exists()
    assert site_index.exists()
    assert channel_page.exists()
    assert claim_page.exists()

    channel_payload = json.loads(channel_json.read_text())
    claim_payload = json.loads(claim_json.read_text())
    version_payload = json.loads(metadata_json.read_text())

    assert channel_payload["display_name"] == "Example Channel"
    assert claim_payload["title"] == "My Claim"
    assert version_payload["file_name"] == "video.mp4"

    assert "Example Channel" in site_index.read_text()
    channel_page_html = channel_page.read_text()
    claim_page_html = claim_page.read_text()

    assert "My Claim" in channel_page_html
    assert 'class="thumb"' in channel_page_html
    assert "Open local file: video.mp4" in claim_page_html
    assert '<video class="media-player" controls preload="metadata"' in claim_page_html
    assert 'poster="../../../../_assets/channels/example__chan123/claims/my-claim__claim123/claim-thumbnail.jpg"' in claim_page_html
    assert '<source src="../../../../../channels/example__chan123/claims/my-claim__claim123/versions/sd_abc123/video.mp4" type="video/mp4">' in claim_page_html


def test_offline_site_handles_string_release_time(tmp_path):
    config = Config()
    config.general.base_dir = str(tmp_path)
    config.general.offline_site_dir = str(tmp_path / "site")
    config.general.fetch_missing_metadata_assets = False

    manager = ArchiveSiteManager(config, tmp_path)

    channel_dir = tmp_path / "channels" / "example__chan123"
    claim_dir = channel_dir / "claims" / "string-time__claim123"
    version_dir = claim_dir / "versions" / "sd_abc123"
    version_dir.mkdir(parents=True)

    (channel_dir / "channel.json").write_text(
        json.dumps({"display_name": "Example", "channel_name": "@example"})
    )
    (claim_dir / "claim.json").write_text(
        json.dumps({"title": "String Time Claim", "release_time": "1712100000"})
    )
    (version_dir / "metadata.json").write_text(
        json.dumps({"version_token": "sd_abc123", "release_time": "1712100000"})
    )
    (version_dir / "file.bin").write_bytes(b"x")

    manager.build_site()

    assert (tmp_path / "site" / "index.html").exists()


def test_channel_page_uses_thumbnail_from_latest_version_when_claim_json_lacks_it(tmp_path):
    config = Config()
    config.general.base_dir = str(tmp_path)
    config.general.offline_site_dir = str(tmp_path / "site")
    config.general.fetch_missing_metadata_assets = False

    manager = ArchiveSiteManager(config, tmp_path)

    channel_dir = tmp_path / "channels" / "example__chan123"
    claim_dir = channel_dir / "claims" / "video-claim__claim123"
    version_dir = claim_dir / "versions" / "sd_abc123"
    version_dir.mkdir(parents=True)

    (channel_dir / "channel.json").write_text(
        json.dumps({"display_name": "Example", "channel_name": "@example"})
    )
    (claim_dir / "claim.json").write_text(
        json.dumps({"title": "Video Claim", "description": "Claim-level description"})
    )
    (version_dir / "metadata.json").write_text(
        json.dumps(
            {
                "version_token": "sd_abc123",
                "title": "Video Claim",
                "description": "Version description",
                "thumbnail_url": "https://example.com/version-thumb.jpg",
                "release_time": 1712100000,
                "source_media_type": "video/mp4",
            }
        )
    )
    (version_dir / "video.mp4").write_bytes(b"x")

    manager.build_site()

    channel_page = tmp_path / "site" / "channels" / "example__chan123" / "index.html"
    claim_page = (
        tmp_path
        / "site"
        / "channels"
        / "example__chan123"
        / "claims"
        / "video-claim__claim123"
        / "index.html"
    )

    channel_page_html = channel_page.read_text()
    claim_page_html = claim_page.read_text()

    assert 'class="thumb" src="https://example.com/version-thumb.jpg"' in channel_page_html
    assert 'class="hero-thumb" src="https://example.com/version-thumb.jpg"' in claim_page_html
    assert 'poster="https://example.com/version-thumb.jpg"' in claim_page_html


def test_build_site_normalizes_mislabeled_thumbnail_extensions(tmp_path):
    config = Config()
    config.general.base_dir = str(tmp_path)
    config.general.offline_site_dir = str(tmp_path / "site")
    config.general.fetch_missing_metadata_assets = False

    manager = ArchiveSiteManager(config, tmp_path)

    channel_dir = tmp_path / "channels" / "example__chan123"
    claim_dir = channel_dir / "claims" / "video-claim__claim123"
    version_dir = claim_dir / "versions" / "sd_abc123"
    version_dir.mkdir(parents=True)

    (channel_dir / "channel.json").write_text(
        json.dumps({"display_name": "Example", "channel_name": "@example"})
    )
    (claim_dir / "claim.json").write_text(
        json.dumps({"title": "Video Claim", "thumbnail_url": "https://example.com/thumb.jpg"})
    )
    (version_dir / "metadata.json").write_text(json.dumps({"version_token": "sd_abc123"}))
    (version_dir / "video.mp4").write_bytes(b"x")

    mislabeled = claim_dir / "claim-thumbnail.jpg"
    mislabeled.write_bytes(WEBP_STUB)

    manager.build_site()

    corrected = claim_dir / "claim-thumbnail.webp"
    channel_page = tmp_path / "site" / "channels" / "example__chan123" / "index.html"
    claim_page = (
        tmp_path
        / "site"
        / "channels"
        / "example__chan123"
        / "claims"
        / "video-claim__claim123"
        / "index.html"
    )

    assert not mislabeled.exists()
    assert corrected.exists()
    assert 'claim-thumbnail.webp' in channel_page.read_text()
    assert 'claim-thumbnail.webp' in claim_page.read_text()


def test_build_site_mirrors_thumbnail_assets_into_site_tree(tmp_path):
    config = Config()
    config.general.base_dir = str(tmp_path)
    config.general.offline_site_dir = str(tmp_path / "site")
    config.general.fetch_missing_metadata_assets = False

    manager = ArchiveSiteManager(config, tmp_path)

    channel_dir = tmp_path / "channels" / "example__chan123"
    claim_dir = channel_dir / "claims" / "video-claim__claim123"
    version_dir = claim_dir / "versions" / "sd_abc123"
    version_dir.mkdir(parents=True)

    (channel_dir / "channel.json").write_text(
        json.dumps({"display_name": "Example", "channel_name": "@example"})
    )
    (claim_dir / "claim.json").write_text(json.dumps({"title": "Video Claim"}))
    (version_dir / "metadata.json").write_text(json.dumps({"version_token": "sd_abc123"}))
    (version_dir / "video.mp4").write_bytes(b"x")
    (claim_dir / "claim-thumbnail.webp").write_bytes(WEBP_STUB)

    manager.build_site()

    mirrored = (
        tmp_path
        / "site"
        / "_assets"
        / "channels"
        / "example__chan123"
        / "claims"
        / "video-claim__claim123"
        / "claim-thumbnail.webp"
    )
    channel_page = tmp_path / "site" / "channels" / "example__chan123" / "index.html"

    assert mirrored.exists()
    assert '_assets/channels/example__chan123/claims/video-claim__claim123/claim-thumbnail.webp' in channel_page.read_text()


def test_build_site_extracts_video_thumbnail_when_metadata_thumbnail_is_missing(
    tmp_path, monkeypatch
):
    config = Config()
    config.general.base_dir = str(tmp_path)
    config.general.offline_site_dir = str(tmp_path / "site")
    config.general.fetch_missing_metadata_assets = False

    manager = ArchiveSiteManager(config, tmp_path)

    channel_dir = tmp_path / "channels" / "example__chan123"
    claim_dir = channel_dir / "claims" / "video-claim__claim123"
    version_dir = claim_dir / "versions" / "sd_abc123"
    version_dir.mkdir(parents=True)

    (channel_dir / "channel.json").write_text(
        json.dumps({"display_name": "Example", "channel_name": "@example"})
    )
    (version_dir / "metadata.json").write_text(
        json.dumps(
            {
                "version_token": "sd_abc123",
                "title": "Video Claim",
                "description": "Video with no upstream thumbnail metadata",
                "source_media_type": "video/mp4",
                "release_time": 1712100000,
            }
        )
    )
    (version_dir / "video.mp4").write_bytes(b"x")

    def fake_extract(input_path, output_path):
        output_path.write_bytes(b"jpeg-data")
        return True

    monkeypatch.setattr(manager, "_run_ffmpeg_thumbnail", fake_extract)

    manager.build_site()

    channel_page = tmp_path / "site" / "channels" / "example__chan123" / "index.html"
    extracted_thumb = claim_dir / "claim-thumbnail.jpg"

    assert extracted_thumb.exists()
    assert '_assets/channels/example__chan123/claims/video-claim__claim123/claim-thumbnail.jpg' in channel_page.read_text()
