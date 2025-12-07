import threading
import collections
import os
import json
import queue
import time
import atexit
import sys
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from types import ModuleType
from contextlib import contextmanager

try:
    import redis

    redis_module: Optional[ModuleType] = redis
except ImportError:
    redis_module = None

try:
    import grpc

    grpc_module: Optional[ModuleType] = grpc
    from ..protos import trace_pb2, trace_pb2_grpc

    trace_pb2_module: Optional[ModuleType] = trace_pb2
    trace_pb2_grpc_module: Optional[ModuleType] = trace_pb2_grpc
except ImportError:
    grpc_module = None
    trace_pb2_module = None
    trace_pb2_grpc_module = None

from ..utils import GLOBAL_CONFIG


@contextmanager
def cross_platform_file_lock(file_obj, lock_type: str = "exclusive"):
    """
    Context manager for cross-platform file locking.
    Uses msvcrt on Windows and fcntl on Unix-like systems.
    """
    if sys.platform == "win32":
        try:
            import msvcrt

            # Windows locking requires a byte count.
            # We'll try to lock the whole file.
            # Note: msvcrt doesn't support shared locks in the same way fcntl does,
            # so we treat both as exclusive for safety or rely on OS behavior.
            # Using LK_RLCK (blocking) or LK_NBLCK (non-blocking).

            # To be safe and simple, we use blocking lock for the max possible size
            # or current size. Here we use a large arbitrary number to cover most logs.
            # 2GB limit is safe for 32-bit systems too.
            MAX_SIZE = 2 * 1024 * 1024 * 1024

            file_obj.seek(0)
            msvcrt.locking(file_obj.fileno(), msvcrt.LK_RLCK, MAX_SIZE)
            try:
                yield
            finally:
                file_obj.seek(0)
                msvcrt.locking(file_obj.fileno(), msvcrt.LK_UNLCK, MAX_SIZE)
        except (ImportError, OSError):
            # Fallback or error (e.g. if file is not a real file)
            yield
    else:
        try:
            import fcntl

            op = fcntl.LOCK_EX if lock_type == "exclusive" else fcntl.LOCK_SH
            fcntl.flock(file_obj, op)
            try:
                yield
            finally:
                fcntl.flock(file_obj, fcntl.LOCK_UN)
        except (ImportError, OSError):
            yield


class BaseCollector(ABC):
    """
    Abstract base class for all trace collectors.
    """

    @abstractmethod
    def add_trace(self, trace: Dict):
        """
        Records a single trace.
        """
        pass

    @abstractmethod
    def get_traces(self) -> List[Dict]:
        """
        Retrieves all recorded traces.
        """
        pass

    @abstractmethod
    def clear(self):
        """
        Clears all recorded traces.
        """
        pass


class MemoryCollector(BaseCollector):
    """
    Thread-safe, sharded in-memory collector.
    Default implementation.
    """

    def __init__(self):
        # Adaptive sharding: Disable sharding for small buffers to preserve behavior
        # and memory efficiency. Enable for large buffers to reduce contention.
        max_traces = GLOBAL_CONFIG.max_traces

        if max_traces < GLOBAL_CONFIG.collector_max_traces_sharding_threshold:
            self.num_shards = 1
        else:
            self.num_shards = GLOBAL_CONFIG.collector_shard_count

        # Calculate shard size, ensuring at least 1 per shard
        shard_maxlen = max(1, max_traces // self.num_shards)

        self._shards = [
            collections.deque(maxlen=shard_maxlen) for _ in range(self.num_shards)
        ]
        self._locks = [threading.Lock() for _ in range(self.num_shards)]

    def add_trace(self, trace: Dict):
        """
        Adds a trace to a thread-local shard. Thread-safe and low contention.
        """
        # Use hash(str(id)) to avoid potential alignment bias in thread IDs on Linux
        shard_idx = hash(str(threading.get_ident())) % self.num_shards
        with self._locks[shard_idx]:
            self._shards[shard_idx].append(trace)

    def get_traces(self) -> List[Dict]:
        """
        Returns a snapshot of the current traces, aggregated from all shards.
        """
        all_traces = []
        for i in range(self.num_shards):
            with self._locks[i]:
                all_traces.extend(self._shards[i])

        # Sort by timestamp to restore chronological order
        all_traces.sort(key=lambda x: x.get("timestamp", 0))
        return all_traces

    def clear(self):
        """
        Clears all shards.
        """
        for i in range(self.num_shards):
            with self._locks[i]:
                self._shards[i].clear()


# Backward compatibility alias
Collector = MemoryCollector


class ThreadedBatchCollector(BaseCollector):
    """
    Base class for collectors that process traces in batches in a background thread.
    This ensures minimal impact on the main application thread.
    """

    def __init__(
        self,
        batch_size: int = 100,
        flush_interval: float = 1.0,
        max_queue_size: int = 10000,
    ):
        self._queue: "queue.Queue[Dict]" = queue.Queue(maxsize=max_queue_size)
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(
            target=self._worker, daemon=True, name="PyPSS-Collector-Worker"
        )
        self._worker_thread.start()
        atexit.register(self.shutdown)

    def add_trace(self, trace: Dict):
        try:
            self._queue.put_nowait(trace)
        except queue.Full:
            # Drop trace if queue is full to preserve application stability (load shedding)
            pass

    def _worker(self):
        batch = []
        last_flush = time.time()

        while not self._stop_event.is_set():
            try:
                # Wait for items with short timeout to check stop_event and flush_interval
                item = self._queue.get(timeout=0.1)
                batch.append(item)

                # Check if batch is full
                if len(batch) >= self._batch_size:
                    self._flush_batch_safe(batch)
                    batch = []
                    last_flush = time.time()
            except queue.Empty:
                pass

            # Check flush interval
            if batch and (time.time() - last_flush > self._flush_interval):
                self._flush_batch_safe(batch)
                batch = []
                last_flush = time.time()

        # Drain queue on shutdown
        while not self._queue.empty():
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break

        if batch:
            self._flush_batch_safe(batch)

    def _flush_batch_safe(self, batch: List[Dict]):
        try:
            self._flush_batch(batch)
        except Exception:
            # Prevent worker crash
            pass

    def shutdown(self):
        """Signals the worker to stop and waits for it to finish."""
        if self._worker_thread.is_alive():
            self._stop_event.set()
            self._worker_thread.join(timeout=2.0)

    @abstractmethod
    def _flush_batch(self, batch: List[Dict]):
        """Implement actual writing logic here."""
        pass


class RedisCollector(ThreadedBatchCollector):
    """
    Collector that pushes traces to a Redis list.
    Uses a pipeline for high-throughput batch insertion.
    """

    def __init__(
        self,
        redis_url: str,
        key_name: str = "pypss:traces",
        batch_size: int = 100,
        flush_interval: float = 1.0,
    ):
        super().__init__(batch_size=batch_size, flush_interval=flush_interval)
        if redis_module is None:
            raise ImportError(
                "Redis client is not installed. Install with 'pip install pypss[distributed]'"
            )
        try:
            self.client = redis_module.from_url(redis_url)
            # Test connection
            self.client.ping()
        except Exception as e:
            raise ConnectionError(f"Could not connect to Redis at {redis_url}: {e}")

        self.key_name = key_name

    def _flush_batch(self, batch: List[Dict]):
        if not batch:
            return

        pipeline = self.client.pipeline()
        for trace in batch:
            pipeline.rpush(self.key_name, json.dumps(trace))
        pipeline.execute()

    def get_traces(self) -> List[Dict]:
        try:
            items = self.client.lrange(self.key_name, 0, -1)
            return [json.loads(item) for item in items]
        except Exception:
            return []

    def clear(self):
        try:
            self.client.delete(self.key_name)
        except Exception:
            pass


class FileFIFOCollector(ThreadedBatchCollector):
    """
    Collector that appends traces to a file using advisory locks (flock).
    Writes in batches to minimize file open/lock overhead.
    """

    def __init__(
        self, file_path: str, batch_size: int = 100, flush_interval: float = 1.0
    ):
        super().__init__(batch_size=batch_size, flush_interval=flush_interval)
        self.file_path = file_path
        try:
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        except OSError:
            pass

    def _flush_batch(self, batch: List[Dict]):
        if not batch:
            return

        # Prepare content block
        content: str = ""
        for trace in batch:
            content += json.dumps(trace) + "\n"

        try:
            # Open for appending
            with open(self.file_path, "a") as f:
                # Exclusive lock for writing the whole batch
                with cross_platform_file_lock(f, "exclusive"):
                    f.write(content)
                    f.flush()
        except Exception:
            pass

    def get_traces(self) -> List[Dict]:
        traces: List[Dict] = []
        if not os.path.exists(self.file_path):
            return traces
        try:
            with open(self.file_path, "r") as f:
                # Shared lock for reading
                with cross_platform_file_lock(f, "shared"):
                    for line in f:
                        if line.strip():
                            try:
                                traces.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
        except Exception:
            pass
        return traces

    def clear(self):
        try:
            # Open for writing (truncates)
            with open(self.file_path, "w") as f:
                with cross_platform_file_lock(f, "exclusive"):
                    pass  # Truncation happens on open
        except Exception:
            pass


class GRPCCollector(BaseCollector):
    """
    Collector that sends traces to a gRPC server.
    Uses async futures for non-blocking operation.
    """

    def __init__(self, target: str, secure: bool = False):
        if grpc_module is None or trace_pb2_grpc_module is None:
            raise ImportError(
                "gRPC support is not installed. Install with 'pip install pypss[distributed]'"
            )

        if secure:
            creds = grpc_module.ssl_channel_credentials()
            self.channel = grpc_module.secure_channel(target, creds)
        else:
            self.channel = grpc_module.insecure_channel(target)

        assert trace_pb2_grpc_module is not None  # mypy: ensure module is not None
        self.stub = trace_pb2_grpc_module.TraceServiceStub(self.channel)

    def add_trace(self, trace: Dict):
        try:
            assert trace_pb2_module is not None  # mypy: ensure module is not None
            msg = trace_pb2_module.TraceMessage(
                trace_id=str(trace.get("trace_id", "")),
                name=str(trace.get("name", "")),
                filename=str(trace.get("filename", "")),
                lineno=int(trace.get("lineno", 0)),
                module=str(trace.get("module", "")),
                duration=float(trace.get("duration", 0.0)),
                cpu_time=float(trace.get("cpu_time", 0.0)),
                wait_time=float(trace.get("wait_time", 0.0)),
                memory=int(trace.get("memory", 0)),
                memory_diff=int(trace.get("memory_diff", 0)),
                error=bool(trace.get("error", False)),
                exception_type=str(trace.get("exception_type") or ""),
                exception_message=str(trace.get("exception_message") or ""),
                branch_tag=str(trace.get("branch_tag") or ""),
                timestamp=float(trace.get("timestamp", 0.0)),
            )
            # Use future to avoid blocking the application
            self.stub.SubmitTrace.future(msg)
        except Exception:
            pass

    def get_traces(self) -> List[Dict]:
        # gRPC collector is write-only
        return []

    def clear(self):
        # Not applicable for remote collector
        pass
