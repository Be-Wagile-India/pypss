import threading
import time
import json
import os
import shutil
import logging
from datetime import datetime
from typing import Optional
from .collectors import Collector
from pypss.utils.config import GLOBAL_CONFIG

logger = logging.getLogger(__name__)


class AutoDumper:
    """
    Background thread that periodically dumps collector traces to a file.
    Performs atomic writes to ensure readers (like the dashboard) don't see partial files.
    Supports file rotation to prevent data loss while keeping the active file manageable.
    """

    def __init__(
        self,
        collector: Collector,
        file_path: str,
        interval: float = GLOBAL_CONFIG.background_dump_interval,
        rotate_interval: Optional[float] = None,
    ):
        self.collector = collector
        self.file_path = file_path
        self.interval = interval
        self.rotate_interval = rotate_interval
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._last_rotate = time.time()

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        # Ensure we dump one last time on stop
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self.dump()

    def _run(self):
        while not self._stop_event.is_set():
            # Check for rotation
            if self.rotate_interval and (
                time.time() - self._last_rotate > self.rotate_interval
            ):
                self.rotate()
                self._last_rotate = time.time()

            # Sleep in small chunks to allow faster stopping
            for _ in range(int(self.interval * 10)):
                if self._stop_event.is_set():
                    break
                time.sleep(0.1)

            if not self._stop_event.is_set():
                self.dump()

    def dump(self):
        new_traces = self.collector.get_traces()
        temp_path = f"{self.file_path}.tmp"

        try:
            # Load existing traces if file exists
            existing_traces = []
            if os.path.exists(self.file_path):
                try:
                    with open(self.file_path, "r") as f:
                        existing_data = json.load(f)
                        if (
                            isinstance(existing_data, dict)
                            and "traces" in existing_data
                        ):
                            existing_traces = existing_data.get("traces", [])
                        elif isinstance(existing_data, list):
                            existing_traces = existing_data
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(
                        f"Could not load existing traces from {self.file_path}: {e}"
                    )
                    existing_traces = []

            # Using trace_id for robust deduplication, including None for traces without an ID
            existing_keys = {t.get("trace_id") for t in existing_traces}

            # Append only new traces that don't already exist
            combined_traces = existing_traces.copy()
            for trace in new_traces:
                trace_id = trace.get("trace_id")
                if trace_id not in existing_keys:
                    combined_traces.append(trace)
                    existing_keys.add(trace_id)

            # Sort by timestamp to maintain chronological order
            combined_traces.sort(key=lambda x: x.get("timestamp", 0))

            # Wrap in a dict structure for metadata support
            data = {
                "last_updated": time.time(),
                "trace_count": len(combined_traces),
                "traces": combined_traces,
            }

            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2)

            # Atomic replacement
            os.replace(temp_path, self.file_path)

        except Exception as e:
            logger.error(f"AutoDumper failed to dump traces to {self.file_path}: {e}")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError as cleanup_error:
                    logger.debug(
                        f"Failed to remove temp file {temp_path}: {cleanup_error}"
                    )

    def rotate(self):
        """
        Rotates the current trace file to an archive and clears memory.
        """
        if not os.path.exists(self.file_path):
            return

        archive_dir = os.path.join(
            os.path.dirname(self.file_path), GLOBAL_CONFIG.background_archive_dir
        )
        os.makedirs(archive_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.basename(self.file_path)
        archive_path = os.path.join(
            archive_dir, f"{filename.replace('.json', '')}_{timestamp}.json"
        )

        try:
            logger.info(f"AutoDumper rotating traces to {archive_path}")
            shutil.move(self.file_path, archive_path)
            # Clear the collector memory to start fresh for the new file
            self.collector.clear()
            # Trigger an immediate dump to reset the file
            self.dump()
        except Exception as e:
            logger.error(f"AutoDumper rotation failed: {e}")
