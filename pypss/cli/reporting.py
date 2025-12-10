import json

from ..core import generate_advisor_report


def render_report_json(report):
    return json.dumps(report, indent=2)


def render_report_text(report):
    lines = [
        "Python Program Stability Score (PSS) Report",
        "===========================================",
        f"PSS: {report.get('pss', 0)}/100",
        "",
        "Breakdown:",
    ]
    breakdown = report.get("breakdown", {})
    for key, value in breakdown.items():
        if len(key) <= 3:
            formatted_key = key.upper()
        else:
            formatted_key = key.replace("_", " ").title()
        lines.append(f"  - {formatted_key}: {value:.2f}")

    lines.append(generate_advisor_report(report))

    return "\n".join(lines)
