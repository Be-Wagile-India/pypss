import click
import ijson
from ..core import compute_pss_from_traces, generate_advisor_report
from ..core.llm_advisor import get_llm_diagnosis
from .reporting import render_report_json, render_report_text
from .html_report import render_report_html
from ..instrumentation import global_collector
from .runner import run_with_instrumentation
from .discovery import get_module_score_breakdown
from ..utils.config import GLOBAL_CONFIG
import json
import sys
import os


@click.group()
def main():
    """pypss - Python Program Stability Score CLI"""
    pass


@main.command()
@click.argument("script", type=click.Path(exists=True))
@click.option("--output", type=click.Path(), help="Path to save the output report.")
@click.option("--html", is_flag=True, help="Generate an HTML dashboard.")
def run(script, output, html):
    """Run a Python script with auto-instrumentation and report stability."""

    # Run the script with our magic
    run_with_instrumentation(script, os.getcwd())

    # Collect results
    traces = global_collector.get_traces()
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
def analyze(trace_file, output, html, fail_if_below):
    """Compute PSS from a trace file."""
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
        if html:
            advisor = generate_advisor_report(report)
            content = render_report_html(report, advisor)
            with open(output, "w") as f:
                f.write(content)
        else:
            with open(output, "w") as f:
                f.write(render_report_json(report))
        click.echo(f"Report saved to {output}")

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

        import nicegui  # noqa: F401

        import plotly  # noqa: F401

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
