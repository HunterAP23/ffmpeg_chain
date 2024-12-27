import json
import shutil
import subprocess
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any, Literal, Optional, Union

from .filters import FilterNode
from .streams import StreamCollection, StreamInfo


@dataclass
class Stream:
    """Represents a single stream in an input or output file.

    Args:
        type (Literal["video", "audio", "subtitle"]): The type of the stream.
        index (int): The index of the stream in the input file.
        input_index (int): The index of the input file containing the stream.
        options (dict[str, str], optional): Additional options for the stream. Defaults to {}.
    """

    type: Literal["video", "audio", "subtitle"]
    index: int
    input_index: int
    options: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Handles post-initialization validation of the Stream object.

        Raises:
            TypeError: If the stream type is not one of "video", "audio", or "subtitle".
        """
        valid_types = ("video", "audio", "subtitle")
        if self.type not in valid_types:
            raise TypeError(f"Stream type must be one of {valid_types}, got {self.type!r}")


@dataclass
class Input:
    """Represents an input file to be processed by FFmpeg.

    Args:
        path (Union[str, Path]): The path to the input file.
        filter_chain (Optional[FilterNode], optional): A FilterNode object representing the
            filter chain for the input. Defaults to None.
        options (dict[str, str], optional): Additional options for the input. Defaults to {}.
        index (int, optional): The index of the input in the FFmpeg command. Defaults to 0.
        _ffprobe_data (Optional[dict], optional): Cached FFprobe data for the input file.
            Defaults to None.
    """

    path: Union[str, Path]
    filter_chain: Optional[FilterNode] = None
    options: dict[str, str] = field(default_factory=dict)
    index: int = field(default=0)
    _ffprobe_data: Optional[dict] = field(default=None, repr=False)

    def probe_file(self) -> dict:
        """Run FFprobe on the input file and return the parsed JSON data.

        Raises:
            FileNotFoundError: Raised if the FFprobe binary is not found in the system PATH.
            RuntimeError: Raised if FFprobe fails to run.

        Returns:
            dict: The parsed JSON data from FFprobe.
        """
        if self._ffprobe_data is None:
            ffprobe_path = shutil.which("ffprobe")
            if not ffprobe_path:
                raise FileNotFoundError("FFprobe binary not found in system PATH")

            cmd = [
                ffprobe_path,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(self.path),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                raise RuntimeError(f"FFprobe failed: {result.stderr}")

            self._ffprobe_data = json.loads(result.stdout)
        return self._ffprobe_data

    def _get_streams_by_type(self, stream_type: str) -> StreamCollection:
        probe_data = self.probe_file()
        streams = []

        for stream in probe_data.get("streams", []):
            if stream.get("codec_type") == stream_type:
                stream_info = StreamInfo(
                    index=stream["index"],
                    codec_type=stream["codec_type"],
                    codec_name=stream["codec_name"],
                    input_index=self.index,
                    metadata=stream.get("tags", {}),
                    raw_info=stream,
                )
                streams.append(stream_info)

        return StreamCollection(streams)

    @cached_property
    def video(self) -> StreamCollection:
        """Returns all video streams in this input."""
        return self._get_streams_by_type("video")

    @cached_property
    def audio(self) -> StreamCollection:
        """Returns all audio streams in this input."""
        return self._get_streams_by_type("audio")

    @cached_property
    def subtitle(self) -> StreamCollection:
        """Returns all subtitle streams in this input."""
        return self._get_streams_by_type("subtitle")

    def filter(self, name: str, **kwargs: Any) -> "Input":
        """Apply a filter to the input stream.

        Args:
            name (str): name of the filter in FFmpeg.

        Returns:
            Input: return the Input node to allow chaining.
        """
        new_filter = FilterNode(name, **kwargs)
        if self.filter_chain is None:
            self.filter_chain = new_filter
        else:
            current = self.filter_chain
            while current.next_node is not None:
                current = current.next_node
            current.next_node = new_filter
        return self


@dataclass
class Output:
    """Represents an output file to be generated by FFmpeg."""

    path: Union[str, Path]
    mapped_streams: list[Stream] = field(default_factory=list)
    options: dict[str, str] = field(default_factory=dict)
    filters: list[str] = field(default_factory=list)
