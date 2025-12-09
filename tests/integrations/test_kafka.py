from pypss.integrations.kafka import report_kafka_lag
import pypss


class TestKafkaIntegration:
    def test_report_kafka_lag(self):
        pypss.init()
        collector = pypss.get_global_collector()
        collector.clear()

        report_kafka_lag(
            lag=50, topic="orders", partition=1, group_id="order_processor"
        )

        traces = collector.get_traces()
        assert len(traces) == 1
        t = traces[0]

        assert t["system_metric"] is True
        assert t["name"] == "kafka_lag_report"
        assert t["metadata"]["kafka_lag"] == 50
        assert t["metadata"]["topic"] == "orders"
        assert t["metadata"]["group_id"] == "order_processor"
