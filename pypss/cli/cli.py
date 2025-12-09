import time
import click
import ijson  # type: ignore
import pypss
from ..core import compute_pss_from_traces, generate_advisor_report
from ..core.llm_advisor import get_llm_diagnosis
from .reporting import render_report_json, render_report_text
from .html_report import render_report_html
from .runner import run_with_instrumentation
from .discovery import get_module_score_breakdown
from .tuning import tune
from .utils import load_traces  # Import load_traces from utils
from ..ml.detector import PatternDetector  # Import PatternDetector
from ..utils.config import GLOBAL_CONFIG
from ..plugins import load_plugins
import json
import sys
import os


@click.group()
def main():
    """pypss - Python Program Stability Score CLI"""
    pass


main.add_command(tune)


@main.command()
@click.option(
    "--baseline-file",
    type=click.Path(exists=True),
    required=True,
    help="Path to the JSON trace file containing baseline (normal) behavior.",
)
@click.option(
    "--target-file",
    type=click.Path(exists=True),
    required=True,
    help="Path to the JSON trace file containing traces to detect anomalies in.",
)
@click.option(
    "--contamination",
    type=float,
    default=0.1,
    help="The proportion of outliers in the baseline dataset. Used by IsolationForest.",
)
@click.option(
    "--random-state",
    type=int,
    default=42,
    help="Random seed for reproducibility of ML model training.",
)
def ml_detect(baseline_file, target_file, contamination, random_state):
    """
    Detects anomalous patterns in target traces using a Machine Learning model
    trained on baseline traces.
    """
    pypss.init()  # Ensure pypss components are initialized

    click.echo(f"📊 Loading baseline traces from {baseline_file}...")
    baseline_traces = load_traces(baseline_file)
    if not baseline_traces:
        click.echo(
            "⚠️  No traces found in baseline file. Cannot train ML model.", err=True
        )
        sys.exit(1)
    click.echo(f"   Loaded {len(baseline_traces)} baseline traces.")

    click.echo("🔍 Initializing and fitting PatternDetector model...")
    try:
        detector = PatternDetector(
            contamination=contamination, random_state=random_state
        )
        detector.fit(baseline_traces)
        click.echo("   Model fitted successfully to baseline traces.")
    except ImportError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo(
            "Please install scikit-learn to use ML features: pip install scikit-learn",
            err=True,
        )
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error fitting ML model: {e}", err=True)
        sys.exit(1)

    click.echo(
        f"\n🔬 Loading target traces from {target_file} for anomaly detection..."
    )
    target_traces = load_traces(target_file)
    if not target_traces:
        click.echo("⚠️  No traces found in target file. Nothing to analyze.", err=True)
        sys.exit(0)
    click.echo(f"   Loaded {len(target_traces)} target traces.")

    click.echo("\n🔎 Predicting anomalies...")
    predictions = detector.predict_anomalies(target_traces)
    scores = detector.anomaly_score(target_traces)

    anomalies_found = False
    for i, (is_anomaly, score) in enumerate(zip(predictions, scores)):
        trace_name = target_traces[i].get("name", f"Trace #{i}")
        if is_anomaly:
            anomalies_found = True
            click.echo(f"  ❌ Anomaly detected in '{trace_name}' (Score: {score:.2f})")
        # else:
        # click.echo(f"  ✅ Normal: '{trace_name}' (Score: {score:.2f})")

    if not anomalies_found:
        click.echo("✅ No significant anomalies detected in target traces.")
    else:
        click.echo("\nSummary: Anomalies were detected.")

    # Optionally, you might want to save the model or the results.
    # Not implemented in this basic CLI integration.


# Add the new command to the main group
main.add_command(ml_detect)


@main.command()
@click.option("--limit", default=10, help="Number of historical records to show.")
@click.option("--days", type=int, help="Show history for the last N days.")
@click.option(
    "--export",
    type=click.Choice(["csv", "json"]),
    help="Export history to file format.",
)
@click.option(
    "--db-path",
    default=GLOBAL_CONFIG.storage_uri,
    help="Path to the SQLite history database.",
)
def history(limit, db_path, days, export):
    """Show historical PSS trends."""
    from ..storage.sqlite import SQLiteStorage

    storage = SQLiteStorage(db_path=db_path)
    history_data = storage.get_history(limit=limit, days=days)

    if not history_data:
        if not export:
            click.echo("No history found.")
            return
        # If exporting and no history_data, proceed to export logic
        # which will output headers and no rows.

    if export:
        if export == "json":
            click.echo(json.dumps(history_data, indent=2))
        elif export == "csv":
            import csv
            import io

            output = io.StringIO()
            all_keys = ["id", "timestamp", "pss", "ts", "ms", "ev", "be", "cc", "meta"]
            writer = csv.DictWriter(output, fieldnames=all_keys)
            writer.writeheader()

            flat_data = []
            for row in history_data:
                r = row.copy()
                r["meta"] = json.dumps(r["meta"])
                flat_data.append(r)

            if flat_data:
                writer.writerows(flat_data)
            click.echo(output.getvalue())
        return

    click.echo(f"\n📜 Historical PSS Trends (Last {limit} runs)")
    click.echo("=" * 60)
    click.echo(
        f"{'Timestamp':<20} | {'PSS':<5} | {'TS':<4} | {'MS':<4} | {'EV':<4} | {'BE':<4} | {'CC':<4}"
    )
    click.echo("-" * 60)

    for item in history_data:
        ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item["timestamp"]))
        click.echo(
            f"{ts_str:<20} | {int(item['pss']):<5} | {item['ts']:.2f} | {item['ms']:.2f} | {item['ev']:.2f} | {item['be']:.2f} | {item['cc']:.2f}"
        )
    click.echo("=" * 60)


@main.command()
@click.argument("script", type=click.Path(exists=True))
@click.option("--output", type=click.Path(), help="Path to save the output report.")
@click.option("--html", is_flag=True, help="Generate an HTML dashboard.")
@click.option(
    "--store-history",
    is_flag=True,
    help="Store the PSS score in the local history database.",
)
def run(script, output, html, store_history):
    """Run a Python script with auto-instrumentation and report stability."""

    # Load plugins dynamically
    if GLOBAL_CONFIG.plugins:
        load_plugins(GLOBAL_CONFIG.plugins)

    # Run the script with our magic
    run_with_instrumentation(script, os.getcwd())

    # Collect results
    collector = pypss.get_global_collector()
    if not collector:
        click.echo("\n⚠️  PyPSS collector not initialized. Did pypss.init() run?")
        return

    traces = collector.get_traces()
    if not traces:
        click.echo("\n⚠️  No traces collected. Did the application run long enough?")
        return

    # 1. Overall Report
    overall_report = compute_pss_from_traces(traces)
    click.echo("\n" + render_report_text(overall_report))

    # 2. Per-Module Breakdown
    click.echo("\n📦 Module Stability Breakdown")
    click.echo("===========================")
    module_scores = get_module_score_breakdown(traces)

    for module, score_data in module_scores.items():
        pss = score_data["pss"]
        # Color coding for CLI
        if pss >= 90:
            indicator = "🟢"
        elif pss >= 70:
            indicator = "🟡"
        else:
            indicator = "🔴"
        click.echo(f"{indicator} {module:<30} PSS: {pss}/100")

    # Save if requested
    if output:
        output_dir = os.path.dirname(output)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        if html:
            advisor = generate_advisor_report(overall_report)
            content = render_report_html(overall_report, advisor)
            with open(output, "w") as f:
                f.write(content)
        else:
            full_data = {
                "overall": overall_report,
                "modules": module_scores,
                "traces": traces,
            }
            with open(output, "w") as f:
                json.dump(full_data, f, indent=2)
        click.echo(f"\nReport saved to {output}")

    history_data = None
    if store_history:
        from ..storage import get_storage_backend, check_regression

        try:
            storage_config = {
                "storage_backend": GLOBAL_CONFIG.storage_backend,
                "storage_uri": GLOBAL_CONFIG.storage_uri,
            }
            storage = get_storage_backend(storage_config)

            # Fetch history for regression checking
            history_data = storage.get_history(
                limit=GLOBAL_CONFIG.regression_history_limit
            )

            # Check regression BEFORE saving current run
            warning = check_regression(
                overall_report,
                storage,
                limit=GLOBAL_CONFIG.regression_history_limit,
                threshold_drop=GLOBAL_CONFIG.regression_threshold_drop,
            )
            if warning:
                click.echo(f"\n{warning}")

            storage.save(overall_report, meta={"script": script})
            click.echo("\n✅ PSS Score stored in history.")
        except Exception as e:
            click.echo(f"\n⚠️  Failed to store history: {e}")

    # Alerting
    from ..alerts.engine import AlertEngine

    engine = AlertEngine()
    alerts = engine.run(overall_report, history=history_data)
    if alerts:
        click.echo(f"\n🔔 {len(alerts)} Alerts triggered and sent.")


@main.command()
@click.option(
    "--trace-file",
    type=click.Path(exists=True),
    required=True,
    help="Path to the JSON trace file.",
)
@click.option("--output", type=click.Path(), help="Path to save the output report.")
@click.option("--html", is_flag=True, help="Generate an HTML dashboard.")
@click.option(
    "--fail-if-below",
    type=int,
    help="Return non-zero exit code if PSS is below this threshold.",
)
@click.option(
    "--store-history",
    is_flag=True,
    help="Store the PSS score in the local history database.",
)
def analyze(trace_file, output, html, fail_if_below, store_history):
    """Compute PSS from a trace file."""

    # Load plugins dynamically
    if GLOBAL_CONFIG.plugins:
        load_plugins(GLOBAL_CONFIG.plugins)

    try:
        # Use streaming JSON parser to handle large files
        with open(trace_file, "rb") as f:
            # Peek to determine structure
            try:
                first_char = f.read(1)
                f.seek(0)
            except Exception:
                # Empty file
                first_char = b""

            if first_char == b"{":
                # Assume {"traces": [...]}
                traces = ijson.items(f, "traces.item")
            elif first_char == b"[":
                # Assume [...]
                traces = ijson.items(f, "item")
            else:
                # Fallback or empty
                traces = []

            report = compute_pss_from_traces(traces)

    except Exception as e:
        click.echo(f"Error reading/analyzing trace file: {e}", err=True)
        sys.exit(1)

    report_text = render_report_text(report)
    click.echo(report_text)

    if output:
        output_dir = os.path.dirname(output)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        if html:
            advisor = generate_advisor_report(report)
            content = render_report_html(report, advisor)
            with open(output, "w") as f:
                f.write(content)
        else:
            with open(output, "w") as f:
                f.write(render_report_json(report))
        click.echo(f"Report saved to {output}")

    history_data = None
    if store_history:
        from ..storage import get_storage_backend, check_regression

        try:
            storage_config = {
                "storage_backend": GLOBAL_CONFIG.storage_backend,
                "storage_uri": GLOBAL_CONFIG.storage_uri,
            }
            storage = get_storage_backend(storage_config)

            # Fetch history for regression checking
            history_data = storage.get_history(
                limit=GLOBAL_CONFIG.regression_history_limit
            )

            # Check regression BEFORE saving current run
            warning = check_regression(
                report,
                storage,
                limit=GLOBAL_CONFIG.regression_history_limit,
                threshold_drop=GLOBAL_CONFIG.regression_threshold_drop,
            )
            if warning:
                click.echo(f"\n{warning}")

            storage.save(report, meta={"trace_file": trace_file})
            click.echo("\n✅ PSS Score stored in history.")
        except Exception as e:
            click.echo(f"\n⚠️  Failed to store history: {e}")

    # Alerting
    from ..alerts.engine import AlertEngine

    engine = AlertEngine()
    alerts = engine.run(report, history=history_data)
    if alerts:
        click.echo(f"\n🔔 {len(alerts)} Alerts triggered and sent.")

    if fail_if_below is not None:
        if report["pss"] < fail_if_below:
            click.echo(
                f"PSS {report['pss']} is below threshold {fail_if_below}. Failing."
            )
            sys.exit(1)


@main.command()
@click.option(
    "--trace-file",
    type=click.Path(exists=True),
    required=True,
    help="Path to the JSON trace file.",
)
@click.option(
    "--provider",
    type=click.Choice(["openai", "ollama"]),
    default="openai",
    help="LLM Provider for diagnosis.",
)
@click.option("--api-key", envvar="OPENAI_API_KEY", help="API Key for OpenAI.")
def diagnose(trace_file, provider, api_key):
    """
    Ask an AI to diagnose the root cause of instability from traces.
    """
    try:
        with open(trace_file, "rb") as f:
            # Peek to determine structure, similar to analyze command
            try:
                first_char = f.read(1)
                f.seek(0)
            except Exception:
                first_char = b""

            if first_char == b"{":
                traces = list(ijson.items(f, "traces.item"))
            elif first_char == b"[":
                traces = list(ijson.items(f, "item"))
            else:
                traces = []
    except Exception as e:
        click.echo(f"Error reading trace file: {e}", err=True)
        sys.exit(1)

    if not traces:
        click.echo("No traces found in the file to diagnose.")
        # Do not exit, allow command to proceed with empty traces
        # This is consistent with `analyze` and allows mocks to be called in tests.

    click.echo(f"🧠 analyzing {len(traces)} traces with {provider.upper()}...")

    diagnosis = get_llm_diagnosis(traces, provider=provider, api_key=api_key)

    click.echo("\n================= AI Diagnosis =================")
    click.echo(diagnosis)
    click.echo("================================================")


@main.command()
@click.argument(
    "trace_file", type=click.Path(), default=GLOBAL_CONFIG.default_trace_file
)
def board(trace_file):
    """


    Launch the interactive Stability Dashboard.


    """

    import subprocess

    try:
        # check if modules are available (optional check, as subprocess would fail too but clearer here)

        import nicegui  # type: ignore # noqa: F401
        import plotly  # type: ignore # noqa: F401
        import pandas  # noqa: F401

    except ImportError:
        click.echo("⚠️  Dashboard dependencies missing.")

        click.echo("Run: pip install pypss[dashboard]")

        sys.exit(1)

    # Launch as subprocess to avoid event loop/signal conflicts between Click and NiceGUI/Uvicorn
    cmd = [sys.executable, "-m", "pypss.board.app", trace_file]

    try:
        # We don't capture output so that NiceGUI's startup logs (like the URL) are visible to the user
        result = subprocess.run(cmd, check=False)

        if result.returncode != 0:
            click.echo(f"Dashboard crashed with exit code {result.returncode}")
            sys.exit(result.returncode)

    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
