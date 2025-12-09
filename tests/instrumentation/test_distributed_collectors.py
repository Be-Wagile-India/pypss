import pytest
import json
import time
import queue
from unittest.mock import MagicMock, patch
import os  # Added import os
from pypss.instrumentation.collectors import (
    RedisCollector,
    GRPCCollector,
    FileFIFOCollector,
    MemoryCollector,
    ThreadedBatchCollector,
)


class TestRedisCollector:
    def test_init_raises_if_no_redis(self):
        # Patch the MODULE variable 'redis_module', NOT the import 'redis'
        with patch("pypss.instrumentation.collectors.redis_module", None):
            with pytest.raises(ImportError):
                RedisCollector("redis://localhost")

    @patch("pypss.instrumentation.collectors.redis_module")
    def test_add_trace_batches(self, mock_redis_module):
        mock_client = MagicMock()
        mock_pipeline = MagicMock()
        mock_client.pipeline.return_value = mock_pipeline
        mock_redis_module.from_url.return_value = mock_client

        # Small batch size to force flush
        collector = RedisCollector(
            "redis://localhost", batch_size=2, flush_interval=10.0
        )

        trace1 = {"name": "t1", "duration": 1.0}
        trace2 = {"name": "t2", "duration": 2.0}

        collector.add_trace(trace1)
        collector.add_trace(trace2)

        # Wait for worker to process (it sleeps 0.1s)
        time.sleep(0.5)

        # Should have called pipeline.rpush twice
        assert mock_pipeline.rpush.call_count >= 2
        mock_pipeline.execute.assert_called()

        collector.shutdown()

    @patch("pypss.instrumentation.collectors.redis_module")
    def test_get_traces(self, mock_redis_module):
        mock_client = MagicMock()
        mock_redis_module.from_url.return_value = mock_client
        trace = {"name": "test", "duration": 1.0}
        mock_client.lrange.return_value = [json.dumps(trace)]

        collector = RedisCollector("redis://localhost")
        traces = collector.get_traces()
        assert len(traces) == 1
        assert traces[0]["name"] == "test"
        collector.shutdown()

    @patch("pypss.instrumentation.collectors.redis_module")
    def test_connection_error(self, mock_redis_module):
        mock_redis_module.from_url.side_effect = Exception("Connection refused")
        with pytest.raises(ConnectionError):
            RedisCollector("redis://localhost")


class TestFileFIFOCollector:
    def test_file_io_batching(self, tmp_path):
        f = tmp_path / "traces.jsonl"
        # small batch size
        collector = FileFIFOCollector(str(f), batch_size=2)

        trace1 = {"name": "t1", "id": 1}
        trace2 = {"name": "t2", "id": 2}

        collector.add_trace(trace1)
        collector.add_trace(trace2)

        time.sleep(0.5)

        traces = collector.get_traces()
        assert len(traces) == 2
        assert traces[0]["name"] == "t1"
        assert traces[1]["name"] == "t2"

        collector.clear()
        assert len(collector.get_traces()) == 0
        collector.shutdown()

    def test_flush_on_interval(self, tmp_path):
        f = tmp_path / "traces_interval.jsonl"
        # Large batch, short interval
        collector = FileFIFOCollector(str(f), batch_size=100, flush_interval=0.2)

        collector.add_trace({"name": "t1"})
        time.sleep(0.5)  # Wait longer than flush interval

        traces = collector.get_traces()
        assert len(traces) == 1
        collector.shutdown()

    def test_shutdown_flushes_queue(self, tmp_path):
        f = tmp_path / "traces_shutdown.jsonl"
        collector = FileFIFOCollector(str(f), batch_size=100)

        collector.add_trace({"name": "t1"})
        # Don't wait, shutdown immediately
        collector.shutdown()

        traces = collector.get_traces()
        assert len(traces) == 1


class TestGRPCCollector:
    def test_init_raises_if_no_grpc(self):
        # Patch grpc_module
        with patch("pypss.instrumentation.collectors.grpc_module", None):
            with pytest.raises(ImportError):
                GRPCCollector("localhost:50051")

    @patch("pypss.instrumentation.collectors.trace_pb2_grpc_module")
    @patch("pypss.instrumentation.collectors.trace_pb2_module")
    @patch("pypss.instrumentation.collectors.grpc_module")
    def test_add_trace(self, mock_grpc, mock_pb2, mock_pb2_grpc):
        # Setup mocks
        mock_channel = MagicMock()
        mock_grpc.insecure_channel.return_value = mock_channel

        mock_stub_cls = MagicMock()
        mock_stub_instance = MagicMock()
        mock_pb2_grpc.TraceServiceStub = mock_stub_cls  # Mock the class
        mock_stub_cls.return_value = mock_stub_instance  # Mock the instance

        collector = GRPCCollector("localhost:50051")
        trace = {"name": "test", "duration": 1.5, "trace_id": "123"}
        collector.add_trace(trace)

        mock_stub_instance.SubmitTrace.future.assert_called_once()


class TestThreadedBatchCollectorGeneric:
    """Test generic behaviors of the base class using a concrete mock impl"""

    class MockBatchCollector(ThreadedBatchCollector):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.flushed_batches = []

        def _flush_batch(self, batch):
            self.flushed_batches.append(batch)
            if isinstance(batch[0], dict) and batch[0].get("error"):
                raise Exception("Boom")

        def get_traces(self):
            return []

        def clear(self):
            pass

    def test_queue_full_handling(self):
        # Extremely small queue
        collector = self.MockBatchCollector(max_queue_size=1, batch_size=10)
        collector.add_trace({"id": 1})

        # Queue is full (size 1). Add another.
        # Since worker is running, it might consume it fast, so we mock queue.put_nowait to raise Full
        with patch.object(collector._queue, "put_nowait", side_effect=queue.Full):
            collector.add_trace({"id": 2})  # Should not raise

        collector.shutdown()

    def test_worker_resilience(self):
        collector = self.MockBatchCollector(batch_size=1)

        # Trace that causes error in _flush_batch
        collector.add_trace({"error": True})
        collector.add_trace({"success": True})

        time.sleep(0.5)

        # Worker should still be alive and have processed the second batch
        assert len(collector.flushed_batches) >= 2
        collector.shutdown()

    def test_drain_on_shutdown(self):
        collector = self.MockBatchCollector(batch_size=100)  # Large batch
        collector.add_trace({"id": 1})
        collector.add_trace({"id": 2})
        # Don't wait, shutdown immediately
        collector.shutdown()

        # Should have flushed one batch with 2 items
        assert len(collector.flushed_batches) == 1
        assert len(collector.flushed_batches[0]) == 2


class TestCollectorMethods:
    """Test misc methods for coverage"""

    @patch("pypss.instrumentation.collectors.redis_module")
    def test_redis_clear(self, mock_redis_module):
        mock_client = MagicMock()
        mock_redis_module.from_url.return_value = mock_client
        collector = RedisCollector("redis://localhost")
        collector.clear()
        mock_client.delete.assert_called_with("pypss:traces")

    @patch("pypss.instrumentation.collectors.redis_module")
    def test_redis_methods_exceptions(self, mock_redis_module):
        # Test exception swallowing in various methods
        mock_client = MagicMock()
        mock_redis_module.from_url.return_value = mock_client
        mock_client.pipeline.side_effect = Exception("Pipeline failed")
        mock_client.delete.side_effect = Exception("Delete failed")
        mock_client.lrange.side_effect = Exception("Lrange failed")

        collector = RedisCollector("redis://localhost")

        # Should not raise (handled by base class wrapper)
        collector._flush_batch_safe([{"a": 1}])

        # Should not raise
        collector.clear()
        assert collector.get_traces() == []
        collector.shutdown()

    def test_file_read_exceptions(self, tmp_path):
        f = tmp_path / "read_fail.jsonl"
        f.write_text('{"valid": 1}\n')
        collector = FileFIFOCollector(str(f))

        # Simulate read error
        with patch("builtins.open", side_effect=OSError("Read failed")):
            assert collector.get_traces() == []

        # Simulate clear error
        with patch("builtins.open", side_effect=OSError("Write failed")):
            collector.clear()  # Should not raise

        collector.shutdown()

    def test_grpc_methods(self):
        # These are no-ops/empty returns, just ensuring they don't crash
        with (
            patch("pypss.instrumentation.collectors.grpc_module"),
            patch("pypss.instrumentation.collectors.trace_pb2_grpc_module"),
            patch("pypss.instrumentation.collectors.trace_pb2_module"),
        ):
            collector = GRPCCollector("localhost:1234")
            assert collector.get_traces() == []
            collector.clear()  # Should do nothing

            # Test add_trace exception
            with patch.object(
                collector.stub.SubmitTrace,
                "future",
                side_effect=Exception("RPC failed"),
            ):
                collector.add_trace({"id": 1})  # Should not raise

    def test_file_clear_exceptions(self, tmp_path, monkeypatch):
        # Simulate an OSError during makedirs
        monkeypatch.setattr(
            os, "makedirs", MagicMock(side_effect=OSError("Permission denied"))
        )
        # Use a path that would normally trigger makedirs
        collector = FileFIFOCollector(str(tmp_path / "non_existent_dir" / "file.jsonl"))
        # Should not raise, and should log the error
        collector.clear()
        collector.shutdown()

    def test_file_flush_exception(self, tmp_path):
        # Simulate write failure
        f = tmp_path / "fail.jsonl"
        collector = FileFIFOCollector(str(f))

        with patch("builtins.open", side_effect=OSError("Disk full")):
            collector._flush_batch([{"id": 1}])  # Should not raise

        collector.shutdown()

    def test_empty_batches(self, tmp_path):
        # Redis
        with patch(
            "pypss.instrumentation.collectors.redis_module"
        ) as mock_redis_module:
            mock_client = MagicMock()
            mock_redis_module.from_url.return_value = mock_client
            c = RedisCollector("redis://localhost")
            c._flush_batch([])  # Should return early
            mock_client.pipeline.assert_not_called()
            c.shutdown()

        # File
        f = tmp_path / "empty.jsonl"
        fc = FileFIFOCollector(str(f))
        fc._flush_batch([])  # Should return early
        assert not f.exists()
        fc.shutdown()

    def test_file_corrupt_json(self, tmp_path):
        f = tmp_path / "corrupt.jsonl"
        f.write_text('{"valid": 1}\n{invalid\n{"valid": 2}\n')

        c = FileFIFOCollector(str(f))
        traces = c.get_traces()

        assert len(traces) == 2
        assert traces[0]["valid"] == 1
        assert traces[1]["valid"] == 2
        c.shutdown()


class TestMemoryCollectorSharding:
    def test_small_buffer_no_sharding(self):
        from pypss.utils import GLOBAL_CONFIG

        orig = GLOBAL_CONFIG.max_traces
        GLOBAL_CONFIG.max_traces = 100  # Below threshold

        c = MemoryCollector()
        assert c.num_shards == 1

        GLOBAL_CONFIG.max_traces = orig

    def test_large_buffer_sharding(self):
        from pypss.utils import GLOBAL_CONFIG

        orig = GLOBAL_CONFIG.max_traces
        GLOBAL_CONFIG.max_traces = 20000  # Above threshold (1000)

        c = MemoryCollector()
        assert c.num_shards == GLOBAL_CONFIG.collector_shard_count

        GLOBAL_CONFIG.max_traces = orig

    def test_memory_collector_clear(self):
        c = MemoryCollector()
        c.add_trace({"id": 1})
        assert len(c.get_traces()) == 1
        c.clear()
        assert len(c.get_traces()) == 0


class TestModuleImports:
    def test_redis_import_error(self):
        # Simulate redis not installed
        # Since we use redis_module variable, we patch that to None
        with patch("pypss.instrumentation.collectors.redis_module", None):
            # Also ensure sys.modules doesn't interfere if logic changes back
            with patch.dict("sys.modules", {"redis": None}):
                with pytest.raises(ImportError):
                    RedisCollector("redis://localhost")

    def test_grpc_import_error(self):
        with patch("pypss.instrumentation.collectors.grpc_module", None):
            with pytest.raises(ImportError):
                GRPCCollector("localhost:1234")

    # Important: Final reload to restore state for subsequent tests if any
    def test_z_restore_module(self):
        # Since we are not reloading modules anymore but patching the module-level variable,
        # we don't strictly need to reload, but to be safe and consistent with previous approach:
        import importlib
        import pypss.instrumentation.collectors

        importlib.reload(pypss.instrumentation.collectors)
