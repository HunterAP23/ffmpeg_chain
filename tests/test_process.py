import time
from collections.abc import Generator
from typing import Any, NamedTuple, Optional
from unittest.mock import Mock

import pytest

from ffmpeg_chain.core.process import PSUTIL_AVAILABLE, FFmpegProcess, PopenProtocol

if PSUTIL_AVAILABLE:
    pass


class MockProcess(PopenProtocol):
    def __init__(self, returncode: Optional[int] = None) -> None:
        self._returncode = returncode
        self._pid = 12345
        self._terminated = False
        self.stdout: Optional[Any] = None
        self.stderr: Optional[Any] = None
        self.args: list[str] = []  # Required by protocol

    @property
    def returncode(self) -> Optional[int]:
        return self._returncode if self._terminated else None

    @property
    def pid(self) -> int:
        return self._pid

    def poll(self) -> Optional[int]:
        return self.returncode

    def wait(self, timeout: Optional[float] = None) -> int:
        self._terminated = True
        if self._returncode is None:
            self._returncode = 0
        return self._returncode

    def terminate(self) -> None:
        self._terminated = True

    def kill(self) -> None:
        self._terminated = True

    def is_running(self) -> bool:
        return not self._terminated

    def cpu_percent(self) -> float:
        return 0.0

    def memory_percent(self) -> float:
        return 0.0

    def memory_info(self) -> NamedTuple:
        # Create a simple namedtuple for memory info
        from collections import namedtuple

        MemInfo = namedtuple("MemInfo", ["rss", "vms"])
        return MemInfo(0, 0)

    def oneshot(self) -> Generator[None, None, None]:
        yield


@pytest.fixture
def mock_process_good() -> MockProcess:
    return MockProcess(returncode=0)


@pytest.fixture
def mock_process_bad() -> MockProcess:
    return MockProcess(returncode=1)


@pytest.fixture
def mock_process_inf() -> MockProcess:
    return MockProcess(returncode=1)


class TestFFmpegProcess:

    def test_process_creation(self, mock_process_good: MockProcess) -> None:
        start_time = time.time()
        process = FFmpegProcess(mock_process_good, start_time)
        assert process.start_time == start_time
        assert not process._terminated
        if PSUTIL_AVAILABLE:
            assert len(process.resource_usage) == 1
        else:
            assert len(process.resource_usage) == 0

    def test_get_process(self, mock_process_good: MockProcess) -> None:
        process = FFmpegProcess(mock_process_good, time.time())
        assert process.get_process() == mock_process_good

    def test_poll_terminated(self, mock_process_good: MockProcess) -> None:
        process = FFmpegProcess(mock_process_good, time.time())
        process._terminated = True
        assert process.poll() == mock_process_good.returncode

    def test_poll_running(self, mock_process_good: MockProcess) -> None:
        process = FFmpegProcess(mock_process_good, time.time())
        assert process.poll() is None

    @pytest.mark.psutil
    def test_poll_with_psutil(self) -> None:
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")
        mock_psutil_process = Mock()
        mock_psutil_process.poll = Mock(return_value=None)
        mock_psutil_process.is_running = Mock(return_value=True)
        mock_psutil_process.cpu_percent = Mock(return_value=10.0)
        mock_psutil_process.memory_percent = Mock(return_value=5.0)
        mock_psutil_process.memory_info = Mock(return_value=Mock(_asdict=lambda: {"rss": 1000}))
        mock_psutil_process.returncode = None
        mock_psutil_process.pid = 12345

        process = FFmpegProcess(mock_psutil_process, time.time())
        assert process.poll() is None
        assert len(process.resource_usage) == 1
        usage = process.resource_usage[0]
        assert "cpu_percent" in usage
        assert "memory_percent" in usage
        assert "memory_info" in usage

    def test_terminate(self, mock_process_good: MockProcess) -> None:
        process = FFmpegProcess(mock_process_good, time.time())
        process.terminate()
        assert process._terminated
        assert mock_process_good._terminated

    def test_kill(self, mock_process_good: MockProcess) -> None:
        process = FFmpegProcess(mock_process_good, time.time())
        process.kill()
        assert process._terminated
        assert mock_process_good._terminated

    def test_wait(self, mock_process_good: MockProcess) -> None:
        process = FFmpegProcess(mock_process_good, time.time())
        # Set up the mock process as already terminated
        mock_process_good._terminated = True
        # mock_process_good.returncode = 0
        # Wait should return immediately since process is already terminated
        assert process.wait() == 0

    def test_wait_timeout(self, mock_process_inf: MockProcess) -> None:
        process = FFmpegProcess(mock_process_inf, time.time())
        # mock_process_inf.returncode = None  # Process never finishes
        with pytest.raises(TimeoutError):
            process.wait(timeout=0.1)

    def test_pid(self, mock_process_good: MockProcess) -> None:
        process = FFmpegProcess(mock_process_good, time.time())
        assert process.pid == mock_process_good.pid

    def test_returncode(self, mock_process_good: MockProcess) -> None:
        process = FFmpegProcess(mock_process_good, time.time())
        assert process.returncode == mock_process_good.returncode

    @pytest.mark.psutil
    def test_metrics_collection(self, mock_process_good: MockProcess) -> None:
        if not PSUTIL_AVAILABLE:
            pytest.skip("psutil not available")

        mock_psutil_process = Mock()
        mock_psutil_process.poll = Mock(return_value=None)
        mock_psutil_process.is_running = Mock(return_value=True)
        mock_psutil_process.cpu_percent = Mock(return_value=10.0)
        mock_psutil_process.memory_percent = Mock(return_value=5.0)
        mock_psutil_process.memory_info = Mock(return_value=Mock(_asdict=lambda: {"rss": 1000}))
        mock_psutil_process.returncode = None
        mock_psutil_process.pid = 12345
        mock_psutil_process.terminate = Mock()

        process = FFmpegProcess(mock_psutil_process, time.time())
        time.sleep(0.3)  # Allow some metrics to be collected
        process.terminate()

        assert len(process.resource_usage) > 0
        assert "cpu_percent" in process.resource_usage[0]
        assert "memory_percent" in process.resource_usage[0]
        assert "memory_info" in process.resource_usage[0]
