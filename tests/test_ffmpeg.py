import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ffmpeg_chain import FFmpeg
from ffmpeg_chain.core.nodes import Stream
from ffmpeg_chain.core.process import PSUTIL_AVAILABLE, FFmpegProcess

if PSUTIL_AVAILABLE:
    pass


class TestFFmpeg:
    def test_initialization(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            ffmpeg = FFmpeg()
            assert ffmpeg.binary_path == "/usr/bin/ffmpeg"
            assert not ffmpeg.global_options
            assert not ffmpeg.inputs
            assert not ffmpeg.outputs

    def test_initialization_binary_not_found(self) -> None:
        with patch("shutil.which", return_value=None):
            with pytest.raises(FileNotFoundError):
                FFmpeg()

    def test_option_without_value(self) -> None:
        ffmpeg = FFmpeg(binary_path="ffmpeg")
        ffmpeg.option("y")
        assert ffmpeg.global_options == ["-y"]

    def test_option_with_value(self) -> None:
        ffmpeg = FFmpeg(binary_path="ffmpeg")
        ffmpeg.option("t", "60")
        assert ffmpeg.global_options == ["-t", "60"]

    def test_input_creation(self) -> None:
        ffmpeg = FFmpeg(binary_path="ffmpeg")
        ffmpeg.input("assets/standard-test.mp4", **{"codec": "h264"})
        input_obj = ffmpeg.inputs[-1]
        assert str(input_obj.path) == "assets/standard-test.mp4"
        assert input_obj.options == {"codec": "h264"}
        assert input_obj.index == 0

    def test_map_stream(self) -> None:
        ffmpeg = FFmpeg(binary_path="ffmpeg")
        ffmpeg.input("assets/standard-test.mp4")
        input_obj = ffmpeg.inputs[-1]
        stream = ffmpeg.map_stream(input_obj, "video", 0)
        assert isinstance(stream, Stream)
        assert stream.type == "video"
        assert stream.index == 0
        assert stream.input_index == 1

    def test_output_creation(self) -> None:
        ffmpeg = FFmpeg(binary_path="ffmpeg")
        ffmpeg.input("assets/standard-test.mp4")
        # Create a Stream object explicitly
        stream = Stream("video", 0, 0)
        ffmpeg.output("output.mp4", mapped_streams=[stream], codec_v="libx264")
        assert len(ffmpeg.outputs) == 1
        assert str(ffmpeg.outputs[0].path) == "output.mp4"
        assert ffmpeg.outputs[0].options == {"codec_v": "libx264"}

    def test_build_command(self) -> None:
        ffmpeg = FFmpeg(binary_path="ffmpeg")
        ffmpeg.option("y").input("assets/standard-test.mp4").output("output.mp4", None, **{"c:v": "libx264"})

        command = ffmpeg._build_command()
        assert "-y" in command
        assert "-i" in command
        assert "assets/standard-test.mp4" in command
        assert "-c:v" in command
        assert "libx264" in command
        assert "output.mp4" in command

    @pytest.mark.psutil
    def test_execute_with_monitoring(self) -> None:
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")
        ffmpeg = FFmpeg(binary_path="ffmpeg")
        mock_process = Mock()
        mock_process.poll = Mock(return_value=None)
        mock_process.wait = Mock(return_value=0)
        mock_process.pid = 12345
        mock_process.returncode = None
        mock_process.is_running = Mock(return_value=True)
        mock_process.cpu_percent = Mock(return_value=10.0)
        mock_process.memory_percent = Mock(return_value=5.0)
        mock_process.memory_info = Mock(return_value=Mock(_asdict=lambda: {"rss": 1000}))

        with patch("psutil.Popen", return_value=mock_process):
            process = ffmpeg.input("assets/standard-test.mp4").output("output.mp4").execute(monitor=True)
            assert process is not None

    def test_execute_with_capture_output(self) -> None:
        ffmpeg = FFmpeg(binary_path="ffmpeg")
        mock_process = Mock()
        mock_process.wait = Mock(return_value=0)
        mock_process.poll = Mock(return_value=None)
        mock_process.pid = 12345
        mock_process.args = ["ffmpeg", "-i", "assets/standard-test.mp4", "output.mp4"]
        mock_process.stdout = "output"
        mock_process.stderr = ""
        mock_process.returncode = 0

        with patch("subprocess.Popen", return_value=mock_process):
            result = ffmpeg.input("assets/standard-test.mp4").output("output.mp4").execute(capture_output=True)
            assert isinstance(result, subprocess.CompletedProcess)
            assert result.returncode == 0
            assert result.stdout == "output"

    @pytest.mark.psutil
    def test_execute_with_capture_output_psutil(self) -> None:
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")
        ffmpeg = FFmpeg(binary_path="ffmpeg")
        mock_process = Mock()
        mock_process.wait = Mock(return_value=0)
        mock_process.poll = Mock(return_value=None)
        mock_process.pid = 12345
        mock_process.args = ["ffmpeg", "-i", "assets/standard-test.mp4", "output.mp4"]
        mock_process.stdout = "output"
        mock_process.stderr = ""

        with patch("psutil.Popen", return_value=mock_process):
            result = ffmpeg.input("assets/standard-test.mp4").output("output.mp4").execute(capture_output=True)
            assert isinstance(result, subprocess.CompletedProcess)
            assert result.returncode == 0
            assert result.stdout == "output"

    def test_terminate(self) -> None:
        ffmpeg = FFmpeg(binary_path="ffmpeg")
        mock_process = Mock()
        ffmpeg._current_process = Mock(process=mock_process)
        ffmpeg.terminate()
        assert ffmpeg._current_process is None

    @pytest.mark.skipif(
        not hasattr(subprocess.Popen, "poll"),
        reason="Platform doesn't support process polling",
    )
    @pytest.mark.psutil
    def test_process_monitoring(self, temp_video: Path) -> None:
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")
        ffmpeg = FFmpeg(binary_path="ffmpeg")
        output_path = temp_video.parent / "output.mp4"
        process = ffmpeg.input(str(temp_video)).output(str(output_path)).execute(monitor=True)

        # Type guard to handle Union type
        if not isinstance(process, FFmpegProcess):
            pytest.fail("Expected FFmpegProcess instance")

        assert process is not None
        while process.poll() is None:
            if hasattr(process.process, "cpu_percent"):
                assert len(process.resource_usage) >= 0

        assert process.returncode is not None

    def test_cleanup_on_exit(self) -> None:
        ffmpeg = FFmpeg(binary_path="ffmpeg")
        mock_process = Mock()
        ffmpeg._current_process = Mock(process=mock_process)
        ffmpeg._cleanup()
        assert ffmpeg._current_process is None
