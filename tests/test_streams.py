from typing import Any

import pytest

from ffmpeg_chain.core.streams import StreamCollection, StreamInfo


class TestStreamInfo:
    def test_stream_info_creation(self, sample_stream_info: dict[str, Any]) -> None:
        stream = StreamInfo(
            index=sample_stream_info["index"],
            codec_type=sample_stream_info["codec_type"],
            codec_name=sample_stream_info["codec_name"],
            input_index=0,
            metadata=sample_stream_info["tags"],
        )
        assert stream.index == 0
        assert stream.codec_type == "video"
        assert stream.codec_name == "h264"
        assert stream.input_index == 0

    def test_stream_info_language(self, sample_stream_info: dict[str, Any]) -> None:
        stream = StreamInfo(
            index=0,
            codec_type="video",
            codec_name="h264",
            input_index=0,
            metadata=sample_stream_info["tags"],
        )
        assert stream.language == "eng"

    def test_stream_info_title(self, sample_stream_info: dict[str, Any]) -> None:
        stream = StreamInfo(
            index=0,
            codec_type="video",
            codec_name="h264",
            input_index=0,
            metadata=sample_stream_info["tags"],
        )
        assert stream.title == "Main Video"

    def test_stream_info_missing_metadata(self) -> None:
        stream = StreamInfo(
            index=0,
            codec_type="video",
            codec_name="h264",
            input_index=0,
        )
        assert stream.language is None
        assert stream.title is None


class TestStreamCollection:
    @pytest.fixture
    def sample_streams(self, sample_stream_info: dict[str, Any]) -> list[StreamInfo]:
        return [
            StreamInfo(0, "video", "h264", 0, sample_stream_info["tags"]),
            StreamInfo(1, "audio", "aac", 0, {"language": "eng"}),
        ]

    def test_stream_collection_creation(self, sample_streams: list[StreamInfo]) -> None:
        collection = StreamCollection(sample_streams)
        assert len(collection.streams) == len(sample_streams)

    def test_stream_collection_iteration(self, sample_streams: list[StreamInfo]) -> None:
        collection = StreamCollection(sample_streams)
        streams = list(collection)
        assert len(streams) == len(sample_streams)
        assert all(isinstance(s, StreamInfo) for s in streams)

    def test_stream_collection_indexing(self, sample_streams: list[StreamInfo]) -> None:
        collection = StreamCollection(sample_streams)
        assert collection[0].codec_type == "video"
        assert collection[1].codec_type == "audio"

    def test_stream_collection_length(self, sample_streams: list[StreamInfo]) -> None:
        collection = StreamCollection(sample_streams)
        assert len(collection) == len(sample_streams)

    def test_stream_collection_bool(self) -> None:
        empty_collection = StreamCollection([])
        assert not empty_collection
        non_empty_collection = StreamCollection([StreamInfo(0, "video", "h264", 0)])
        assert non_empty_collection

    def test_stream_collection_invalid_index(self, sample_streams: list[StreamInfo]) -> None:
        collection = StreamCollection(sample_streams)
        with pytest.raises(IndexError):
            _ = collection[2]
