from pypss.integrations.kafka import report_kafka_lag
from pypss.instrumentation import global_collector


class TestKafkaIntegration:
    def test_report_kafka_lag(self):
        global_collector.clear()

        report_kafka_lag(
            lag=50, topic="orders", partition=1, group_id="order_processor"
        )

        traces = global_collector.get_traces()
        assert len(traces) == 1
        t = traces[0]

        assert t["system_metric"] is True
        assert t["name"] == "kafka_lag_report"
        assert t["metadata"]["kafka_lag"] == 50
        assert t["metadata"]["topic"] == "orders"
        assert t["metadata"]["group_id"] == "order_processor"
