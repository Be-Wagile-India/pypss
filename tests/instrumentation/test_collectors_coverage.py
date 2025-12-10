import importlib
import os
import queue
import sys
import time
from unittest.mock import MagicMock

import pytest

import pypss.instrumentation.collectors
from pypss.instrumentation import collectors
from pypss.instrumentation.collectors import (
    FileFIFOCollector,
    GRPCCollector,
    RedisCollector,
    ThreadedBatchCollector,
    _initialize_global_collector,
    cross_platform_file_lock,
)


class TestCollectorsCoverage:
    def test_imports_coverage(self, monkeypatch):
        # Mock redis and grpc installed
        monkeypatch.setitem(sys.modules, "redis", MagicMock())
        monkeypatch.setitem(sys.modules, "grpc", MagicMock())
        # We need to mock trace_pb2 stuff too to avoid errors during import
        monkeypatch.setitem(sys.modules, "pypss.protos.trace_pb2", MagicMock())
        monkeypatch.setitem(sys.modules, "pypss.protos.trace_pb2_grpc", MagicMock())

        # Reload to trigger the try/except blocks
        importlib.reload(collectors)

        assert collectors.redis_module is not None
        assert collectors.grpc_module is not None

    def test_initialize_global_collector(self):
        # Reset global_collector
        collectors.global_collector = None
        _initialize_global_collector()
        assert collectors.global_collector is not None
        assert isinstance(collectors.global_collector, collectors.MemoryCollector)

    def test_cross_platform_file_lock_win32(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        mock_msvcrt = MagicMock()
        monkeypatch.setitem(sys.modules, "msvcrt", mock_msvcrt)

        mock_file = MagicMock()

        # Test exclusive lock
        with cross_platform_file_lock(mock_file, "exclusive"):
            pass

        assert mock_msvcrt.locking.called

    def test_cross_platform_file_lock_win32_import_error(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setitem(sys.modules, "msvcrt", None)  # Simulate import error

        mock_file = MagicMock()
        with cross_platform_file_lock(mock_file):
            pass

    def test_cross_platform_file_lock_linux_import_error(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setitem(sys.modules, "fcntl", None)  # Simulate import error

        mock_file = MagicMock()
        with cross_platform_file_lock(mock_file):
            pass

    def test_threaded_collector_queue_full(self):
        class MockCollector(ThreadedBatchCollector):
            def _flush_batch(self, batch):
                pass

            def clear(self):
                pass

            def get_traces(self):
                return []

        collector = MockCollector(max_queue_size=1)
        collector.add_trace({"a": 1})

        # Fill queue
        try:
            collector._queue.put_nowait({"b": 2})
        except queue.Full:
            pass

        # This should trigger queue.Full exception handling (pass)
        collector.add_trace({"c": 3})
        collector.shutdown()

    def test_threaded_collector_flush_exception(self):
        class FailingCollector(ThreadedBatchCollector):
            def _flush_batch(self, batch):
                raise ValueError("Flush failed")

            def clear(self):
                pass

            def get_traces(self):
                return []

        collector = FailingCollector(flush_interval=0.1)
        collector.add_trace({"a": 1})
        time.sleep(0.2)  # Wait for flush
        collector.shutdown()
        # Should not crash

    def test_file_fifo_collector_makedirs_error(self, monkeypatch, tmp_path):
        monkeypatch.setattr(os, "makedirs", MagicMock(side_effect=OSError))
        FileFIFOCollector(str(tmp_path / "temp_file.fifo"))
        # Should not raise

    def test_file_fifo_collector_flush_open_error(self, monkeypatch, tmp_path):
        collector = FileFIFOCollector(str(tmp_path / "temp_file.fifo"))
        monkeypatch.setattr("builtins.open", MagicMock(side_effect=OSError))
        collector.add_trace({"a": 1})
        collector._flush_batch([{"a": 1}])  # Trigger manually
        # Should not raise

    def test_file_fifo_collector_get_traces_open_error(self, monkeypatch, tmp_path):
        collector = FileFIFOCollector(str(tmp_path / "temp_file.fifo"))
        monkeypatch.setattr(os.path, "exists", lambda x: True)
        monkeypatch.setattr("builtins.open", MagicMock(side_effect=OSError))
        traces = collector.get_traces()
        assert traces == []

    def test_file_fifo_collector_clear_open_error(self, monkeypatch, tmp_path):
        collector = FileFIFOCollector(str(tmp_path / "temp_file.fifo"))
        monkeypatch.setattr("builtins.open", MagicMock(side_effect=OSError))
        collector.clear()
        # Should not raise

    def test_grpc_collector_secure(self, monkeypatch):
        # Mock grpc module
        mock_grpc = MagicMock()
        mock_pb2_grpc = MagicMock()

        monkeypatch.setitem(sys.modules, "grpc", mock_grpc)
        monkeypatch.setattr(pypss.instrumentation.collectors, "grpc_module", mock_grpc)
        monkeypatch.setattr(pypss.instrumentation.collectors, "trace_pb2_grpc_module", mock_pb2_grpc)

        GRPCCollector("target", secure=True)

        assert mock_grpc.secure_channel.called

    def test_grpc_collector_add_trace_exception(self, monkeypatch):
        mock_grpc = MagicMock()
        mock_pb2_grpc = MagicMock()

        monkeypatch.setitem(sys.modules, "grpc", mock_grpc)
        monkeypatch.setattr(pypss.instrumentation.collectors, "grpc_module", mock_grpc)
        monkeypatch.setattr(pypss.instrumentation.collectors, "trace_pb2_grpc_module", mock_pb2_grpc)

        collector = GRPCCollector("target")
        # Mock stub to raise exception
        collector.stub.SubmitTrace.future.side_effect = Exception("RPC Error")

        collector.add_trace({"trace_id": "1"})
        # Should not raise

    def test_redis_collector_no_module(self, monkeypatch):
        monkeypatch.setattr(pypss.instrumentation.collectors, "redis_module", None)
        with pytest.raises(ImportError):
            RedisCollector("redis://localhost")
