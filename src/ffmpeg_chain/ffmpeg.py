import atexit
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Literal, Optional, Union, cast

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from .core.nodes import FilterNode, Input, Output, Stream
from .core.process import FFmpegProcess, PopenProtocol


class FFmpeg:
    """A class to build and execute FFmpeg commands."""

    _active_processes: list[FFmpegProcess] = []  # Track all active FFmpeg processes
    inputs: list[Input] = []
    outputs: list[Output] = []
    _current_process: Optional[FFmpegProcess] = None

    def __init__(self, binary_path: Optional[str] = None):
        self.binary_path = binary_path or self._find_ffmpeg()
        self.global_options: list[str] = []

        # Register cleanup handler
        atexit.register(self._cleanup)

    def _cleanup(self) -> None:
        """Clean up any running processes on exit."""
        if self._current_process:
            self.terminate()

    @classmethod
    def terminate_all(cls) -> None:
        """Terminate all active FFmpeg processes."""
        for process in cls._active_processes:
            process.terminate()

    def terminate(self) -> None:
        """Terminate the current FFmpeg process if it exists."""
        if self._current_process:
            self._current_process.terminate()
            self._current_process = None

    @property
    def process(self) -> Optional[FFmpegProcess]:
        """Get the current FFmpegProcess instance if a process is running."""
        return self._current_process

    @property
    def get_process(self) -> Optional[PopenProtocol]:
        """Get the Popen instance if a process is running."""
        return self._current_process.get_process() if self._current_process else None

    def execute(
        self, capture_output: bool = False, monitor: bool = False
    ) -> Union[FFmpegProcess, subprocess.CompletedProcess[str], None]:
        """Execute the FFmpeg command.

        Args:
            capture_output (bool, optional): Whether to capture the output. Defaults to False.
            monitor (bool, optional): Whether to monitor resource usage, requires psutil to be
                installed. Defaults to False.

        Raises:
            RuntimeError: Raised when trying to monitor resources without psutil installed.
            subprocess.CalledProcessError: When the process returns a non-zero exit code when
                attempting to capture output.

        Returns:
            Union[FFmpegProcess, subprocess.CompletedProcess[str], None]: Returns FFmpegProcess
                instance if monitoring is enabled, subprocess.CompletedProcess instance if
                capture_output is enabled, or None if neither is enabled.
        """
        command = self._build_command()

        if monitor and not PSUTIL_AVAILABLE:
            raise RuntimeError("Resource monitoring requires psutil to be installed")

        kwargs: dict[str, Any] = {}
        if capture_output:
            kwargs["stdout"] = subprocess.PIPE
            kwargs["stderr"] = subprocess.PIPE
            kwargs["text"] = True

        # Create the appropriate Popen object based on psutil availability
        process: PopenProtocol
        if PSUTIL_AVAILABLE:
            process = cast(PopenProtocol, psutil.Popen(command, **kwargs))
        else:
            process = cast(PopenProtocol, subprocess.Popen(command, **kwargs))

        if capture_output:
            # try:
            returncode = process.wait()
            # stdout = process.stdout.read() if process.stdout else ""
            stdout = process.stdout if process.stdout else ""
            # stderr = process.stderr.read() if process.stderr else ""
            stderr = process.stderr if process.stderr else ""

            if returncode == 0:
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=returncode,
                    stdout=stdout,
                    stderr=stderr,
                )
            raise subprocess.CalledProcessError(
                returncode,
                command,
                output=stdout,
                stderr=stderr,
            )
            # except Exception:
            #     Clean up process resources
            #     if process.stdout:
            #         process.stdout.close()
            #     if process.stderr:
            #         process.stderr.close()
            #     raise

        self._current_process = FFmpegProcess(process, time.time())
        self._active_processes.append(self._current_process)

        return self._current_process if monitor else None

    def _find_ffmpeg(self) -> str:
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            raise FileNotFoundError("FFmpeg binary not found in system PATH")
        return ffmpeg_path

    def option(self, option: str, value: Optional[str] = None) -> "FFmpeg":
        """Add a global option to the FFmpeg command.

        Args:
            option (str): The option name to add.
            value (Optional[str], optional): The option value, if any. Defaults to None.

        Returns:
            FFmpeg: The FFmpeg instance with the option applied.
        """
        if value:
            self.global_options.extend([f"-{option}", value])
        else:
            self.global_options.append(f"-{option}")
        return self

    def input(self, path: Union[str, Path], **options: Any) -> "FFmpeg":
        """Add an input file to the FFmpeg command.

        Args:
            path (Union[str, Path]): Path to the input file.

        Returns:
            Input: The Input object representing the input file.
        """
        input_index = len(self.inputs)
        input_obj = Input(str(path), options=options, index=input_index)
        self.inputs.append(input_obj)
        return self

    def map_stream(
        self,
        input_obj: Input,
        stream_type: Literal["video", "audio", "subtitle"] = "video",
        stream_index: int = 0,
    ) -> Stream:
        """Map a stream from an input file.

        Args:
            input_obj (Input): The input object to map the stream from.
            stream_type (Literal["video", "audio", "subtitle"], optional):
                The type of the stream. Defaults to "video".
            stream_index (int, optional): The index of the stream. Defaults to 0.

        Returns:
            Stream: The Stream object representing the mapped stream.
        """
        return Stream(type=stream_type, index=stream_index, input_index=input_obj.index)

    def output(
        self,
        path: Union[str, Path],
        mapped_streams: Optional[list[Stream]] = None,
        **options: Any,
    ) -> "FFmpeg":
        """Add an output file to the FFmpeg command.

        Args:
            path (Union[str, Path]): Path to the output file.
            mapped_streams (Optional[list[Stream]], optional): List of mapped streams.
                Defaults to None.

        Returns:
            FFmpeg: The FFmpeg instance with the output file added.
        """
        if mapped_streams is None:
            # Default to mapping first video and audio streams from the last input
            last_input = self.inputs[-1]
            mapped_streams = [
                Stream("video", 0, last_input.index),
                Stream("audio", 0, last_input.index),
            ]

        output_obj = Output(str(path), mapped_streams=mapped_streams)
        output_obj.options.update(**options)
        self.outputs.append(output_obj)
        return self

    def _build_filter_chain(self, filter_node: Optional[FilterNode]) -> str:
        if filter_node is None:
            return ""

        chain = []
        current: Optional[FilterNode] = filter_node
        while current is not None:
            chain.append(str(current))
            current = current.next_node

        return ",".join(chain)

    def _build_command(self) -> list[str]:
        command: list = [self.binary_path]

        # Add global options
        command.extend(self.global_options)

        # Add inputs and their options
        for input_obj in self.inputs:
            for opt, value in input_obj.options.items():
                command.extend([f"-{opt}", str(value)])

            if input_obj.filter_chain:
                filter_str = self._build_filter_chain(input_obj.filter_chain)
                command.extend(["-vf", filter_str])

            command.extend(["-i", str(input_obj.path)])

        # Add outputs and their options
        for output_obj in self.outputs:
            # Add stream mappings
            for stream in output_obj.mapped_streams:
                map_str = f"{stream.input_index}:{stream.type[0]}:{stream.index}"
                command.extend(["-map", map_str])

            # Add other output options
            for opt, value in output_obj.options.items():
                if opt == "vf":
                    output_obj.filters.append(value)
                else:
                    command.extend([f"-{opt}", str(value)])

            if output_obj.filters:
                command.extend(["-vf", ",".join(output_obj.filters)])

            command.append(str(output_obj.path))

        return command

    def print_command(self) -> None:
        """Print the FFmpeg command to the console."""
        command = self._build_command()
        print(" ".join(command))


# Add signal handlers for graceful shutdown
def signal_handler(*_: Any, **__: Any) -> None:
    """Signal handler to terminate all active FFmpeg processes on SIGINT and SIGTERM."""
    FFmpeg.terminate_all()


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
