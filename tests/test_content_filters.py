"""Tests for CLI content-type filtering."""

from main import filter_actions_by_content_type
from models import DownloadAction


def make_action(name: str, **metadata):
    base_metadata = {
        "source_name": name,
        "file_name": name,
    }
    base_metadata.update(metadata)
    return DownloadAction(
        claim_id=f"claim-{name}",
        claim_name=name,
        channel_claim_id="channel-1",
        version_token=f"version-{name}",
        action="download_new",
        uri=f"lbry://{name}",
        target_dir="/tmp",
        metadata=base_metadata,
    )


def test_video_only_keeps_only_video_actions():
    video_action = make_action("clip.mp4", source_media_type="video/mp4")
    zip_action = make_action("bundle.zip", source_media_type="application/zip")

    actions = filter_actions_by_content_type(
        [video_action, zip_action],
        video_only=True,
    )

    assert actions == [video_action]


def test_non_video_only_keeps_zip_and_skips_video():
    video_action = make_action("clip.mp4", source_media_type="video/mp4")
    zip_action = make_action("bundle.zip", source_media_type="application/zip")

    actions = filter_actions_by_content_type(
        [video_action, zip_action],
        non_video_only=True,
    )

    assert actions == [zip_action]


def test_video_filter_falls_back_to_filename_extension():
    video_action = make_action("clip.mkv")
    other_action = make_action("bundle.zip")

    actions = filter_actions_by_content_type(
        [video_action, other_action],
        video_only=True,
    )

    assert actions == [video_action]
