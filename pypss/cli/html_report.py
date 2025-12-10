from typing import Dict

from pypss.utils.config import GLOBAL_CONFIG

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ report_title }}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
               background: #f4f6f8; margin: 0; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .card { background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
                padding: 20px; margin-bottom: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        .score-large { font-size: 72px; font-weight: bold; color: #2ecc71; }
        .score-bad { color: #e74c3c; }
        .score-med { color: #f1c40f; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .metric { text-align: center; }
        .metric-value { font-size: 24px; font-weight: bold; }
        .metric-label { color: #7f8c8d; font-size: 14px; }
        pre { background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; overflow-x: auto; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>PyPSS Report</h1>
                <p>Python Program Stability Score</p>
            </div>
            <div class="score-large {{ score_class }}">
                {{ pss }}
            </div>
        </div>

        <div class="grid">
            <div class="card metric">
                <div class="metric-value">{{ breakdown.timing_stability }}</div>
                <div class="metric-label">Timing Stability</div>
            </div>
            <div class="card metric">
                <div class="metric-value">{{ breakdown.memory_stability }}</div>
                <div class="metric-label">Memory Stability</div>
            </div>
            <div class="card metric">
                <div class="metric-value">{{ breakdown.error_volatility }}</div>
                <div class="metric-label">Error Volatility</div>
            </div>
            <div class="card metric">
                <div class="metric-value">{{ breakdown.concurrency_chaos }}</div>
                <div class="metric-label">Concurrency Chaos</div>
            </div>
        </div>

        <div class="card">
            <h2>🧠 AI Advisor</h2>
            <pre>{{ advisor_report }}</pre>
        </div>

        <div class="card">
            <h2>Stability Radar</h2>
            <canvas id="radarChart"></canvas>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('radarChart').getContext('2d');
        new Chart(ctx, {
            type: 'radar',
            data: {
                labels: ['Timing', 'Memory', 'Errors', 'Entropy', 'Concurrency'],
                datasets: [{
                    label: 'Stability Score',
                    data: [
                        {{ breakdown.timing_stability }},
                        {{ breakdown.memory_stability }},
                        {{ breakdown.error_volatility }},
                        {{ breakdown.branching_entropy }},
                        {{ breakdown.concurrency_chaos }}
                    ],
                    backgroundColor: 'rgba(46, 204, 113, 0.2)',
                    borderColor: 'rgba(46, 204, 113, 1)',
                    borderWidth: 2
                }]
            },
            options: {
                scales: {
                    r: {
                        suggestedMin: 0,
                        suggestedMax: 1
                    }
                }
            }
        });
    </script>
</body>
</html>
"""


def render_report_html(report: Dict, advisor_text: str) -> str:
    pss = report.get("pss", 0)
    score_class = "score-bad"
    if pss >= 90:
        score_class = ""
    elif pss >= 70:
        score_class = "score-med"

    html = HTML_TEMPLATE
    html = html.replace("{{ report_title }}", GLOBAL_CONFIG.default_html_report_title)
    html = html.replace("{{ pss }}", str(pss))
    html = html.replace("{{ score_class }}", score_class)
    html = html.replace("{{ advisor_report }}", advisor_text)

    bd = report.get("breakdown", {})
    for key, val in bd.items():
        html = html.replace(f"{{{{ breakdown.{key} }}}}", str(val))

    return html
