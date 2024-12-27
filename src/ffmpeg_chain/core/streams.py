from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StreamInfo:
    """Represents a single stream in an input or output file.

    Returns:
        StreamInfo: A stream object.
    """

    index: int
    codec_type: str
    codec_name: str
    input_index: int
    metadata: dict = field(default_factory=dict)
    raw_info: dict = field(default_factory=dict)

    @property
    def language(self) -> Optional[str]:
        """Get the language of the stream.

        Returns:
            Optional[str]: The language of the stream.
        """
        return self.metadata.get("language")

    @property
    def title(self) -> Optional[str]:
        """Get the title of the stream.

        Returns:
            Optional[str]: The title of the stream.
        """
        return self.metadata.get("title")


class StreamCollection:
    """A collection of StreamInfo objects."""

    def __init__(self, streams: list[StreamInfo]):
        self.streams = streams

    def __iter__(self) -> Generator[StreamInfo, None, None]:
        yield from self.streams

    def __getitem__(self, idx: int) -> StreamInfo:
        return self.streams[idx]

    def __len__(self) -> int:
        return len(self.streams)

    def __bool__(self) -> bool:
        return bool(self.streams)
