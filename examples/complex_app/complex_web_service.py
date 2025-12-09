# examples/complex_app/complex_web_service.py
import random
import time
import os
from typing import Optional, List, Any
import pypss
from pypss.instrumentation import (
    monitor_function,
    monitor_block,
    AutoDumper,
)
from pypss.core import compute_pss_from_traces

# Simulate some memory usage
_memory_hog: List[Any] = []


@monitor_function("auth_check", module_name="auth_service")
def auth_check(user_id):
    """Simulates authentication check."""
    time.sleep(random.uniform(0.005, 0.02))
    if random.random() < 0.01:
        raise ValueError("Authentication failed")


@monitor_function("check_cache", module_name="cache_service")
def check_cache(key):
    """Simulates cache lookup."""
    time.sleep(random.uniform(0.001, 0.005))
    return random.random() < 0.7  # 70% hit rate


@monitor_function("query_database", module_name="database_service")
def query_database(query):
    """Simulates database query."""
    time.sleep(random.uniform(0.02, 0.1))
    if random.random() < 0.05:
        time.sleep(0.2)  # Slow query


@monitor_function("process_payment", module_name="payment_service")
def process_payment(amount):
    """Simulates payment processing."""
    time.sleep(random.uniform(0.1, 0.5))
    if random.random() < 0.05:
        raise ConnectionError("Payment gateway timeout")


@monitor_function("send_email_notification", module_name="notification_service")
def send_email_notification(email):
    """Simulates sending email."""
    time.sleep(random.uniform(0.05, 0.15))


@monitor_function("update_search_index", module_name="search_service")
def update_search_index(doc_id):
    """Simulates updating search index."""
    time.sleep(random.uniform(0.01, 0.05))


@monitor_function("process_image", module_name="image_processing")
def process_image(image_id):
    """Simulates image processing."""
    with monitor_block("image_resize_cpu_task", module_name="image_processing"):
        time.sleep(random.uniform(0.1, 0.3))


@monitor_function("log_audit_event", module_name="audit_service")
def log_audit_event(event):
    """Simulates logging."""
    time.sleep(random.uniform(0.001, 0.01))


@monitor_function("track_analytics", module_name="analytics_service")
def track_analytics(data):
    """Simulates analytics tracking."""
    time.sleep(random.uniform(0.005, 0.02))


@monitor_function("process_request", module_name="api_gateway")
def process_request(request_id: int):
    """Simulates processing a web request with varying stability."""
    print(f"[{request_id}] Processing request...")
    time.sleep(random.uniform(0.01, 0.05))
    return {"status": "success", "request_id": request_id}


@monitor_function("background_job", module_name="background_worker")
def run_background_job():
    """Simulates a background job that occasionally waits for resources."""
    print("[BG] Running background job...")
    time.sleep(random.uniform(0.02, 0.08))

    # Background jobs might also do DB work or Indexing
    if random.random() < 0.5:
        query_database("SELECT * FROM jobs")

    if random.random() < 0.3:
        update_search_index("job_data")

    if random.random() < 0.1:  # 10% chance of waiting
        wait_time = random.uniform(0.1, 0.5)
        # Update wait_time for the last trace in the collector (manual context)
        # if global_collector.get_traces():
        #     global_collector.get_traces()[-1]["wait_time"] = wait_time # Simulating custom attribute
        time.sleep(wait_time)

    # Simulate a small chance of error in background
    if random.random() < 0.02:
        raise ConnectionError("Simulated background job failure")

    print("[BG] Background job complete.")


def run_service_simulation(
    num_requests: int = 100,
    trace_file: str = "traces.json",
    continuous: bool = False,
    dump_interval: Optional[float] = None,
    rotate_interval: Optional[float] = None,
):
    """
    Runs a simulation of the web service and saves the traces.
    """
    global _memory_hog
    _memory_hog = []  # Clear memory hog for each simulation run

    # Get the global collector (ensure pypss.init() is called by the test fixture)
    collector = pypss.get_global_collector()
    collector.clear()  # Ensure a clean start

    # --- Removed: Resume from existing traces logic ---

    dumper = None
    if dump_interval:
        print(f"Auto-dumping traces every {dump_interval}s to {trace_file}")
        dumper = AutoDumper(
            collector,  # Use the retrieved collector
            trace_file,
            interval=dump_interval,
            rotate_interval=rotate_interval,
        )
        dumper.start()

    try:
        print("Starting service simulation...")
        if continuous:
            print("Running in continuous mode (Press Ctrl+C to stop)...")
            i = 0
            while True:
                try:
                    if i % 10 == 0:  # Periodically run a background job
                        run_background_job()
                    process_request(i)
                except (ValueError, ConnectionError) as e:
                    print(f"[{i}] Request/Job failed: {e}")

                time.sleep(random.uniform(0.005, 0.02))  # Small delay between requests
                i += 1
                if not continuous and i >= num_requests:
                    break
        else:
            for i in range(num_requests):
                try:
                    if i % 10 == 0:  # Periodically run a background job
                        run_background_job()
                    process_request(i)
                except (ValueError, ConnectionError) as e:
                    print(f"[{i}] Request failed: {e}")
                time.sleep(random.uniform(0.005, 0.02))  # Small delay between requests

    except KeyboardInterrupt:
        print("\nSimulation stopped by user.")
    finally:
        if dumper:
            print("Stopping auto-dumper...")
            dumper.stop()

    traces = collector.get_traces()  # Use the retrieved collector
    # Final write if not using dumper, or just to be sure
    if not dumper:
        with open(trace_file, "w") as f:
            import json

            json.dump({"traces": traces}, f, indent=2)

    print(f"Simulation finished. Traces saved to {trace_file}")

    # Optionally, compute PSS and print report
    if traces:
        report = compute_pss_from_traces(traces)
        print("\n--- PSS Report ---")
        print(f"Overall PSS: {report['pss']}/100")
        print("Breakdown:")
        for metric, score in report["breakdown"].items():
            print(f"  {metric.replace('_', ' ').title()}: {score:.2f}")
        print("------------------")

    return traces


if __name__ == "__main__":
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)
    trace_path = os.path.join(output_dir, "complex_app_traces.json")
    run_service_simulation(num_requests=42, trace_file=trace_path)
