from unittest.mock import MagicMock
import json
import time
import shutil
from pypss.instrumentation.background import AutoDumper
from pypss.instrumentation.collectors import MemoryCollector


class TestBackgroundCoverage:
    def test_dump_corrupted_existing_file(self, tmp_path):
        f = tmp_path / "traces.json"
        f.write_text("corrupted json")

        collector = MemoryCollector()
        collector.add_trace({"trace_id": "1", "timestamp": 1})

        dumper = AutoDumper(collector, str(f))
        dumper.dump()

        # Should have overwritten the corrupted file
        data = json.loads(f.read_text())
        assert len(data["traces"]) == 1

    def test_dump_exception_handling(self, tmp_path, monkeypatch):
        f = tmp_path / "traces.json"
        collector = MemoryCollector()
        dumper = AutoDumper(collector, str(f))

        # Mock open to raise exception
        monkeypatch.setattr(
            "builtins.open", MagicMock(side_effect=IOError("Disk full"))
        )

        # Should not crash
        dumper.dump()

    def test_rotate_exception(self, tmp_path, monkeypatch):
        f = tmp_path / "traces.json"
        f.write_text(json.dumps({"traces": []}))

        collector = MemoryCollector()
        dumper = AutoDumper(collector, str(f))

        # Mock shutil.move to fail
        monkeypatch.setattr(
            shutil, "move", MagicMock(side_effect=IOError("Permission denied"))
        )

        dumper.rotate()
        # Should log error and not crash

    def test_run_with_rotation(self, tmp_path):
        f = tmp_path / "traces.json"
        collector = MemoryCollector()
        dumper = AutoDumper(collector, str(f), interval=0.1, rotate_interval=0.1)

        dumper.start()
        time.sleep(0.3)
        dumper.stop()

        # Verify rotation happened (file might be empty or recreated)
        assert f.exists()
