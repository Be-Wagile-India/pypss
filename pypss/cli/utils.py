import sys
from decimal import Decimal
from typing import Any, Dict, List

import click
import ijson


def _convert_decimals_to_floats(obj):
    """
    Recursively converts Decimal objects within a dictionary or list to floats.
    """
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _convert_decimals_to_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_decimals_to_floats(elem) for elem in obj]
    return obj


def load_traces(trace_file: str) -> List[Dict[str, Any]]:
    """Loads traces from a JSON file."""
    traces = []
    try:
        with open(trace_file, "rb") as f:
            try:
                first_char = f.read(1)
                f.seek(0)
            except Exception:
                first_char = b""

            if first_char == b"{":
                raw_traces = list(ijson.items(f, "traces.item"))
            elif first_char == b"[":
                raw_traces = list(ijson.items(f, "item"))
            else:
                raw_traces = []

            traces = [_convert_decimals_to_floats(trace) for trace in raw_traces]

    except Exception as e:
        click.echo(f"Error reading trace file: {e}", err=True)
        sys.exit(1)
    return traces
