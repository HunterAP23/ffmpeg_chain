from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest


@pytest.fixture
def sample_stream_info() -> dict[str, Any]:
    return {
        "index": 0,
        "codec_type": "video",
        "codec_name": "h264",
        "tags": {"language": "eng", "title": "Main Video"},
    }


@pytest.fixture
def sample_ffprobe_output() -> dict[str, Any]:
    return {
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "codec_name": "h264",
                "tags": {"language": "eng", "title": "Main Video"},
            },
            {
                "index": 1,
                "codec_type": "audio",
                "codec_name": "aac",
                "tags": {"language": "eng", "title": "Main Audio"},
            },
        ]
    }


@pytest.fixture
def temp_video(tmp_path: Path) -> Path:
    """Create a temporary video file path."""
    video_path = tmp_path / "test.mp4"
    video_path.touch()
    return video_path


@pytest.fixture
def mock_run() -> Mock:
    """Create a mock for subprocess.run."""
    return Mock()
