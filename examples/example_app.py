# Example application using pypss
import json
import random
import time

from pypss import (
    compute_pss_from_traces,
    global_collector,
    init,  # Import the init function
    monitor_function,
    render_report_text,
)


# Simulate a stable function
@monitor_function("stable_op")
def stable_operation():
    time.sleep(0.01)


# Simulate an unstable function (jittery timing, occasional errors)
@monitor_function("unstable_op", branch_tag="main_path")
def unstable_operation():
    # Timing jitter
    sleep_time = random.uniform(0.01, 0.10)
    time.sleep(sleep_time)

    # Error volatility
    if random.random() < 0.2:
        raise ValueError("Random failure!")


def main():
    # Initialize pypss components
    init()  # Call init() at the beginning of the application

    print("Running stable operations...")
    for _ in range(20):
        stable_operation()

    print("Running unstable operations (expecting errors)...")
    for _ in range(20):
        try:
            unstable_operation()
        except ValueError:
            pass  # Ignore expected errors

    traces = global_collector.get_traces()

    # Save traces to file for CLI testing
    with open("traces.json", "w") as f:
        json.dump(traces, f, indent=2)
    print("Saved traces to traces.json")

    report = compute_pss_from_traces(traces)
    print("\n" + render_report_text(report))


if __name__ == "__main__":
    main()
