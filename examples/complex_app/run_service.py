# examples/complex_app/run_service.py
import os
import argparse
from complex_web_service import run_service_simulation
from pypss.utils.utils import parse_time_string


def main():
    parser = argparse.ArgumentParser(
        description="Run a complex web service simulation with PyPSS instrumentation."
    )
    parser.add_argument(
        "--num_requests",
        type=int,
        default=50,
        help="Number of simulated requests to process.",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="output",
        help="Directory to save the trace file.",
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run indefinitely.",
    )
    parser.add_argument(
        "--dump_interval",
        type=str,
        default=None,
        help="Interval to auto-dump traces (e.g., '5s', '2m', '1h').",
    )
    parser.add_argument(
        "--rotate_interval",
        type=str,
        default=None,
        help="Interval to rotate trace file to archive (e.g., '1h', '1d').",
    )
    args = parser.parse_args()

    script_dir = os.path.dirname(__file__)
    output_path = os.path.join(script_dir, args.output_dir)
    os.makedirs(output_path, exist_ok=True)
    trace_file = os.path.join(output_path, "complex_app_traces.json")

    # Parse time intervals
    parsed_dump_interval = None
    if args.dump_interval:
        try:
            parsed_dump_interval = parse_time_string(args.dump_interval)
        except ValueError as e:
            print(f"Error: Invalid dump_interval format: {e}")
            return

    parsed_rotate_interval = None
    if args.rotate_interval:
        try:
            parsed_rotate_interval = parse_time_string(args.rotate_interval)
        except ValueError as e:
            print(f"Error: Invalid rotate_interval format: {e}")
            return

    print(f"Running complex service simulation with {args.num_requests} requests...")
    run_service_simulation(
        num_requests=args.num_requests,
        trace_file=trace_file,
        continuous=args.continuous,
        dump_interval=parsed_dump_interval,
        rotate_interval=parsed_rotate_interval,
    )


if __name__ == "__main__":
    main()
