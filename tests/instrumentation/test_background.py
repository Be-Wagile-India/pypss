import os
import json
import time
import pytest
from pypss.instrumentation.background import AutoDumper
from pypss.instrumentation.collectors import Collector


class TestAutoDumper:
    @pytest.fixture
    def collector(self):
        return Collector()

    @pytest.fixture
    def temp_file(self, tmp_path):
        return str(tmp_path / "traces.json")

    def test_dump_writes_file(self, collector, temp_file):
        collector.add_trace({"id": 1})
        dumper = AutoDumper(collector, temp_file, interval=0.1)

        dumper.dump()

        assert os.path.exists(temp_file)
        with open(temp_file, "r") as f:
            data = json.load(f)
            assert data["trace_count"] == 1
            assert data["traces"][0]["id"] == 1

    def test_background_thread_runs_and_dumps(self, collector, temp_file):
        collector.add_trace({"id": 1})
        # Use short interval
        dumper = AutoDumper(collector, temp_file, interval=0.1)
        dumper.start()

        try:
            time.sleep(0.3)  # Wait for at least one dump
            assert os.path.exists(temp_file)
        finally:
            dumper.stop()

        with open(temp_file, "r") as f:
            data = json.load(f)
            assert len(data["traces"]) == 1

    def test_rotate(self, collector, temp_file):
        # Create a dummy file first
        with open(temp_file, "w") as f:
            json.dump({"traces": [{"id": "old"}]}, f)

        collector.add_trace({"id": "new"})
        dumper = AutoDumper(collector, temp_file, interval=1.0, rotate_interval=0.1)

        # Manually trigger rotation logic via _run would wait too long or depend on timing
        # So we test rotate() directly
        dumper.rotate()

        # Check archive exists
        archive_dir = os.path.join(os.path.dirname(temp_file), "archive")
        assert os.path.exists(archive_dir)
        archives = os.listdir(archive_dir)
        assert len(archives) == 1

        # Check collector is cleared
        assert len(collector.get_traces()) == 0

        # Check main file is reset (because rotate calls dump() which dumps empty collector)
        with open(temp_file, "r") as f:
            data = json.load(f)
            assert len(data["traces"]) == 0

    @pytest.mark.filterwarnings(
        "ignore:coroutine 'AsyncMockMixin._execute_mock_call' was never awaited:RuntimeWarning"
    )
    def test_rotation_trigger_in_thread(self, collector, temp_file):
        # Create a dummy file first so rotation has something to rotate
        with open(temp_file, "w") as f:
            json.dump({"traces": []}, f)

        collector.add_trace({"id": 1})
        # Small rotate interval
        dumper = AutoDumper(collector, temp_file, interval=0.1, rotate_interval=0.2)
        dumper._last_rotate = time.time() - 0.3  # Force rotation due

        dumper.start()
        try:
            time.sleep(0.3)
        finally:
            dumper.stop()

        # Archive should exist
        archive_dir = os.path.join(os.path.dirname(temp_file), "archive")
        if os.path.exists(archive_dir):
            assert len(os.listdir(archive_dir)) >= 1
        else:
            pytest.fail("Archive directory not created by rotation")

    def test_dump_exception_handling(self, collector):
        # Invalid path to force exception
        dumper = AutoDumper(collector, "/invalid/path/traces.json")
        # Should not raise
        dumper.dump()
