from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


def create_stability_sunburst(df):
    if df.empty:
        return go.Figure()

    font_color = "#333333"  # Darker grey for light theme

    fig = px.sunburst(
        df,
        path=["module"],
        values="traces",
        color="pss",
        color_continuous_scale=["#ef4444", "#eab308", "#22c55e"],
        range_color=[0, 100],
    )
    fig.update_layout(
        margin=dict(t=10, l=10, r=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=font_color,
        colorway=[
            "#4285F4",
            "#34A853",
            "#FBBC04",
            "#EA4335",
            "#607D8B",
            "#1e90ff",
            "#ff7f0e",
            "#2ca02c",
            "#d62728",
            "#9467bd",
        ],  # Google-ish colorway
    )
    return fig


def create_trend_chart(traces):
    if not traces:
        return go.Figure()

    df = pd.DataFrame(traces)

    # Ensure we have data to plot
    if "duration" not in df.columns or df.empty:
        return go.Figure()

    # Sort by timestamp if available, else use index
    if "timestamp" in df.columns:
        df = df.sort_values("timestamp")

    # Create bins for trend analysis (compress noise)
    # Target ~20-30 data points for the trend line
    num_bins = min(30, len(df))
    if num_bins < 2:
        return go.Figure()

    # Use index-based binning to ensure equal data distribution or time-based?
    # Index-based is safer for simulations that run very fast.
    df["bin"] = pd.qcut(df.index, q=num_bins, duplicates="drop")

    # Aggregate stats per bin
    grouped = (
        df.groupby("bin", observed=False)["duration"]
        .quantile([0.50, 0.90, 0.99])
        .unstack()
    )

    # Create x-axis points (just use bin number 0..N)
    x_axis = list(range(len(grouped)))

    # Calculate time labels if timestamp exists
    tick_vals = x_axis
    tick_text = None
    last_update_str = ""
    if "timestamp" in df.columns:
        grouped_time = df.groupby("bin", observed=False)["timestamp"].min()
        tick_text = [
            datetime.fromtimestamp(ts).strftime("%H:%M:%S") for ts in grouped_time
        ]

        # Latest timestamp for title
        max_ts = df["timestamp"].max()
        last_update_str = f"<br><span style='font-size:10px; color:gray'>Latest Data: {datetime.fromtimestamp(max_ts).strftime('%H:%M:%S')}</span>"

        # Reduce tick density if too many
        if len(tick_text) > 10:
            # Keep first, last, and every Nth in between
            step = len(tick_text) // 6
            final_vals = []
            final_text = []
            for i in range(0, len(tick_text), step):
                final_vals.append(tick_vals[i])
                final_text.append(tick_text[i])
            tick_vals = final_vals
            tick_text = final_text

    font_color = "#333333"
    grid_color = "#e0e0e0"

    fig = go.Figure()

    # P99 Line (Worst case)
    fig.add_trace(
        go.Scatter(
            x=x_axis,
            y=grouped[0.99],
            mode="lines",
            name="P99 (Tail)",
            line=dict(color="#EA4335", width=2, shape="spline"),  # Red
        )
    )

    # P90 Line (Heavy tail)
    fig.add_trace(
        go.Scatter(
            x=x_axis,
            y=grouped[0.90],
            mode="lines",
            name="P90",
            line=dict(color="#FBBC04", width=2, shape="spline"),  # Yellow/Orange
            fill="tonexty",  # Fill to P99
            fillcolor="rgba(251, 188, 4, 0.1)",
        )
    )

    # P50 Line (Median)
    fig.add_trace(
        go.Scatter(
            x=x_axis,
            y=grouped[0.50],
            mode="lines",
            name="P50 (Median)",
            line=dict(color="#34A853", width=3, shape="spline"),  # Green
            fill="tonexty",  # Fill to P90
            fillcolor="rgba(52, 168, 83, 0.1)",
        )
    )

    fig.update_layout(
        title=f"Latency Percentiles (P50 / P90 / P99){last_update_str}",
        xaxis_title="Time",
        yaxis_title="Duration (s)",
        margin=dict(t=50, l=40, r=20, b=40),  # Increased top margin for subtitle
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=font_color,
        showlegend=True,
        xaxis=dict(
            gridcolor=grid_color,
            tickfont_color=font_color,
            title_font_color=font_color,
            showticklabels=True if tick_text else False,
            tickvals=tick_vals,
            ticktext=tick_text,
        ),
        yaxis=dict(
            gridcolor=grid_color, tickfont_color=font_color, title_font_color=font_color
        ),
        hovermode="x unified",
    )
    return fig


def create_gauge_chart(score, title: str = "Stability Score"):
    font_color = "#333333"

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": title, "font": {"size": 14}},  # Dynamic title, smaller font
            gauge={
                "axis": {
                    "range": [None, 100],
                    "tickwidth": 1,
                    "tickcolor": font_color,
                    "tickfont_color": font_color,
                },
                "bar": {"color": "#4285F4"},
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 50], "color": "rgba(234, 67, 53, 0.2)"},
                    {"range": [50, 80], "color": "rgba(251, 188, 4, 0.2)"},
                    {"range": [80, 100], "color": "rgba(52, 168, 83, 0.2)"},
                ],
                "threshold": {
                    "line": {"color": font_color, "width": 2},
                    "thickness": 0.75,
                    "value": 90,
                },
            },
        )
    )

    fig.update_layout(
        margin=dict(t=30, b=10, l=25, r=25),  # Increased margins
        paper_bgcolor="rgba(0,0,0,0)",
        font={
            "color": font_color,
            "family": "Roboto Mono, monospace",
        },  # Use Roboto Mono for charts
    )
    return fig


def create_historical_chart(history_data):
    if not history_data:
        fig = go.Figure()
        fig.update_layout(
            title="No historical data available",
            xaxis={"visible": False},
            yaxis={"visible": False},
            annotations=[
                {
                    "text": "Run with --store-history to see trends",
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 16, "color": "#888"},
                }
            ],
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        return fig

    # Extract data
    dates = [datetime.fromtimestamp(h["timestamp"]) for h in history_data]
    pss_scores = [h["pss"] for h in history_data]
    ts_scores = [h.get("ts", 0) * 100 for h in history_data]
    ms_scores = [h.get("ms", 0) * 100 for h in history_data]
    ev_scores = [h.get("ev", 0) * 100 for h in history_data]
    be_scores = [h.get("be", 0) * 100 for h in history_data]
    cc_scores = [h.get("cc", 0) * 100 for h in history_data]

    # Prepare custom data for tooltips (all sub-scores)
    custom_data = []
    for i in range(len(history_data)):
        custom_data.append(
            [ts_scores[i], ms_scores[i], ev_scores[i], be_scores[i], cc_scores[i]]
        )

    fig = go.Figure()

    # Main PSS Line (Bold)
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=pss_scores,
            customdata=custom_data,
            mode="lines+markers",
            name="Overall PSS",
            line=dict(color="#4285F4", width=4),
            marker=dict(size=8, color="#4285F4", line=dict(color="white", width=2)),
            hovertemplate=(
                "<b>PSS: %{y}</b><br>"
                + "Time: %{x|%Y-%m-%d %H:%M:%S}<br><br>"
                + "Timing: %{customdata[0]:.1f} | Memory: %{customdata[1]:.1f}<br>"
                + "Errors: %{customdata[2]:.1f} | Entropy: %{customdata[3]:.1f}<br>"
                + "Concurrency: %{customdata[4]:.1f}<extra></extra>"
            ),
        )
    )

    # Sub-scores (Thinner, dashed)
    def add_sub_line(y_data, name, color):
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=y_data,
                mode="lines",
                name=name,
                line=dict(width=1.5, dash="dot", color=color),
                hoverinfo="skip",
            )
        )

    add_sub_line(ts_scores, "Timing", "#34A853")
    add_sub_line(ms_scores, "Memory", "#FBBC04")
    add_sub_line(ev_scores, "Errors", "#EA4335")

    font_color = "#333333"
    grid_color = "#e0e0e0"

    fig.update_layout(
        title=dict(text="Historical Stability Trend", font=dict(size=18)),
        xaxis_title="Run Time",
        yaxis_title="Score (0-100)",
        yaxis=dict(
            range=[0, 105],
            gridcolor=grid_color,
            tickfont_color=font_color,
            title_font_color=font_color,
        ),
        xaxis=dict(
            gridcolor=grid_color,
            tickfont_color=font_color,
            title_font_color=font_color,
            rangeselector=dict(
                buttons=list(
                    [
                        dict(count=1, label="1h", step="hour", stepmode="backward"),
                        dict(count=1, label="1d", step="day", stepmode="backward"),
                        dict(count=7, label="1w", step="day", stepmode="backward"),
                        dict(step="all"),
                    ]
                )
            ),
            type="date",
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=font_color,
        margin=dict(l=40, r=20, t=40, b=40),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def plot_stability_trends(df: pd.DataFrame):
    """
    Plots time-series for all 5 stability metrics + Overall PSS.
    df should be the aggregated DataFrame from TraceProcessor.
    """
    if df is None or df.empty:
        return go.Figure()

    fig = go.Figure()

    # Scale 0-1 metrics to 0-100 for consistent plotting with PSS
    metrics = {
        "pss": {"name": "Overall PSS", "color": "#4285F4", "width": 4, "dash": "solid"},
        "ts": {
            "name": "Timing Stability",
            "color": "#34A853",
            "width": 2,
            "dash": "dot",
        },
        "ms": {
            "name": "Memory Stability",
            "color": "#FBBC04",
            "width": 2,
            "dash": "dot",
        },
        "ev": {
            "name": "Error Volatility",
            "color": "#EA4335",
            "width": 2,
            "dash": "dot",
        },
        "be": {
            "name": "Branching Entropy",
            "color": "#9333EA",
            "width": 2,
            "dash": "dot",
        },
        "cc": {
            "name": "Concurrency Chaos",
            "color": "#06B6D4",
            "width": 2,
            "dash": "dot",
        },
    }

    for col, style in metrics.items():
        if col not in df.columns:
            continue

        # Determine if we need to scale (PSS is already 0-100, others are 0-1)
        y_vals = df[col] if col == "pss" else df[col] * 100

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=y_vals,
                mode="lines+markers",
                name=style["name"],
                line=dict(
                    color=style["color"], width=style["width"], dash=style["dash"]
                ),
                hovertemplate=f"<b>{style['name']}: %{{y:.1f}}</b><extra></extra>",
            )
        )
    font_color = "#333333"
    grid_color = "#e0e0e0"

    fig.update_layout(
        title="Stability Metrics Over Time",
        xaxis_title="Time",
        yaxis_title="Score (0-100)",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=font_color,
        margin=dict(l=40, r=20, t=40, b=40),
        hovermode="x unified",
        yaxis=dict(range=[0, 105], gridcolor=grid_color),
        xaxis=dict(gridcolor=grid_color),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return fig


def plot_error_heatmap(traces: list):
    """
    Heatmap of Error Density: Time vs Module.
    """
    if not traces:
        return go.Figure()

    df = pd.DataFrame(traces)
    # Robustly check columns exist
    if "error" not in df.columns or "module" not in df.columns:
        return go.Figure()

    # Ensure error is boolean and handle filtering safely
    try:
        # Fill NAs with False to avoid errors during filtering
        df["error"] = df["error"].fillna(False).astype(bool)
        errors = df[df["error"]].copy()
    except Exception:
        return go.Figure()

    if errors.empty:
        # Return empty with message? Or just empty grid
        fig = go.Figure()
        fig.update_layout(
            title="No errors detected (Great job!)",
            xaxis={"visible": False},
            yaxis={"visible": False},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#333333",
        )
        return fig

    if "timestamp" in errors.columns:
        errors["datetime"] = pd.to_datetime(errors["timestamp"], unit="s")
    else:
        # Fallback if no timestamp
        return go.Figure()

    # Use Density Heatmap
    fig = px.density_heatmap(
        errors,
        x="datetime",
        y="module",
        nbinsx=30,  # Auto-binning
        title="Error Cluster Heatmap",
        color_continuous_scale="Reds",
    )

    font_color = "#333333"
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=font_color,
        margin=dict(l=40, r=20, t=40, b=40),
    )
    return fig


def plot_entropy_heatmap(traces: list):
    """
    Heatmap of Branching Activity/Entropy: Time vs Module.
    Uses 'branch_tag' presence as a proxy for complex logic density.
    """
    if not traces:
        return go.Figure()

    df = pd.DataFrame(traces)
    if "branch_tag" not in df.columns or "module" not in df.columns:
        return go.Figure()

    # Filter traces with branch tags
    branches = df[df["branch_tag"].notna() & (df["branch_tag"] != "")].copy()
    if branches.empty:
        return go.Figure()

    if "timestamp" in branches.columns:
        branches["datetime"] = pd.to_datetime(branches["timestamp"], unit="s")

    # We want to show 'Entropy' or 'Complexity'.
    # Simply counting branch tags in a bin gives 'Branch Density'.
    # Calculating actual entropy requires aggregation.
    # For visual simplicity in a heatmap, Density of Branching Events is a good proxy for "Hot/Complex Paths".

    fig = px.density_heatmap(
        branches,
        x="datetime",
        y="module",
        nbinsx=30,
        title="Branching Activity Heatmap (Complexity Proxy)",
        color_continuous_scale="Viridis",
    )

    font_color = "#333333"
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=font_color,
        margin=dict(l=40, r=20, t=40, b=40),
    )
    return fig


def plot_concurrency_dist(traces: list):
    """
    Distribution of CPU Time vs Wait Time (Violin Plot).
    """
    if not traces:
        return go.Figure()

    df = pd.DataFrame(traces)
    required_cols = ["cpu_time", "wait_time"]
    if not all(col in df.columns for col in required_cols):
        return go.Figure()

    # Melt for side-by-side violin
    melted = df.melt(
        value_vars=["cpu_time", "wait_time"], var_name="Metric", value_name="Seconds"
    )

    fig = px.violin(
        melted,
        y="Seconds",
        x="Metric",
        color="Metric",
        box=True,  # Show box plot inside violin
        points="outliers",  # Show outliers
        title="Concurrency Distribution: CPU vs Wait Time",
        color_discrete_map={"cpu_time": "#4285F4", "wait_time": "#FBBC04"},
    )

    font_color = "#333333"
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=font_color,
        showlegend=False,
        margin=dict(l=40, r=20, t=40, b=40),
    )
    return fig
