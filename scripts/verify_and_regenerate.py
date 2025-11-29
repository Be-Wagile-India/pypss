import os
import subprocess
import json
import sys

# Determine the project root (one level up from this script)
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)

# Change working directory to project root
os.chdir(project_root)
print(f"Working in project root: {project_root}")

# Forcefully delete the old data
output_dir = "examples/complex_app/output"
trace_file = os.path.join(output_dir, "complex_app_traces.json")
if os.path.exists(trace_file):
    os.remove(trace_file)
    print(f"Forcefully deleted {trace_file}")

# Regenerate the data
print("Regenerating trace data...")
# Use sys.executable to ensure we use the same python interpreter
subprocess.run([sys.executable, "examples/complex_app/complex_web_service.py"])

# Verify the new data
print("\n--- Verifying new trace data ---")
if os.path.exists(trace_file):
    with open(trace_file, "r") as f:
        data = json.load(f)
        trace_count = len(data.get("traces", []))
        print(f"Found {trace_count} traces in the new file.")
else:
    print(f"Error: Trace file {trace_file} was not generated.")
