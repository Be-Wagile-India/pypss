import click
import ijson
import sys
from typing import List, Dict, Any


def load_traces(trace_file: str) -> List[Dict[str, Any]]:
    """Loads traces from a JSON file."""
    traces = []
    try:
        with open(trace_file, "rb") as f:
            # Peek to determine structure
            try:
                first_char = f.read(1)
                f.seek(0)
            except Exception:
                first_char = b""

            if first_char == b"{":
                # Assume {"traces": [...]}
                traces = list(ijson.items(f, "traces.item"))
            elif first_char == b"[":
                # Assume [...]
                traces = list(ijson.items(f, "item"))
            else:
                traces = []
    except Exception as e:
        click.echo(f"Error reading trace file: {e}", err=True)
        sys.exit(1)
    return traces
