import subprocess
import threading
import time
from collections.abc import Generator, Sequence
from os import PathLike
from typing import Any, NamedTuple, Optional, Protocol, Union, cast

CommandArg = Union[str, bytes, PathLike[str], PathLike[bytes]]
CommandLine = Union[CommandArg, Sequence[CommandArg]]  # Changed from list to Sequence


try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class PopenProtocol(Protocol):
    """Protocol defining the common interface between subprocess.Popen and psutil.Popen."""

    args: CommandLine  # Changed type to match subprocess expectations

    @property
    def pid(self) -> int: ...

    @property
    def returncode(self) -> Optional[int]: ...

    def poll(self) -> Optional[int]: ...
    def wait(self, timeout: Optional[float] = None) -> int: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...
    def is_running(self) -> bool: ...
    def cpu_percent(self) -> float: ...
    def memory_percent(self) -> float: ...
    def memory_info(self) -> NamedTuple: ...
    def oneshot(self) -> Generator: ...

    stdout: Optional[str]
    stderr: Optional[str]


class FFmpegProcess:
    """Wrapper around a Popen instance to provide additional functionality and metrics tracking."""

    def __init__(self, process: PopenProtocol, start_time: float):
        self.process: PopenProtocol = process
        self.start_time = start_time
        self.resource_usage: list[dict[str, Any]] = []
        self._terminated = False
        self._metrics_thread: Optional[threading.Thread] = None
        self._stop_metrics = threading.Event()

        # Start metrics collection if psutil is available
        if PSUTIL_AVAILABLE:
            self._metrics_thread = threading.Thread(target=self._collect_metrics)
            self._metrics_thread.daemon = True
            self._metrics_thread.start()

    def get_process(self) -> PopenProtocol:
        """Get the underlying process instance.

        Returns:
            PopenProtocol: The process instance
        """
        return self.process

    def poll(self) -> Optional[int]:
        """Check if the process has finished.

        Returns:
            Optional[int]: The process return code if it has finished, None otherwise
        """
        if self._terminated:
            return self.process.returncode
        status = self.process.poll()
        if status is not None:
            self._stop_metrics.set()
            self._terminated = True
        return status

    def wait(self, timeout: Optional[float] = None) -> int:
        """Wait for the process to complete and return its exit code.

        Args:
            timeout (Optional[float]): Maximum time to wait in seconds. None means wait forever.

        Returns:
            int: The process return code

        Raises:
            TimeoutError: If the process doesn't complete within the timeout period
        """
        start_time = time.time()
        while True:
            returncode = self.poll()
            if returncode is not None:
                return returncode

            if timeout is not None and (time.time() - start_time) > timeout:
                raise TimeoutError("Process did not complete within the specified timeout")

            time.sleep(0.1)

    def terminate(self) -> None:
        """Terminate the FFmpeg process gracefully."""
        if not self._terminated and self.poll() is None:
            self.process.terminate()
            self._terminated = True
            self._stop_metrics.set()
            if self._metrics_thread and self._metrics_thread.is_alive():
                self._metrics_thread.join(timeout=1.0)

    def kill(self) -> None:
        """Forcefully kill the FFmpeg process."""
        if not self._terminated and self.poll() is None:
            self.process.kill()
            self._terminated = True
            self._stop_metrics.set()
            if self._metrics_thread and self._metrics_thread.is_alive():
                self._metrics_thread.join(timeout=1.0)

    @property
    def pid(self) -> int:
        """Get the process ID of the FFmpeg process."""
        return self.process.pid

    @property
    def returncode(self) -> Optional[int]:
        """Get the return code of the FFmpeg process."""
        return self.process.returncode

    def get_output(self) -> tuple[Optional[str], Optional[str]]:
        """Get the current stdout and stderr output.

        Returns:
            tuple[Optional[str], Optional[str]]: Current stdout and stderr content
        """
        stdout = stderr = None
        if self.process.stdout:
            try:
                stdout = self.process.stdout
                # if stdout == b"":  # handle bytes output
                #     stdout = None
                # elif isinstance(stdout, bytes):
                #     stdout = stdout.decode()
            except (OSError, ValueError):
                pass

        if self.process.stderr:
            try:
                stderr = self.process.stderr
                # if stderr == b"":  # handle bytes output
                #     stderr = None
                # elif isinstance(stderr, bytes):
                #     stderr = stderr.decode()
            except (OSError, ValueError):
                pass

        return stdout, stderr

    def check_output(self) -> Optional[Union[subprocess.CompletedProcess, subprocess.CalledProcessError]]:
        """Check the process output and return a CompletedProcess instance, or raise
            a CalledProcessError exception.

        Raises:
            subprocess.CalledProcessError: If the process returned a non-zero exit code.

        Returns:
            Optional[Union[subprocess.CompletedProcess, subprocess.CalledProcessError]]:
                The process result.
        """
        returncode = self.poll()
        if returncode is None:
            return None

        stdout, stderr = self.get_output()

        # Type narrowing for args
        args = self.process.args
        args_seq: Sequence[CommandArg]

        if isinstance(args, Sequence):
            # This forces type checking of sequence args
            args_seq = cast(Sequence[CommandArg], args)
        else:
            # Ensure single arg is CommandArg type before making list
            single_arg: CommandArg = args  # This forces type checking of non-sequence arg
            args_seq = [single_arg]

        if returncode == 0:
            return subprocess.CompletedProcess(
                args=args_seq,
                returncode=returncode,
                stdout=stdout or "",
                stderr=stderr or "",
            )
        else:
            raise subprocess.CalledProcessError(
                returncode,
                args_seq,
                output=stdout,
                stderr=stderr,
            )

    def _collect_metrics(self) -> None:
        """Continuously collect process metrics in the background."""
        if not PSUTIL_AVAILABLE:
            return

        while not self._stop_metrics.is_set():
            try:
                if self.process.is_running():
                    usage = {
                        "timestamp": time.time() - self.start_time,
                        "cpu_percent": self.process.cpu_percent(),
                        "memory_percent": self.process.memory_percent(),
                        "memory_info": self.process.memory_info()._asdict(),
                    }
                    self.resource_usage.append(usage)
                else:
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            time.sleep(0.1)  # Collect metrics every 100ms
