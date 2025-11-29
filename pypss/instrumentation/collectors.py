import threading
import collections
from typing import List, Dict
from ..utils import GLOBAL_CONFIG


class Collector:
    """
    Thread-safe, sharded collector to minimize lock contention.
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
