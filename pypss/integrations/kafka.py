import time
from typing import Optional

import pypss


def report_kafka_lag(lag: int, topic: str, partition: int = 0, group_id: Optional[str] = None):
    """
    Manually report Kafka consumer lag for stability analysis.
    """
    trace = {
        "system_metric": True,
        "timestamp": time.time(),
        "name": "kafka_lag_report",
        "metadata": {
            "kafka_lag": lag,
            "topic": topic,
            "partition": partition,
            "group_id": group_id or "unknown",
        },
    }
    collector = pypss.get_global_collector()
    if collector:
        collector.add_trace(trace)
