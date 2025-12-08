import time
from typing import Optional
from ..instrumentation import global_collector


def report_kafka_lag(
    lag: int, topic: str, partition: int = 0, group_id: Optional[str] = None
):
    """
    Manually report Kafka consumer lag for stability analysis.

    This creates a system metric trace that the KafkaLagStabilityMetric plugin can analyze.

    Args:
        lag (int): The difference between Highwater Mark and Current Offset.
        topic (str): The Kafka topic name.
        partition (int): The partition number.
        group_id (str, optional): The consumer group ID.
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
    global_collector.add_trace(trace)
