import os
import time
from datetime import datetime

from nicegui import app, ui

from pypss.board.charts import (
    create_gauge_chart,
    create_historical_chart,
    create_trend_chart,
    plot_concurrency_dist,
    plot_entropy_heatmap,
    plot_error_heatmap,
    plot_stability_trends,
)
from pypss.board.data_loader import load_trace_data
from pypss.core import compute_pss_from_traces
from pypss.storage import get_storage_backend
from pypss.utils.config import GLOBAL_CONFIG


def start_board(trace_file: str):
    # --- THEME CONFIGURATION (Google AI Studio inspired) ---
    # Deep primary for dark mode, clean for light mode
    ui.colors(
        primary=GLOBAL_CONFIG.ui_theme_primary,
        secondary=GLOBAL_CONFIG.ui_theme_secondary,
        accent=GLOBAL_CONFIG.ui_theme_accent,
        positive=GLOBAL_CONFIG.ui_theme_positive,
        negative=GLOBAL_CONFIG.ui_theme_negative,
        info=GLOBAL_CONFIG.ui_theme_info,
        warning=GLOBAL_CONFIG.ui_theme_warning,
    )

    # Register static files
    docs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "docs"))
    if os.path.exists(docs_dir):
        app.add_static_files("/static", docs_dir)
    else:
        print(f"Warning: Docs directory not found at {docs_dir}. Static files will not be served.")

    # State
    last_mtime = 0.0

    # AI Diagnostics Logic
    def generate_ai_diagnostics(report, df):
        analysis_summary = []
        recommendations = []

        overall_pss = report["pss"]
        if overall_pss >= 90:
            analysis_summary.append("Overall system stability is **Excellent**.")
            recommendations.append("Maintain current best practices and monitor for any regressions.")
        elif overall_pss >= 70:
            analysis_summary.append("System stability is **Good**, but shows some areas for improvement.")
            recommendations.append(
                "Review the 'Metric Breakdown' and 'Module Performance' for specific areas to optimize."
            )
        else:
            analysis_summary.append("System stability is **Unstable**. Immediate attention is recommended.")
            recommendations.append("Prioritize investigating the root causes identified below.")

        # Find worst performing metric
        breakdown_scores = report["breakdown"]
        worst_metric = min(breakdown_scores, key=breakdown_scores.get)
        worst_metric_score = breakdown_scores[worst_metric] * 100  # Convert to 0-100

        if worst_metric_score < 70:
            analysis_summary.append(
                f"**{worst_metric.replace('_', ' ').title()}** is the weakest pillar ({worst_metric_score:.1f}/100)."
            )

            if worst_metric == "error_volatility":
                recommendations.append(
                    "Focus on identifying and fixing critical errors, especially in modules with high error rates."
                )
            elif worst_metric == "timing_stability":
                recommendations.append(
                    "Investigate latency spikes and variance. Look for I/O bottlenecks or inefficient algorithms."
                )
            elif worst_metric == "memory_stability":
                recommendations.append(
                    "Address potential memory leaks or excessive memory consumption in high-impact modules."
                )
            elif worst_metric == "branching_entropy":
                recommendations.append("Review complex conditional logic and ensure predictable execution paths.")
            elif worst_metric == "concurrency_chaos":
                recommendations.append("Analyze resource contention and thread/process synchronization issues.")

        # Find top offending module if overall PSS is not excellent
        top_offender_module = "N/A"
        if overall_pss < 90 and not df.empty:
            worst_module_row = df.loc[df["pss"].idxmin()]
            top_offender_module = worst_module_row["module"]
            offender_pss = worst_module_row["pss"]
            analysis_summary.append(
                f"The most unstable component is **{top_offender_module}** (PSS: {offender_pss:.1f}/100)."
            )

            # More specific recommendations based on top offender and worst metric
            if worst_metric_score < 70 and top_offender_module != "N/A":
                if worst_metric == "error_volatility":
                    recommendations.append(
                        f"Specifically, review error handling and logic in the `{top_offender_module}` module."
                    )
                elif worst_metric == "timing_stability":
                    recommendations.append(
                        f"Deep dive into `{top_offender_module}` to profile performance bottlenecks."
                    )
                elif worst_metric == "memory_stability":
                    recommendations.append(
                        f"Examine `{top_offender_module}` for memory allocation patterns and potential leaks."
                    )

        return "\n".join([f"* {s}" for s in analysis_summary]), "\n".join([f"* {r}" for r in recommendations])

    # Anomaly Detection Logic
    def check_for_anomalies(report, raw_traces):
        CRITICAL_PSS_THRESHOLD = GLOBAL_CONFIG.dashboard_critical_pss_threshold
        WARNING_ERROR_RATE = GLOBAL_CONFIG.dashboard_warning_error_rate

        is_anomaly = False
        anomaly_messages = []

        overall_pss = report["pss"]
        if overall_pss < CRITICAL_PSS_THRESHOLD:
            is_anomaly = True
            anomaly_messages.append(f"CRITICAL: Overall PSS ({overall_pss}/100) is below {CRITICAL_PSS_THRESHOLD}.")

        # Calculate current error rate
        error_count = len([t for t in raw_traces if t.get("error")])
        total_traces = len(raw_traces)
        current_error_rate = (error_count / total_traces) if total_traces > 0 else 0

        if current_error_rate > WARNING_ERROR_RATE:
            is_anomaly = True
            anomaly_messages.append(
                f"WARNING: Error Rate ({current_error_rate:.1%}) is above {WARNING_ERROR_RATE:.1%}."
            )

        return is_anomaly, "\n".join(anomaly_messages)

    # Help Dialog
    def show_help():
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-2xl p-0"):
            with ui.row().classes("w-full bg-gray-50 p-4 border-b border-gray-200 items-center justify-between"):
                ui.label("PyPSS Stability Guide").classes("text-lg font-bold text-gray-800")
                ui.button(icon="close", on_click=dialog.close).props("flat round dense")

            with ui.column().classes("p-6 gap-6 overflow-y-auto max-h-[80vh]"):
                # Section 1: PSS Score
                with ui.column().classes("gap-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("health_and_safety", size="sm").classes("text-green-600")
                        ui.label("What is the PSS Score?").classes("text-md font-bold text-gray-700")
                    ui.markdown(
                        """
                        The **Python Stability Score (PSS)** is a 0-100 rating of your
                        system's reliability.
                        *   **90-100:** Excellent. Stable and predictable.
                        *   **70-89:** Good. Minor variance or occasional glitches.
                        *   **< 70:** Unstable. High latency, errors, or resource spikes.
                        """
                    ).classes("text-sm text-gray-600 ml-8")

                ui.separator()

                # Section 2: Latency Percentiles
                with ui.column().classes("gap-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("show_chart", size="sm").classes("text-blue-600")
                        ui.label("Understanding Latency (P50 / P90 / P99)").classes("text-md font-bold text-gray-700")
                    ui.markdown(
                        """
                        Averages lie. We use **Percentiles** to show the true user
                        experience over the **Execution Timeline** (Left = Start, 
                        Right = End):
                        
                        *   <span class="text-green-600 font-bold">P50 (Median):</span>
                            The **Typical User**. 50% of requests are faster than this.
                        *   <span class="text-orange-500 font-bold">P90 (Heavy Load):</span>
                            The **Slow User**. 90% of requests are faster than this.
                        *   <span class="text-red-600 font-bold">P99 (Worst Case):</span>
                            The **Tail End**. 1% of users experience this slowness.
                        """
                    ).classes("text-sm text-gray-600 ml-8")

                ui.separator()

                # Section 3: Stability Bands
                with ui.column().classes("gap-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("layers", size="sm").classes("text-purple-600")
                        ui.label("The 'Stability Gap'").classes("text-md font-bold text-gray-700")
                    ui.markdown(
                        """
                        In the **Latency Percentiles** chart, look at the gap between
                        the <span class=\"text-green-600\">Green Line (P50)</span> and
                        the <span class=\"text-red-600\">Red Line (P99)</span>.
                        
                        *   **Narrow Gap:** Predictable performance. (Good)
                        *   **Wide Gap:** Unpredictable "jitter". Some users are waiting
                            much longer than others. (Bad)
                        """
                    ).classes("text-sm text-gray-600 ml-8")

                ui.separator()

                # Section 4: AI Advisor (New)
                with ui.column().classes("gap-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("auto_awesome", size="sm").classes("text-purple-600")
                        ui.label("AI Advisor").classes("text-md font-bold text-gray-700")
                    ui.markdown(
                        """
                        The **AI Diagnostics** card automatically analyzes your
                        stability report to find the root cause of low scores.
                        *   **Analysis:** Summarizes the overall health and identifies
                            the weakest metric.
                        *   **Recommendations:** Provides actionable steps to improve
                            stability, such as "Investigate latency spikes" or "Fix
                            error handling in module X".
                        """
                    ).classes("text-sm text-gray-600 ml-8")

                ui.separator()

                # Section 5: Scoring Breakdown
                with ui.column().classes("gap-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("fact_check", size="sm").classes("text-indigo-600")
                        ui.label("Scoring Breakdown (The 5 Pillars)").classes("text-md font-bold text-gray-700")
                    ui.markdown(
                        """
                        Your PSS score is calculated from these 5 metrics:
                        
                        1.  **Timing Stability:** Do tasks take the same amount of time
                            every run? (Low variance = High Score)
                        2.  **Memory Stability:** Is memory usage flat, or does it spike
                            unpredictably? (Flat = High Score)
                        3.  **Error Volatility:** Are errors rare and isolated, or do
                            they happen in bursts? (No bursts = High Score)
                        4.  **Branching Entropy:** Does the code take random different
                            paths (if/else) or is it deterministic? (Predictable paths
                            = High Score)
                        5.  **Concurrency Chaos:** Are threads waiting on locks/
                            resources? (Low wait time = High Score)
                        """
                    ).classes("text-sm text-gray-600 ml-8")

                ui.separator()

                # Section 6: Advanced Diagnostics (New)
                with ui.column().classes("gap-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("bug_report", size="sm").classes("text-red-500")
                        ui.label("Advanced Diagnostics (Heatmaps)").classes("text-md font-bold text-gray-700")
                    ui.markdown(
                        """
                        In the **Diagnostics** tab, we visualize system behavior
                        over time:
                        *   **Error Clusters:** Shows *when* and *where* errors are
                            happening. Dense red spots indicate instability bursts in
                            specific modules.
                        *   **Logic Complexity:** Visualizes which modules have the most
                            complex execution paths (branching). High complexity often
                            correlates with lower stability.
                        """
                    ).classes("text-sm text-gray-600 ml-8")

                ui.separator()

                # Section 7: Concurrency & Performance (New)
                with ui.column().classes("gap-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("speed", size="sm").classes("text-teal-500")
                        ui.label("Concurrency & Performance").classes("text-md font-bold text-gray-700")
                    ui.markdown(
                        """
                        In the **Performance** tab:
                        *   **Latency Percentiles:** A detailed view of P50, P90, and P99
                            latency over time.
                        *   **Concurrency Wait Times:** A violin plot comparing **CPU Time**
                            (active work) vs. **Wait Time** (blocked/sleeping). High wait
                            times indicate resource contention, I/O bottlenecks, or lock
                            issues.
                        """
                    ).classes("text-sm text-gray-600 ml-8")

                ui.separator()

                # Section 8: Configuration
                with ui.column().classes("gap-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("settings", size="sm").classes("text-gray-600")
                        ui.label("Configuring PyPSS").classes("text-md font-bold text-gray-700")
                    ui.markdown(
                        """
                        You can tune the PSS algorithm using the **Settings** button
                        (the gear icon in the header).

                        *   **Sampling:** Control how many data points are collected.
                            `Sample Rate` is great for high-traffic apps, while `Max Traces`
                            limits memory usage.
                        *   **PSS Weights:** Adjust the importance of each of the 5 pillars.
                            The weights must sum to 1.0.
                        *   **Sensitivity:** Advanced options to fine-tune how the algorithm
                            detects anomalies in timing, memory, and errors.

                        **Example:** If your application is a data processing pipeline where
                        occasional errors are less important than consistent processing
                        time, you could:
                        1.  Decrease the **Error Volatility** weight (e.g., from `0.2` to
                            `0.1`).
                        2.  Increase the **Timing Stability** weight (e.g., from `0.3` to
                            `0.4`).
                        
                        This makes the PSS score more sensitive to performance and less
                        sensitive to errors.
                        """
                    ).classes("text-sm text-gray-600 ml-8")

                ui.separator()

                # Section 6: Historical Trends
                with ui.column().classes("gap-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("history", size="sm").classes("text-blue-500")
                        ui.label("Historical Trends").classes("text-md font-bold text-gray-700")
                    ui.markdown(
                        """
                        The **Historical Stability Trend** chart shows how your PSS score
                        has evolved over time.
                        *   **Blue Line:** Overall PSS Score.
                        *   **Dashed Lines:** Individual stability pillars (Timing, Memory,
                            Errors).
                        *   **Drops:** A sudden drop in the blue line indicates a regression.
                            Hover over the point to see which pillar caused it.
                        """
                    ).classes("text-sm text-gray-600 ml-8")

        dialog.open()

    def show_settings_dialog(current_report=None, current_df=None, current_trace_file=None):
        from pypss.utils.config import GLOBAL_CONFIG  # Re-import to get latest

        # Local state for dialog inputs using a dictionary
        settings = {
            "sample_rate": GLOBAL_CONFIG.sample_rate,
            "max_traces": GLOBAL_CONFIG.max_traces,
            "w_ts": GLOBAL_CONFIG.w_ts,
            "w_ms": GLOBAL_CONFIG.w_ms,
            "w_ev": GLOBAL_CONFIG.w_ev,
            "w_be": GLOBAL_CONFIG.w_be,
            "w_cc": GLOBAL_CONFIG.w_cc,
            "alpha": GLOBAL_CONFIG.alpha,
            "beta": GLOBAL_CONFIG.beta,
            "gamma": GLOBAL_CONFIG.gamma,
            "mem_spike_threshold_ratio": GLOBAL_CONFIG.mem_spike_threshold_ratio,
            "delta": GLOBAL_CONFIG.delta,
            "error_spike_threshold": GLOBAL_CONFIG.error_spike_threshold,
            "consecutive_error_threshold": GLOBAL_CONFIG.consecutive_error_threshold,
            "concurrency_wait_threshold": GLOBAL_CONFIG.concurrency_wait_threshold,
        }

        with (
            ui.dialog() as dialog,
            ui.card().classes("w-full max-w-2xl p-0 max-h-[90vh]"),
        ):
            # --- Dialog Header ---
            with ui.row().classes(
                "w-full bg-gray-50 p-4 border-b border-gray-200 items-center justify-between sticky top-0 z-10"
            ):
                ui.label("PyPSS Configuration").classes("text-lg font-bold text-gray-800")
                ui.button(icon="close", on_click=dialog.close).props("flat round dense")

            # --- Tabs ---
            with ui.tabs().props("align=left").classes("w-full") as tabs:
                ui.tab("sampling", label="Sampling", icon="scatter_plot")
                ui.tab("weights", label="PSS Weights", icon="balance")
                ui.tab("thresholds", label="Sensitivity", icon="tune")

            # --- Tab Panels (Main Content) ---
            with ui.tab_panels(tabs, value="sampling").classes("w-full overflow-y-auto"):
                # --- Sampling Panel ---
                with ui.tab_panel("sampling"):
                    with ui.column().classes("gap-4 p-4"):
                        with ui.column():
                            with ui.row().classes("items-center"):
                                ui.label("Sample Rate").classes("text-md font-semibold")
                                ui.icon("help_outline", size="xs").tooltip(
                                    "The fraction of traces to collect (0.01 to 1.0)."
                                ).classes("text-gray-500 cursor-pointer")
                            ui.slider(
                                min=0.01,
                                max=1.0,
                                step=0.01,
                                value=settings["sample_rate"],
                            ).bind_value(settings, "sample_rate").props("label-always")

                        ui.separator()

                        with ui.column():
                            with ui.row().classes("items-center"):
                                ui.label("Max Traces (Buffer Size)").classes("text-md font-semibold")
                                ui.icon("help_outline", size="xs").tooltip(
                                    "The maximum number of traces to keep in the buffer."
                                ).classes("text-gray-500 cursor-pointer")
                            ui.number(value=settings["max_traces"]).bind_value(settings, "max_traces").props(
                                "outlined dense"
                            ).classes("w-full")

                # --- Weights Panel ---
                with ui.tab_panel("weights"):
                    with ui.column().classes("gap-4 p-4"):
                        sum_label = ui.label().classes("font-mono font-bold self-end mb-2 px-2 py-1 rounded-md")

                        def update_sum():
                            s = (
                                settings["w_ts"]
                                + settings["w_ms"]
                                + settings["w_ev"]
                                + settings["w_be"]
                                + settings["w_cc"]
                            )
                            sum_label.set_text(f"Sum: {s:.2f}")
                            if abs(s - 1.0) > 0.001:
                                sum_label.classes(
                                    "bg-red-100 text-red-700",
                                    remove="bg-green-100 text-green-700",
                                )
                            else:
                                sum_label.classes(
                                    "bg-green-100 text-green-700",
                                    remove="bg-red-100 text-red-700",
                                )

                        def weight_slider(key, label_text):
                            with ui.column():
                                ui.label(label_text).classes("text-md font-semibold")
                                ui.slider(min=0.0, max=1.0, step=0.01, value=settings[key]).bind_value(
                                    settings, key
                                ).props("label-always").on("update:model-value", lambda: update_sum())
                            ui.separator()

                        weight_slider("w_ts", "Timing Stability")
                        weight_slider("w_ms", "Memory Stability")
                        weight_slider("w_ev", "Error Volatility")
                        weight_slider("w_be", "Branching Entropy")
                        weight_slider("w_cc", "Concurrency Chaos")

                        update_sum()

                # --- Sensitivity Panel ---
                with ui.tab_panel("thresholds"):
                    with ui.column().classes("gap-4 p-4"):

                        def threshold_input(key, label_text, tooltip_text, step):
                            with ui.column():
                                with ui.row().classes("items-center"):
                                    ui.label(label_text).classes("text-md font-semibold")
                                    ui.icon("help_outline", size="xs").tooltip(tooltip_text).classes(
                                        "text-gray-500 cursor-pointer"
                                    )
                                ui.number(value=settings[key]).bind_value(settings, key).props(
                                    f"outlined dense step={step}"
                                ).classes("w-full")
                            ui.separator()

                        threshold_input(
                            "alpha",
                            "Timing CV (alpha)",
                            "Sensitivity to timing variance. Higher is stricter.",
                            0.1,
                        )
                        threshold_input(
                            "beta",
                            "Timing Tail (beta)",
                            "Sensitivity to latency spikes. Higher is stricter.",
                            0.1,
                        )
                        threshold_input(
                            "gamma",
                            "Memory (gamma)",
                            "Sensitivity to memory usage variance. Higher is stricter.",
                            0.1,
                        )
                        threshold_input(
                            "mem_spike_threshold_ratio",
                            "Memory Spike Ratio",
                            "Ratio to detect a memory spike.",
                            0.1,
                        )
                        threshold_input(
                            "delta",
                            "Error (delta)",
                            "Sensitivity to error bursts. Higher is stricter.",
                            0.1,
                        )
                        threshold_input(
                            "error_spike_threshold",
                            "Error Spike Rate",
                            "Error rate to detect an error spike.",
                            0.01,
                        )
                        threshold_input(
                            "consecutive_error_threshold",
                            "Consecutive Errors",
                            "Number of consecutive errors to detect a spike.",
                            1,
                        )
                        threshold_input(
                            "concurrency_wait_threshold",
                            "Concurrency Wait (s)",
                            "Concurrency wait time threshold in seconds.",
                            0.0001,
                        )

            # --- Dialog Footer / Action Buttons ---
            with ui.row().classes("w-full justify-end gap-2 p-4 border-t bg-white"):
                ui.button("Cancel", on_click=dialog.close).props("flat").classes("text-gray-700")
                ui.button("Save Changes", on_click=lambda: save_settings()).props("color=primary")

        def save_settings():
            # Update GLOBAL_CONFIG from the settings dictionary
            GLOBAL_CONFIG.sample_rate = settings["sample_rate"]
            GLOBAL_CONFIG.max_traces = int(settings["max_traces"])
            GLOBAL_CONFIG.w_ts = settings["w_ts"]
            GLOBAL_CONFIG.w_ms = settings["w_ms"]
            GLOBAL_CONFIG.w_ev = settings["w_ev"]
            GLOBAL_CONFIG.w_be = settings["w_be"]
            GLOBAL_CONFIG.w_cc = settings["w_cc"]
            GLOBAL_CONFIG.alpha = settings["alpha"]
            GLOBAL_CONFIG.beta = settings["beta"]
            GLOBAL_CONFIG.gamma = settings["gamma"]
            GLOBAL_CONFIG.mem_spike_threshold_ratio = settings["mem_spike_threshold_ratio"]
            GLOBAL_CONFIG.delta = settings["delta"]
            GLOBAL_CONFIG.error_spike_threshold = settings["error_spike_threshold"]
            GLOBAL_CONFIG.consecutive_error_threshold = int(settings["consecutive_error_threshold"])
            GLOBAL_CONFIG.concurrency_wait_threshold = settings["concurrency_wait_threshold"]

            GLOBAL_CONFIG.save()  # Save to pypss.toml
            ui.notify("Settings saved and dashboard refreshed!", type="positive")
            dialog.close()
            content.refresh()  # Refresh main dashboard to apply new settings

        dialog.open()

    # Theme state (reactive)

    # KPI card helper function (moved outside content())
    def kpi_card(
        title,
        value,
        subtitle,
        icon,
        color_class,
        extra_details=None,
        on_click=None,
    ):
        # Card background is crucial here
        card_classes = (
            "col-span-12 sm:col-span-6 md:col-span-3 p-4 shadow-sm border"
            " border-gray-200 bg-white flex flex-col justify-between"
        )
        if on_click:
            card_classes += " cursor-pointer hover:shadow-md transition-shadow"

        card = ui.card().classes(card_classes).on("click", on_click if on_click else lambda: None)
        with card:
            with ui.row().classes("justify-between items-start w-full"):
                with ui.column().classes("gap-1"):
                    ui.label(title).classes("text-sm font-semibold text-gray-600 uppercase tracking-wider")
                    ui.label(value).classes(f"text-3xl font-black {color_class}")
                    ui.label(subtitle).classes("text-xs font-medium text-gray-400")
                ui.icon(icon, size="3em").classes(f"{color_class} opacity-10")

            if extra_details:
                ui.separator().classes("my-2")
                with ui.row().classes("w-full justify-between gap-2 text-xs text-gray-500"):
                    for label, val in extra_details.items():
                        with ui.column().classes("gap-0"):
                            ui.label(label).classes("font-semibold text-gray-400")
                            ui.label(val).classes("font-mono font-medium")
        return card

    # --- LAYOUT ---
    ui.query("body").classes("bg-white flex flex-col h-screen")

    # Header (Theme-aware)
    with (
        ui.header()
        .classes("bg-white text-gray-900 border-b border-gray-200 items-center px-6 h-16")
        .props("elevated=false")
        .style('transition: all 0.3s ease; font-family: "Google Sans Mono", monospace;')
    ):
        # Logo & Title
        with ui.row().classes("items-center gap-4"):
            ui.image("/static/TDMC.png").classes("w-10 h-10 object-contain")

            with ui.column().classes("gap-0"):
                ui.label("PyPSS Platform").classes("text-xl font-bold tracking-tight leading-none text-gray-900")
                ui.label("Stability Intelligence").classes(
                    "text-xs font-medium text-gray-600 uppercase tracking-widest"
                )

        ui.space()

        # Right Actions (Theme-aware)
        with ui.row().classes("items-center gap-4"):
            # Data Freshness
            freshness_label = ui.label("Data: --").classes("text-xs font-mono font-bold text-gray-500")

            # Clock
            clock_label = ui.label().classes("text-xs font-mono text-gray-600 border-r border-gray-300 pr-4")

            # Status Indicator
            with ui.row().classes("items-center gap-2 bg-gray-50 rounded-full px-3 py-1 border border-gray-200"):
                ui.icon("fiber_manual_record", size="12px").classes("text-green-500 animate-pulse")
                ui.label("Live").classes("text-xs font-bold text-gray-700")

            # Anomaly Alert Indicator
            anomaly_alert_icon = ui.icon("warning", size="20px").classes("text-red-500 hidden")
            with anomaly_alert_icon:
                anomaly_tooltip = ui.tooltip("No anomalies detected.")

            # Help Button
            ui.button(icon="help_outline", on_click=show_help).props("flat round dense color=grey-7").tooltip(
                "Guide: How to read this dashboard"
            )

            # Settings Button
            ui.button(
                icon="settings",
                on_click=lambda: show_settings_dialog(current_trace_file=trace_file),
            ).props("flat round dense color=grey-7").tooltip("Configure PyPSS Parameters")

            # Theme Toggle (Icon color adjusts)

    # --- DYNAMIC CONTENT ---
    # This will be the main content wrapper background, allowing normal scrolling
    with ui.column().classes("w-full bg-gray-50 p-6 gap-6 flex-grow overflow-y-auto"):

        @ui.refreshable
        def content():
            report, df, raw_traces, processor = load_trace_data(trace_file)

            # Load History
            history_data = []
            try:
                storage = get_storage_backend(
                    {
                        "storage_backend": GLOBAL_CONFIG.storage_backend,
                        "storage_uri": GLOBAL_CONFIG.storage_uri,
                    }
                )
                history_data = storage.get_history(limit=50)
                # Sort by timestamp ascending for the chart (oldest first)
                history_data.reverse()
            except Exception:
                # Silently fail if storage not configured or db missing
                pass

            if not report:
                with ui.column().classes("w-full h-[80vh] items-center justify-center bg-white"):
                    ui.icon("analytics", size="6rem").classes("text-gray-400")
                    ui.label("Waiting for Trace Data...").classes("text-2xl font-light text-gray-500 mt-4")
                    ui.spinner(size="lg", color="primary").classes("mt-4")
                # Hide anomaly icon if no data
                anomaly_alert_icon.classes(replace="text-red-500 animate-pulse", add="hidden")
                anomaly_tooltip.set_text("No data to analyze.")
                return

            # Check for anomalies and update alert icon
            is_anomaly, anomaly_message = check_for_anomalies(report, raw_traces)
            if is_anomaly:
                anomaly_alert_icon.classes(replace="hidden", add="text-red-500 animate-pulse")
                anomaly_tooltip.set_text(anomaly_message)
            else:
                anomaly_alert_icon.classes(replace="text-red-500 animate-pulse", add="hidden")
                anomaly_tooltip.set_text("No anomalies detected.")

            # --- TABS LAYOUT ---
            with ui.tabs().classes("w-full text-gray-700") as tabs:
                ui.tab("overview", icon="dashboard", label="Overview")
                ui.tab("metrics", icon="timeline", label="Metrics")
                ui.tab("diagnostics", icon="bug_report", label="Diagnostics")
                ui.tab("performance", icon="speed", label="Performance")

            with ui.tab_panels(tabs, value="overview").classes("w-full bg-transparent"):
                # --- TAB 1: OVERVIEW ---
                with ui.tab_panel("overview").classes("p-0 gap-6"):
                    with ui.column().classes("w-full gap-6"):
                        # Module Detail Dialog (kept in overview context)
                        def show_module_detail_dialog(module_name: str):
                            module_traces = [t for t in raw_traces if t.get("module") == module_name]
                            if not module_traces:
                                ui.notify(
                                    f"No traces found for module {module_name}.",
                                    type="info",
                                )
                                return

                            module_report = compute_pss_from_traces(module_traces)

                            with (
                                ui.dialog() as dialog,
                                ui.card().classes("w-full max-w-5xl h-[90vh] flex flex-col"),
                            ):
                                with ui.row().classes("w-full items-center justify-between border-b pb-2"):
                                    ui.label(f"Module Performance: {module_name}").classes(
                                        "text-xl font-bold text-gray-800"
                                    )
                                    ui.label(f"PSS: {module_report['pss']}/100").classes(
                                        "text-lg font-semibold text-gray-700"
                                    )
                                    ui.button(icon="close", on_click=dialog.close).props("flat round dense")

                                with ui.column().classes("flex-grow overflow-y-auto w-full gap-4 p-4"):
                                    # Module-specific Latency Trend
                                    with ui.card().classes(
                                        "w-full shadow-sm border border-gray-200 bg-white p-0 flex flex-col"
                                    ):
                                        with ui.row().classes(
                                            "w-full p-4 border-b border-gray-200 items-center justify-between"
                                        ):
                                            ui.label(f"Latency Percentiles for {module_name}").classes(
                                                "font-bold text-gray-700 text-lg"
                                            )
                                            ui.icon("show_chart", size="sm").classes("text-gray-400")
                                        ui.plotly(create_trend_chart(module_traces)).classes("w-full h-64")

                                    # Module-specific Failed Traces
                                    failed_module_traces_all = [t for t in module_traces if t.get("error")]

                                    if failed_module_traces_all:
                                        rows = []
                                        for t in failed_module_traces_all:
                                            ts_str = datetime.fromtimestamp(t.get("timestamp", 0)).strftime("%H:%M:%S")
                                            rows.append(
                                                {
                                                    "time": ts_str,
                                                    "function": t.get("name", "unknown"),
                                                    "error_type": t.get("exception_type", "N/A"),
                                                    "error_message": t.get("exception_message", "N/A"),
                                                    "duration": (f"{t.get('duration', 0) * 1000:.1f}ms"),
                                                }
                                            )

                                        with ui.card().classes(
                                            "w-full shadow-sm border border-gray-200 bg-white p-0 flex flex-col mt-4"
                                        ):
                                            with ui.row().classes(
                                                "w-full p-4 border-b border-gray-200 items-center justify-between"
                                            ):
                                                ui.label(
                                                    f"Failed Traces in {module_name} ({len(failed_module_traces_all)})"
                                                ).classes("font-bold text-red-600 text-lg")
                                                ui.icon("error_outline", size="sm").classes("text-red-400")

                                            ui.table(
                                                columns=[
                                                    {
                                                        "name": "time",
                                                        "label": "Time",
                                                        "field": "time",
                                                        "sortable": True,
                                                        "align": "left",
                                                    },
                                                    {
                                                        "name": "function",
                                                        "label": "Function",
                                                        "field": "function",
                                                        "sortable": True,
                                                        "align": "left",
                                                    },
                                                    {
                                                        "name": "error_type",
                                                        "label": "Error Type",
                                                        "field": "error_type",
                                                        "sortable": True,
                                                        "align": "left",
                                                    },
                                                    {
                                                        "name": "error_message",
                                                        "label": "Error Message",
                                                        "field": "error_message",
                                                        "sortable": False,
                                                        "align": "left",
                                                        "classes": "max-w-xs truncate",
                                                    },
                                                    {
                                                        "name": "duration",
                                                        "label": "Duration",
                                                        "field": "duration",
                                                        "sortable": True,
                                                        "align": "right",
                                                    },
                                                ],
                                                rows=rows,
                                                pagination=5,
                                            ).classes("w-full flex-grow")
                                    else:
                                        ui.label("No failed traces for this module.").classes(
                                            "text-gray-500 italic mt-4"
                                        )

                                dialog.open()

                        def show_failures():
                            failed_traces = [t for t in raw_traces if t.get("error")]
                            if not failed_traces:
                                ui.notify("No failed traces found.", type="positive")
                                return

                            with (
                                ui.dialog() as dialog,
                                ui.card().classes("w-full max-w-6xl h-[90vh] flex flex-col"),
                            ):
                                with ui.row().classes("w-full items-center justify-between border-b pb-2"):
                                    ui.label(f"All Failed Traces ({len(failed_traces)})").classes(
                                        "text-xl font-bold text-red-600"
                                    )
                                    ui.button(icon="close", on_click=dialog.close).props("flat round dense")

                                rows = []
                                for t in failed_traces:
                                    ts_str = datetime.fromtimestamp(t.get("timestamp", 0)).strftime("%H:%M:%S")
                                    rows.append(
                                        {
                                            "time": ts_str,
                                            "module": t.get("module", "unknown"),
                                            "function": t.get("name", "unknown"),
                                            "error_type": t.get("exception_type", "N/A"),
                                            "error_message": t.get("exception_message", "N/A"),
                                            "duration": (f"{t.get('duration', 0) * 1000:.1f}ms"),
                                        }
                                    )

                                ui.table(
                                    columns=[
                                        {
                                            "name": "time",
                                            "label": "Time",
                                            "field": "time",
                                            "sortable": True,
                                            "align": "left",
                                        },
                                        {
                                            "name": "module",
                                            "label": "Module",
                                            "field": "module",
                                            "sortable": True,
                                            "align": "left",
                                        },
                                        {
                                            "name": "function",
                                            "label": "Function",
                                            "field": "function",
                                            "sortable": True,
                                            "align": "left",
                                        },
                                        {
                                            "name": "error_type",
                                            "label": "Error Type",
                                            "field": "error_type",
                                            "sortable": True,
                                            "align": "left",
                                        },
                                        {
                                            "name": "error_message",
                                            "label": "Error Message",
                                            "field": "error_message",
                                            "sortable": False,
                                            "align": "left",
                                            "classes": "max-w-xs truncate",
                                        },
                                        {
                                            "name": "duration",
                                            "label": "Duration",
                                            "field": "duration",
                                            "sortable": True,
                                            "align": "right",
                                        },
                                    ],
                                    rows=rows,
                                    pagination=10,
                                ).classes("w-full flex-grow")

                                dialog.open()

                        # --- ROW 1: Key Performance Indicators ---
                        with ui.grid().classes("w-full gap-6 grid-cols-12"):
                            # Overall PSS Gauge (3 cols)
                            with ui.card().classes(
                                "col-span-12 sm:col-span-6 xl:col-span-3 p-4"
                                " shadow-sm border border-gray-200 bg-white"
                                " flex flex-col justify-between"
                            ):
                                with ui.row().classes(
                                    "w-full pb-2 mb-2 border-b border-gray-200 items-center justify-between"
                                ):
                                    ui.label("Overall PSS").classes("font-bold text-gray-700 text-lg").tooltip(
                                        "0-100 Stability Score. Higher is better."
                                    )
                                    ui.icon("speed", size="sm").classes("text-gray-400")
                                ui.plotly(create_gauge_chart(report["pss"], "")).classes("w-full h-40")

                            # Total Samples (3 cols)
                            timestamps = [t.get("timestamp", 0) for t in raw_traces]
                            duration_window = (
                                max(timestamps) - min(timestamps) if timestamps and len(timestamps) > 1 else 0
                            )
                            rps = len(raw_traces) / duration_window if duration_window > 0 else 0
                            kpi_card(
                                "Total Traces",
                                f"{len(raw_traces):,}",
                                "Recorded Executions",
                                "dataset",
                                "text-blue-600",
                                extra_details={
                                    "Time Window": f"{duration_window:.1f}s",
                                    "Throughput": f"{rps:.1f} req/s",
                                },
                            ).classes("col-span-12 sm:col-span-6 xl:col-span-3")

                            # Error Rate (3 cols)
                            error_traces = [t for t in raw_traces if t.get("error")]
                            err_count = len(error_traces)
                            err_rate = (err_count / len(raw_traces) * 100) if raw_traces else 0
                            from collections import Counter

                            failing_modules = [t.get("module", "unknown") for t in error_traces]
                            top_offender = Counter(failing_modules).most_common(1)
                            top_offender_name = top_offender[0][0] if top_offender else "None"
                            affected_count = len(set(failing_modules))
                            kpi_card(
                                "Error Rate",
                                f"{err_rate:.1f}%",
                                f"{err_count} Failed Traces",
                                "error_outline",
                                "text-red-500",
                                extra_details={
                                    "Affected Mods": f"{affected_count}",
                                    "Top Offender": top_offender_name,
                                },
                                on_click=lambda: show_failures(),
                            ).classes("col-span-12 sm:col-span-6 xl:col-span-3")

                            # Avg Latency (3 cols)
                            import statistics

                            durations = [t.get("duration", 0) for t in raw_traces]
                            avg_lat = statistics.mean(durations) if durations else 0
                            max_lat = max(durations) if durations else 0
                            sorted_dur = sorted(durations)
                            p95_lat = sorted_dur[int(len(sorted_dur) * 0.95)] if sorted_dur else 0
                            kpi_card(
                                "Avg Latency",
                                f"{avg_lat * 1000:.1f}ms",
                                "Per Execution",
                                "timer",
                                "text-gray-700",
                                extra_details={
                                    "P95 Latency": f"{p95_lat * 1000:.1f}ms",
                                    "Max Spike": f"{max_lat * 1000:.1f}ms",
                                },
                            ).classes("col-span-12 sm:col-span-6 xl:col-span-3")

                        # Row 2: Metric Breakdown + AI Advisor (4 + 8 cols)
                        with ui.grid().classes("w-full gap-6 grid-cols-12"):
                            # Metric Breakdown (4 cols)
                            with ui.card().classes(
                                "col-span-12 md:col-span-4 shadow-sm border border-gray-200 bg-white p-4 flex flex-col"
                            ):
                                with ui.row().classes(
                                    "w-full pb-2 border-b border-gray-200 items-center justify-between"
                                ):
                                    ui.label("Metric Breakdown").classes("font-bold text-gray-700 text-lg")
                                    ui.icon("monitoring", size="sm").classes("text-gray-400")

                                # Vertical list layout for gauges (Compact)
                                with ui.column().classes("w-full gap-3 mt-2"):
                                    for metric_name, score_value in report["breakdown"].items():
                                        with ui.row().classes("w-full items-center justify-between"):
                                            score_color_class = (
                                                "text-green-600"
                                                if score_value >= 0.90
                                                else "text-amber-500"
                                                if score_value >= 0.70
                                                else "text-red-600"
                                            )
                                            progress_color = (
                                                "positive"
                                                if score_value >= 0.9
                                                else "warning"
                                                if score_value >= 0.7
                                                else "negative"
                                            )
                                            ui.label(metric_name.replace("_", " ").title()).classes(
                                                "text-sm font-medium text-gray-600"
                                            )

                                            with ui.row().classes("items-center gap-3"):
                                                ui.label(f"{int(score_value * 100)}").classes(
                                                    f"text-sm font-bold {score_color_class}"
                                                )
                                                ui.linear_progress(value=score_value, show_value=False).props(
                                                    f"color={progress_color}"
                                                ).classes("w-24")

                            # AI Advisor (8 cols)
                            with ui.card().classes(
                                "col-span-12 md:col-span-8 shadow-sm border border-gray-200 bg-white p-6 flex flex-col"
                            ):
                                with ui.row().classes("items-center gap-3 mb-4"):
                                    ui.icon("auto_awesome", size="md").classes("text-purple-600")
                                    ui.label("AI Diagnostics").classes("text-xl font-bold text-gray-800")

                                analysis_text, recommendations_text = generate_ai_diagnostics(report, df)
                                with ui.scroll_area().classes("h-64 w-full pr-2"):
                                    ui.markdown(f"**Analysis:**\n{analysis_text}").classes(
                                        "text-sm text-gray-600 leading-relaxed font-mono"
                                    )
                                    ui.markdown(f"**Recommendations:**\n{recommendations_text}").classes(
                                        "text-sm text-gray-600 leading-relaxed font-mono mt-4"
                                    )

                        # Row 3: Historical Trend + Module Table (6 + 6 cols)
                        with ui.grid().classes("w-full gap-6 grid-cols-12"):
                            # Historical Trend (6 cols)
                            with ui.card().classes(
                                "col-span-12 lg:col-span-6 shadow-sm border border-gray-200 bg-white p-0 flex flex-col"
                            ):
                                with ui.row().classes(
                                    "w-full p-4 border-b border-gray-200 items-center justify-between"
                                ):
                                    ui.label("Long-term Stability History").classes("font-bold text-gray-700 text-lg")
                                    ui.icon("history", size="sm").classes("text-gray-400")
                                # Fixed height to prevent infinite growth loop
                                ui.plotly(create_historical_chart(history_data)).classes("w-full h-96")

                            # Module Table (6 cols)
                            with ui.card().classes(
                                "col-span-12 lg:col-span-6 shadow-sm border border-gray-200 bg-white p-0"
                            ):
                                if df is not None and not df.empty:
                                    table_rows = df.to_dict("records")
                                    for row in table_rows:
                                        if "timing" in row:
                                            row["timing"] = f"{row['timing']:.2f}"
                                        if "errors" in row:
                                            row["errors"] = f"{row['errors']:.2f}"

                                    with ui.row().classes(
                                        "w-full p-4 border-b border-gray-200 items-center justify-between"
                                    ):
                                        ui.label("Module Performance").classes("font-bold text-gray-700 text-lg")

                                    ui.table(
                                        columns=[
                                            {
                                                "name": "module",
                                                "label": "Module Name",
                                                "field": "module",
                                                "align": "left",
                                                "sortable": True,
                                                "classes": (
                                                    "text-gray-700 cursor-pointer"
                                                    " hover:text-blue-600 transition-colors"
                                                    " max-w-[150px] truncate"
                                                ),
                                            },
                                            {
                                                "name": "pss",
                                                "label": "PSS",
                                                "field": "pss",
                                                "sortable": True,
                                                "align": "center",
                                            },
                                            {
                                                "name": "traces",
                                                "label": "Samples",
                                                "field": "traces",
                                                "sortable": True,
                                                "align": "center",
                                            },
                                            {
                                                "name": "timing",
                                                "label": "Timing",
                                                "field": "timing",
                                                "sortable": True,
                                                "align": "right",
                                            },
                                            {
                                                "name": "errors",
                                                "label": "Errors",
                                                "field": "errors",
                                                "sortable": True,
                                                "align": "right",
                                            },
                                        ],
                                        rows=table_rows,
                                        row_key="module",
                                        pagination=10,
                                    ).classes("w-full flat-table").on(
                                        "cell_click",
                                        lambda e: show_module_detail_dialog(e.args[1]["module"])
                                        if e.args[0]["name"] == "module"
                                        else None,
                                    )
                                else:
                                    ui.label("No module performance data available.").classes(
                                        "text-gray-500 italic p-4"
                                    )

                # --- TAB 2: METRICS (DEEP DIVE) ---
                with ui.tab_panel("metrics"):
                    with ui.column().classes("w-full gap-6"):
                        with ui.row().classes("items-center justify-between w-full"):
                            ui.label("Real-time Stability Trends").classes("text-xl font-bold text-gray-800")

                            window_size = ui.select(
                                ["10s", "30s", "1min", "5min", "10min"],
                                value="1min",
                                label="Window Size",
                            ).classes("w-32")

                        @ui.refreshable
                        def refresh_metrics_chart():
                            try:
                                ts_df = processor.get_metric_timeseries(window_size.value)
                                with ui.card().classes(
                                    "w-full shadow-sm border border-gray-200 bg-white p-0 flex flex-col"
                                ):
                                    ui.plotly(plot_stability_trends(ts_df)).classes("w-full h-[600px]")
                            except Exception as e:
                                with ui.card().classes("w-full bg-red-50 p-4"):
                                    ui.label(f"Error loading metrics chart: {e}").classes("text-red-500")

                        window_size.on_value_change(refresh_metrics_chart.refresh)
                        refresh_metrics_chart()

                # --- TAB 3: DIAGNOSTICS ---
                with ui.tab_panel("diagnostics"):
                    with ui.column().classes("w-full gap-6"):
                        # Heatmaps Row
                        with ui.grid().classes("w-full grid-cols-1 md:grid-cols-2 gap-6"):
                            # Error Heatmap
                            with ui.card().classes("shadow-sm border border-gray-200 bg-white p-0 flex flex-col"):
                                with ui.row().classes("w-full p-4 border-b border-gray-200"):
                                    ui.label("Error Clusters").classes("font-bold text-gray-700 text-lg")
                                ui.plotly(plot_error_heatmap(raw_traces)).classes("w-full h-80")

                            # Entropy Heatmap
                            with ui.card().classes("shadow-sm border border-gray-200 bg-white p-0 flex flex-col"):
                                with ui.row().classes("w-full p-4 border-b border-gray-200"):
                                    ui.label("Logic Complexity").classes("font-bold text-gray-700 text-lg")
                                ui.plotly(plot_entropy_heatmap(raw_traces)).classes("w-full h-80")

                        # AI Advisor (Moved from Overview)
                        with ui.card().classes("w-full shadow-sm border border-gray-200 bg-white p-6"):
                            with ui.row().classes("items-center gap-3 mb-4"):
                                ui.icon("auto_awesome", size="md").classes("text-purple-600")
                                ui.label("AI Diagnostics").classes("text-xl font-bold text-gray-800")

                            analysis_text, recommendations_text = generate_ai_diagnostics(report, df)
                            ui.markdown(f"**Analysis:**\n{analysis_text}").classes(
                                "text-sm text-gray-600 leading-relaxed font-mono"
                            )
                            ui.markdown(f"**Recommendations:**\n{recommendations_text}").classes(
                                "text-sm text-gray-600 leading-relaxed font-mono mt-4"
                            )

                # --- TAB 4: PERFORMANCE ---
                with ui.tab_panel("performance"):
                    with ui.column().classes("w-full gap-6"):
                        # Latency Percentiles (Moved from Overview)
                        with ui.card().classes("w-full shadow-sm border border-gray-200 bg-white p-0 flex flex-col"):
                            with ui.row().classes("w-full p-4 border-b border-gray-200 items-center justify-between"):
                                ui.label("Latency Percentiles").classes("font-bold text-gray-700 text-lg")
                                ui.icon("show_chart", size="sm").classes("text-gray-400")
                            ui.plotly(create_trend_chart(raw_traces)).classes("w-full h-80")

                        # Concurrency Distribution
                        with ui.card().classes("w-full shadow-sm border border-gray-200 bg-white p-0 flex flex-col"):
                            with ui.row().classes("w-full p-4 border-b border-gray-200 items-center justify-between"):
                                ui.label("Concurrency Wait Times").classes("font-bold text-gray-700 text-lg")
                                ui.icon("speed", size="sm").classes("text-gray-400")
                            ui.plotly(plot_concurrency_dist(raw_traces)).classes("w-full h-80")

        # --- HEADER UPDATES ---
        def update_header_stats():
            # Update Clock
            try:
                # Use astimezone() for local time awareness
                now = datetime.now().astimezone()
                clock_label.set_text(now.strftime("%Y-%m-%d %H:%M:%S %Z"))
            except Exception:
                clock_label.set_text(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            # Update Freshness
            if last_mtime > 0:
                age = time.time() - last_mtime
                if age < 60:
                    freshness_label.set_text(f"Data: {int(age)}s ago")
                elif age < 3600:
                    freshness_label.set_text(f"Data: {int(age / 60)}m ago")
                else:
                    freshness_label.set_text(f"Data: {int(age / 3600)}h ago")
            else:
                freshness_label.set_text("Data: Pending")

        ui.timer(1.0, update_header_stats)

        # --- REFRESH LOGIC ---
        def check_refresh():
            nonlocal last_mtime
            if not os.path.exists(trace_file):
                return
            try:
                mtime = os.path.getmtime(trace_file)
                if mtime > last_mtime:
                    last_mtime = mtime
                    content.refresh()
            except OSError:
                pass

        # --- INIT ---
        ui.timer(1.0, check_refresh)
        if os.path.exists(trace_file):
            last_mtime = os.path.getmtime(trace_file)

        content()


def main():
    """Entry point for the pypss-board CLI command."""
    import sys

    if len(sys.argv) > 1:
        start_board(sys.argv[1])
    else:
        print("Usage: pypss-board <trace_file>")
        sys.exit(1)


if __name__ in {"__main__", "__mp_main__"}:
    # Force standard asyncio loop to prevent uvloop crashes in virtualized/headless envs
    os.environ["UVICORN_LOOP"] = "asyncio"

    main()

    ui.run(
        title=GLOBAL_CONFIG.ui_title,
        reload=False,
        port=GLOBAL_CONFIG.ui_port,
        favicon="📊",
        show=False,
    )
