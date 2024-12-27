import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from ffmpeg_chain.core.nodes import Input, Output, Stream


class TestStream:
    def test_stream_creation(self) -> None:
        stream = Stream("video", 0, 1)
        assert stream.type == "video"
        assert stream.index == 0
        assert stream.input_index == 1
        assert not stream.options

    def test_stream_with_options(self) -> None:
        stream = Stream("audio", 1, 0, {"codec": "aac"})
        assert stream.type == "audio"
        assert stream.options == {"codec": "aac"}

    def test_stream_invalid_type(self) -> None:
        with pytest.raises(TypeError):
            Stream("invalid", 0, 0)  # type: ignore  # Testing invalid input


class TestInput:
    def test_input_creation(self) -> None:
        input_obj = Input("test.mp4")
        assert str(input_obj.path) == "test.mp4"
        assert input_obj.index == 0
        assert not input_obj.options
        assert input_obj.filter_chain is None

    def test_input_with_options(self) -> None:
        input_obj = Input("test.mp4", options={"codec": "h264"})
        assert input_obj.options == {"codec": "h264"}

    def test_input_path_conversion(self) -> None:
        path = Path("test.mp4")
        input_obj = Input(path)
        assert isinstance(input_obj.path, (str, Path))

    @patch("subprocess.run")
    def test_probe_file(self, mock_run: Mock, sample_ffprobe_output: dict[str, Any]) -> None:
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(sample_ffprobe_output)
        mock_run.return_value = mock_result

        input_obj = Input("test.mp4")
        probe_data = input_obj.probe_file()

        assert len(probe_data["streams"]) == len(sample_ffprobe_output["streams"])
        assert probe_data["streams"][0]["codec_type"] == "video"
        assert probe_data["streams"][1]["codec_type"] == "audio"

    @patch("subprocess.run")
    def test_probe_file_error(self, mock_run: Mock) -> None:
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "FFprobe error"
        mock_run.return_value = mock_result

        input_obj = Input("test.mp4")
        with pytest.raises(RuntimeError, match="FFprobe failed: FFprobe error"):
            input_obj.probe_file()

    @patch("subprocess.run")
    def test_get_streams_by_type(self, mock_run: Mock, sample_ffprobe_output: dict[str, Any]) -> None:
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(sample_ffprobe_output)
        mock_run.return_value = mock_result

        input_obj = Input("test.mp4")
        video_streams = input_obj._get_streams_by_type("video")
        assert len(video_streams) == 1
        assert video_streams[0].codec_type == "video"

    def test_filter(self) -> None:
        input_obj = Input("test.mp4")
        input_obj.filter("scale", width="1280", height="-1")

        assert input_obj.filter_chain is not None
        assert input_obj.filter_chain.filter_name == "scale"
        assert input_obj.filter_chain.filter_args == {"width": "1280", "height": "-1"}

    def test_apply_multiple_filters(self) -> None:
        input_obj = Input("test.mp4")
        (input_obj.filter("scale", width="1280", height="-1").filter("fps", fps="30"))

        current = input_obj.filter_chain
        filters = []
        while current is not None:
            filters.append(current.filter_name)
            current = current.next_node

        assert filters == ["scale", "fps"]


class TestOutput:
    def test_output_creation(self) -> None:
        output_obj = Output("output.mp4")
        assert str(output_obj.path) == "output.mp4"
        assert not output_obj.options
        assert not output_obj.filters
        assert not output_obj.mapped_streams

    def test_output_with_streams(self) -> None:
        streams = [Stream("video", 0, 0), Stream("audio", 1, 0)]
        output_obj = Output("output.mp4", mapped_streams=streams)
        assert len(output_obj.mapped_streams) == len(streams)
        assert output_obj.mapped_streams[0].type == "video"
        assert output_obj.mapped_streams[1].type == "audio"

    def test_output_with_options(self) -> None:
        output_obj = Output("output.mp4", options={"codec:v": "libx264", "preset": "medium"})
        assert output_obj.options == {"codec:v": "libx264", "preset": "medium"}

    def test_output_with_filters(self) -> None:
        output_obj = Output("output.mp4")
        output_obj.filters.append("scale=1280:-1")
        assert output_obj.filters == ["scale=1280:-1"]

    def test_output_path_conversion(self) -> None:
        path = Path("output.mp4")
        output_obj = Output(path)
        assert isinstance(output_obj.path, (str, Path))
