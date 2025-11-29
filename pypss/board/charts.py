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
