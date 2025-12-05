import os
from datetime import datetime
import time
from nicegui import ui, app
from pypss.board.data_loader import load_trace_data
from pypss.utils.config import GLOBAL_CONFIG
from pypss.board.charts import (
    create_trend_chart,
    create_gauge_chart,
    create_historical_chart,
)
from pypss.core import compute_pss_from_traces
from pypss.storage import get_storage_backend


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
    docs_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "docs")
    )
    app.add_static_files("/static", docs_dir)

    # State
    last_mtime = 0.0

    # AI Diagnostics Logic
    def generate_ai_diagnostics(report, df):
        analysis_summary = []
        recommendations = []

        overall_pss = report["pss"]
        if overall_pss >= 90:
            analysis_summary.append("Overall system stability is **Excellent**.")
            recommendations.append(
                "Maintain current best practices and monitor for any regressions."
            )
        elif overall_pss >= 70:
            analysis_summary.append(
                "System stability is **Good**, but shows some areas for improvement."
            )
            recommendations.append(
                "Review the 'Metric Breakdown' and 'Module Performance' for specific areas to optimize."
            )
        else:
            analysis_summary.append(
                "System stability is **Unstable**. Immediate attention is recommended."
            )
            recommendations.append(
                "Prioritize investigating the root causes identified below."
            )

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
                recommendations.append(
                    "Review complex conditional logic and ensure predictable execution paths."
                )
            elif worst_metric == "concurrency_chaos":
                recommendations.append(
                    "Analyze resource contention and thread/process synchronization issues."
                )

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

        return "\n".join([f"* {s}" for s in analysis_summary]), "\n".join(
            [f"* {r}" for r in recommendations]
        )

    # Anomaly Detection Logic
    def check_for_anomalies(report, raw_traces):
        CRITICAL_PSS_THRESHOLD = GLOBAL_CONFIG.dashboard_critical_pss_threshold
        WARNING_ERROR_RATE = GLOBAL_CONFIG.dashboard_warning_error_rate

        is_anomaly = False
        anomaly_messages = []

        overall_pss = report["pss"]
        if overall_pss < CRITICAL_PSS_THRESHOLD:
            is_anomaly = True
            anomaly_messages.append(
                f"CRITICAL: Overall PSS ({overall_pss}/100) is below {CRITICAL_PSS_THRESHOLD}."
            )

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
            with ui.row().classes(
                "w-full bg-gray-50 p-4 border-b border-gray-200 items-center justify-between"
            ):
                ui.label("PyPSS Stability Guide").classes(
                    "text-lg font-bold text-gray-800"
                )
                ui.button(icon="close", on_click=dialog.close).props("flat round dense")

            with ui.column().classes("p-6 gap-6 overflow-y-auto max-h-[80vh]"):
                # Section 1: PSS Score
                with ui.column().classes("gap-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("health_and_safety", size="sm").classes(
                            "text-green-600"
                        )
                        ui.label("What is the PSS Score?").classes(
                            "text-md font-bold text-gray-700"
                        )
                    ui.markdown(
                        """
                        The **Python Stability Score (PSS)** is a 0-100 rating of your system's reliability.
                        *   **90-100:** Excellent. Stable and predictable.
                        *   **70-89:** Good. Minor variance or occasional glitches.
                        *   **< 70:** Unstable. High latency, errors, or resource spikes detected.
                        """
                    ).classes("text-sm text-gray-600 ml-8")

                ui.separator()

                # Section 2: Latency Percentiles
                with ui.column().classes("gap-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("show_chart", size="sm").classes("text-blue-600")
                        ui.label("Understanding Latency (P50 / P90 / P99)").classes(
                            "text-md font-bold text-gray-700"
                        )
                    ui.markdown(
                        """
                        Averages lie. We use **Percentiles** to show the true user experience over the **Execution Timeline** (Left = Start, Right = End):
                        
                        *   <span class="text-green-600 font-bold">P50 (Median):</span> The **Typical User**. 50% of requests are faster than this.
                        *   <span class="text-orange-500 font-bold">P90 (Heavy Load):</span> The **Slow User**. 90% of requests are faster than this.
                        *   <span class="text-red-600 font-bold">P99 (Worst Case):</span> The **Tail End**. 1% of users experience this slowness.
                        """
                    ).classes("text-sm text-gray-600 ml-8")

                ui.separator()

                # Section 3: Stability Bands
                with ui.column().classes("gap-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("layers", size="sm").classes("text-purple-600")
                        ui.label("The 'Stability Gap'").classes(
                            "text-md font-bold text-gray-700"
                        )
                    ui.markdown(
                        """
                        In the **Latency Percentiles** chart, look at the gap between the <span class="text-green-600">Green Line (P50)</span> and the <span class="text-red-600">Red Line (P99)</span>.
                        
                        *   **Narrow Gap:** Predictable performance. (Good)
                        *   **Wide Gap:** Unpredictable "jitter". Some users are waiting much longer than others. (Bad)
                        """
                    ).classes("text-sm text-gray-600 ml-8")

                ui.separator()

                # Section 4: Scoring Breakdown
                with ui.column().classes("gap-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("fact_check", size="sm").classes("text-indigo-600")
                        ui.label("Scoring Breakdown (The 5 Pillars)").classes(
                            "text-md font-bold text-gray-700"
                        )
                    ui.markdown(
                        """
                        Your PSS score is calculated from these 5 metrics:
                        
                        1.  **Timing Stability:** Do tasks take the same amount of time every run? (Low variance = High Score)
                        2.  **Memory Stability:** Is memory usage flat, or does it spike unpredictably? (Flat = High Score)
                        3.  **Error Volatility:** Are errors rare and isolated, or do they happen in bursts? (No bursts = High Score)
                        4.  **Branching Entropy:** Does the code take random different paths (if/else) or is it deterministic? (Predictable paths = High Score)
                        5.  **Concurrency Chaos:** Are threads waiting on locks/resources? (Low wait time = High Score)
                        """
                    ).classes("text-sm text-gray-600 ml-8")

                ui.separator()

                # Section 5: Configuration
                with ui.column().classes("gap-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("settings", size="sm").classes("text-gray-600")
                        ui.label("Configuring PyPSS").classes(
                            "text-md font-bold text-gray-700"
                        )
                    ui.markdown(
                        """
                        You can tune the PSS algorithm using the **Settings** button (the gear icon in the header).

                        *   **Sampling:** Control how many data points are collected. `Sample Rate` is great for high-traffic apps, while `Max Traces` limits memory usage.
                        *   **PSS Weights:** Adjust the importance of each of the 5 pillars. The weights must sum to 1.0.
                        *   **Sensitivity:** Advanced options to fine-tune how the algorithm detects anomalies in timing, memory, and errors.

                        **Example:** If your application is a data processing pipeline where occasional errors are less important than consistent processing time, you could:
                        1.  Decrease the **Error Volatility** weight (e.g., from `0.2` to `0.1`).
                        2.  Increase the **Timing Stability** weight (e.g., from `0.3` to `0.4`).
                        
                        This makes the PSS score more sensitive to performance and less sensitive to errors.
                        """
                    ).classes("text-sm text-gray-600 ml-8")

                ui.separator()

                # Section 6: Historical Trends
                with ui.column().classes("gap-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("history", size="sm").classes("text-blue-500")
                        ui.label("Historical Trends").classes(
                            "text-md font-bold text-gray-700"
                        )
                    ui.markdown(
                        """
                        The **Historical Stability Trend** chart shows how your PSS score has evolved over time.
                        *   **Blue Line:** Overall PSS Score.
                        *   **Dashed Lines:** Individual stability pillars (Timing, Memory, Errors).
                        *   **Drops:** A sudden drop in the blue line indicates a regression. Hover over the point to see which pillar caused it.
                        """
                    ).classes("text-sm text-gray-600 ml-8")

        dialog.open()

    def show_settings_dialog(
        current_report=None, current_df=None, current_trace_file=None
    ):
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
                ui.label("PyPSS Configuration").classes(
                    "text-lg font-bold text-gray-800"
                )
                ui.button(icon="close", on_click=dialog.close).props("flat round dense")

            # --- Tabs ---
            with ui.tabs().props("align=left").classes("w-full") as tabs:
                ui.tab("sampling", label="Sampling", icon="scatter_plot")
                ui.tab("weights", label="PSS Weights", icon="balance")
                ui.tab("thresholds", label="Sensitivity", icon="tune")

            # --- Tab Panels (Main Content) ---
            with ui.tab_panels(tabs, value="sampling").classes(
                "w-full overflow-y-auto"
            ):
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
                                ui.label("Max Traces (Buffer Size)").classes(
                                    "text-md font-semibold"
                                )
                                ui.icon("help_outline", size="xs").tooltip(
                                    "The maximum number of traces to keep in the buffer."
                                ).classes("text-gray-500 cursor-pointer")
                            ui.number(value=settings["max_traces"]).bind_value(
                                settings, "max_traces"
                            ).props("outlined dense").classes("w-full")

                # --- Weights Panel ---
                with ui.tab_panel("weights"):
                    with ui.column().classes("gap-4 p-4"):
                        sum_label = ui.label().classes(
                            "font-mono font-bold self-end mb-2 px-2 py-1 rounded-md"
                        )

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
                                ui.slider(
                                    min=0.0, max=1.0, step=0.01, value=settings[key]
                                ).bind_value(settings, key).props("label-always").on(
                                    "update:model-value", lambda: update_sum()
                                )
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
                                    ui.label(label_text).classes(
                                        "text-md font-semibold"
                                    )
                                    ui.icon("help_outline", size="xs").tooltip(
                                        tooltip_text
                                    ).classes("text-gray-500 cursor-pointer")
                                ui.number(value=settings[key]).bind_value(
                                    settings, key
                                ).props(f"outlined dense step={step}").classes("w-full")
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
                ui.button("Cancel", on_click=dialog.close).props("flat").classes(
                    "text-gray-700"
                )
                ui.button("Save Changes", on_click=lambda: save_settings()).props(
                    "color=primary"
                )

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
            GLOBAL_CONFIG.mem_spike_threshold_ratio = settings[
                "mem_spike_threshold_ratio"
            ]
            GLOBAL_CONFIG.delta = settings["delta"]
            GLOBAL_CONFIG.error_spike_threshold = settings["error_spike_threshold"]
            GLOBAL_CONFIG.consecutive_error_threshold = int(
                settings["consecutive_error_threshold"]
            )
            GLOBAL_CONFIG.concurrency_wait_threshold = settings[
                "concurrency_wait_threshold"
            ]

            GLOBAL_CONFIG.save()  # Save to pypss.toml
            ui.notify("Settings saved and dashboard refreshed!", type="positive")
            dialog.close()
            content.refresh()  # Refresh main dashboard to apply new settings

        dialog.open()

    # Theme state (reactive)

    # KPI card helper function (moved outside content())
    def kpi_card(
        title, value, subtitle, icon, color_class, extra_details=None, on_click=None
    ):
        # Card background is crucial here
        card_classes = "col-span-12 sm:col-span-6 md:col-span-3 p-4 shadow-sm border border-gray-200 bg-white flex flex-col justify-between"
        if on_click:
            card_classes += " cursor-pointer hover:shadow-md transition-shadow"

        with (
            ui.card()
            .classes(card_classes)
            .on("click", on_click if on_click else lambda: None)
        ):
            with ui.row().classes("justify-between items-start w-full"):
                with ui.column().classes("gap-1"):
                    ui.label(title).classes(
                        "text-sm font-semibold text-gray-600 uppercase tracking-wider"
                    )
                    ui.label(value).classes(f"text-3xl font-black {color_class}")
                    ui.label(subtitle).classes("text-xs font-medium text-gray-400")
                ui.icon(icon, size="3em").classes(f"{color_class} opacity-10")

            if extra_details:
                ui.separator().classes("my-2")
                with ui.row().classes(
                    "w-full justify-between gap-2 text-xs text-gray-500"
                ):
                    for label, val in extra_details.items():
                        with ui.column().classes("gap-0"):
                            ui.label(label).classes("font-semibold text-gray-400")
                            ui.label(val).classes("font-mono font-medium")

    # --- LAYOUT ---
    ui.query("body").classes("bg-white flex flex-col h-screen")

    # Header (Theme-aware)
    with (
        ui.header()
        .classes(
            "bg-white text-gray-900 border-b border-gray-200 items-center px-6 h-16"
        )
        .props("elevated=false")
        .style('transition: all 0.3s ease; font-family: "Google Sans Mono", monospace;')
    ):
        # Logo & Title
        with ui.row().classes("items-center gap-4"):
            ui.image("/static/TDMC.png").classes("w-10 h-10 object-contain")

            with ui.column().classes("gap-0"):
                ui.label("PyPSS Platform").classes(
                    "text-xl font-bold tracking-tight leading-none text-gray-900"
                )
                ui.label("Stability Intelligence").classes(
                    "text-xs font-medium text-gray-600 uppercase tracking-widest"
                )

        ui.space()

        # Right Actions (Theme-aware)
        with ui.row().classes("items-center gap-4"):
            # Data Freshness
            freshness_label = ui.label("Data: --").classes(
                "text-xs font-mono font-bold text-gray-500"
            )

            # Clock
            clock_label = ui.label().classes(
                "text-xs font-mono text-gray-600 border-r border-gray-300 pr-4"
            )

            # Status Indicator
            with ui.row().classes(
                "items-center gap-2 bg-gray-50 rounded-full px-3 py-1 border border-gray-200"
            ):
                ui.icon("fiber_manual_record", size="12px").classes(
                    "text-green-500 animate-pulse"
                )
                ui.label("Live").classes("text-xs font-bold text-gray-700")

            # Anomaly Alert Indicator
            anomaly_alert_icon = ui.icon("warning", size="20px").classes(
                "text-red-500 hidden"
            )
            with anomaly_alert_icon:
                anomaly_tooltip = ui.tooltip("No anomalies detected.")

            # Help Button
            ui.button(icon="help_outline", on_click=show_help).props(
                "flat round dense color=grey-7"
            ).tooltip("Guide: How to read this dashboard")

            # Settings Button
            ui.button(
                icon="settings",
                on_click=lambda: show_settings_dialog(current_trace_file=trace_file),
            ).props("flat round dense color=grey-7").tooltip(
                "Configure PyPSS Parameters"
            )

            # Theme Toggle (Icon color adjusts)

    # --- DYNAMIC CONTENT ---
    # This will be the main content wrapper background, allowing normal scrolling
    with ui.column().classes("w-full bg-gray-50 p-6 gap-6 flex-grow overflow-y-auto"):

        @ui.refreshable
        def content():
            report, df, raw_traces = load_trace_data(trace_file)

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
                with ui.column().classes(
                    "w-full h-[80vh] items-center justify-center bg-white"
                ):
                    ui.icon("analytics", size="6rem").classes("text-gray-400")
                    ui.label("Waiting for Trace Data...").classes(
                        "text-2xl font-light text-gray-500 mt-4"
                    )
                    ui.spinner(size="lg", color="primary").classes("mt-4")
                # Hide anomaly icon if no data
                anomaly_alert_icon.classes(
                    replace="text-red-500 animate-pulse", add="hidden"
                )
                anomaly_tooltip.set_text("No data to analyze.")
                return

            # Check for anomalies and update alert icon
            is_anomaly, anomaly_message = check_for_anomalies(report, raw_traces)
            if is_anomaly:
                anomaly_alert_icon.classes(
                    replace="hidden", add="text-red-500 animate-pulse"
                )
                anomaly_tooltip.set_text(anomaly_message)
            else:
                anomaly_alert_icon.classes(
                    replace="text-red-500 animate-pulse", add="hidden"
                )
                anomaly_tooltip.set_text("No anomalies detected.")

            # --- ROW 1: KPI CARDS AND OVERALL PSS GAUGE ---

            # Module Detail Dialog
            def show_module_detail_dialog(module_name: str):
                module_traces = [
                    t for t in raw_traces if t.get("module") == module_name
                ]
                if not module_traces:
                    ui.notify(f"No traces found for module {module_name}.", type="info")
                    return

                # Calculate module-specific report (can be outside refreshable if only once needed)
                module_report = compute_pss_from_traces(module_traces)

                with (
                    ui.dialog() as dialog,
                    ui.card().classes("w-full max-w-5xl h-[90vh] flex flex-col"),
                ):
                    with ui.row().classes(
                        "w-full items-center justify-between border-b pb-2"
                    ):
                        ui.label(f"Module Performance: {module_name}").classes(
                            "text-xl font-bold text-gray-800"
                        )
                        ui.label(f"PSS: {module_report['pss']}/100").classes(
                            "text-lg font-semibold text-gray-700"
                        )
                        ui.button(icon="close", on_click=dialog.close).props(
                            "flat round dense"
                        )

                    with ui.column().classes(
                        "flex-grow overflow-y-auto w-full gap-4 p-4"
                    ):
                        # Module-specific Latency Trend
                        with ui.card().classes(
                            "w-full shadow-sm border border-gray-200 bg-white p-0 flex flex-col"
                        ):
                            with ui.row().classes(
                                "w-full p-4 border-b border-gray-200 items-center justify-between"
                            ):
                                ui.label(
                                    f"Latency Percentiles for {module_name}"
                                ).classes("font-bold text-gray-700 text-lg")
                                ui.icon("show_chart", size="sm").classes(
                                    "text-gray-400"
                                )
                            ui.plotly(create_trend_chart(module_traces)).classes(
                                "w-full h-64"
                            )

                        # Module-specific Failed Traces
                        failed_module_traces_all = [
                            t for t in module_traces if t.get("error")
                        ]

                        @ui.refreshable
                        def refresh_module_failed_table():
                            if not failed_module_traces_all:
                                ui.label("No failed traces for this module.").classes(
                                    "text-gray-500 italic"
                                )
                                return

                            # Add search/filter inputs for module-specific failed traces if desired, similar to show_failures.
                            # For now, just display all failed traces for the module.

                            rows = []
                            for t in failed_module_traces_all:
                                ts_str = datetime.fromtimestamp(
                                    t.get("timestamp", 0)
                                ).strftime("%H:%M:%S")
                                rows.append(
                                    {
                                        "time": ts_str,
                                        "function": t.get("name", "unknown"),
                                        "error_type": t.get("exception_type", "N/A"),
                                        "error_message": t.get(
                                            "exception_message", "N/A"
                                        ),
                                        "duration": f"{t.get('duration', 0) * 1000:.1f}ms",
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
                                    ui.icon("error_outline", size="sm").classes(
                                        "text-red-400"
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

                        refresh_module_failed_table()  # Initial render

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
                    with ui.row().classes(
                        "w-full items-center justify-between border-b pb-2"
                    ):
                        ui.label(f"All Failed Traces ({len(failed_traces)})").classes(
                            "text-xl font-bold text-red-600"
                        )
                        ui.button(icon="close", on_click=dialog.close).props(
                            "flat round dense"
                        )

                    rows = []
                    for t in failed_traces:
                        ts_str = datetime.fromtimestamp(t.get("timestamp", 0)).strftime(
                            "%H:%M:%S"
                        )
                        rows.append(
                            {
                                "time": ts_str,
                                "module": t.get("module", "unknown"),
                                "function": t.get("name", "unknown"),
                                "error_type": t.get("exception_type", "N/A"),
                                "error_message": t.get("exception_message", "N/A"),
                                "duration": f"{t.get('duration', 0) * 1000:.1f}ms",
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

            # 2. Dashboard Grid (Theme-aware)
            with ui.grid().classes("w-full gap-6 grid-cols-12"):
                # Overall PSS Gauge Chart
                with ui.card().classes(
                    "col-span-12 sm:col-span-6 md:col-span-3 p-4 shadow-sm border border-gray-200 bg-white flex flex-col"
                ):
                    with ui.row().classes(
                        "w-full pb-2 mb-2 border-b border-gray-200 items-center justify-between"
                    ):
                        ui.label("Overall PSS").classes(
                            "font-bold text-gray-700 text-lg"
                        ).tooltip("0-100 Stability Score. Higher is better.")
                        ui.icon("speed", size="sm").classes("text-gray-400")
                    ui.plotly(create_gauge_chart(report["pss"], "")).classes(
                        "w-full h-48"
                    )

                # Total Samples Calculations
                timestamps = [t.get("timestamp", 0) for t in raw_traces]
                duration_window = (
                    max(timestamps) - min(timestamps)
                    if timestamps and len(timestamps) > 1
                    else 0
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
                )

                # Error Rate Calculations
                error_traces = [t for t in raw_traces if t.get("error")]
                err_count = len(error_traces)
                err_rate = (err_count / len(raw_traces) * 100) if raw_traces else 0

                # Find top offender
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
                )

                # Avg Latency Calculations
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
                )

                # Add tooltip for Avg Latency manually since it's inside a helper
                # Note: kpi_card helper doesn't support adding tooltips to internal labels easily without refactor.
                # Instead, I will modify the Latency Percentiles and Metric Breakdown labels below which are accessible.

                # --- ROW 2: MAIN CHARTS ---

                # Metric Breakdown Gauges
                with ui.card().classes(
                    "col-span-12 md:col-span-4 shadow-sm border border-gray-200 bg-white p-4 flex flex-col"
                ):
                    with ui.row().classes(
                        "w-full pb-2 border-b border-gray-200 items-center justify-between"
                    ):
                        ui.label("Metric Breakdown").classes(
                            "font-bold text-gray-700 text-lg"
                        ).tooltip(
                            "Scores for individual stability pillars (Timing, Memory, Errors, etc.)"
                        )
                        ui.icon("monitoring", size="sm").classes(
                            "text-gray-400"
                        )  # Changed icon

                    # Container for individual gauges
                    with ui.grid().classes("w-full grid-cols-2 gap-y-4 gap-x-2 mt-4"):
                        for metric_name, score_value in report["breakdown"].items():
                            with ui.column().classes("items-center justify-center"):
                                # Determine color based on score_value
                                score_color_class = (
                                    "text-green-600"
                                    if score_value >= 0.90
                                    else "text-amber-500"
                                    if score_value >= 0.70
                                    else "text-red-600"
                                )

                                metric_descriptions = {
                                    "timing_stability": "Consistency of task execution time.",
                                    "memory_stability": "Predictability of memory usage.",
                                    "error_volatility": "Frequency and burstiness of errors.",
                                    "branching_entropy": "Determinism of code execution paths.",
                                    "concurrency_chaos": "Resource contention and wait times.",
                                }

                                ui.label(metric_name.replace("_", " ").title()).classes(
                                    f"text-xs font-semibold {score_color_class} mb-1"
                                )
                                ui.label(
                                    metric_descriptions.get(metric_name, "")
                                ).classes(
                                    "text-tiny text-gray-500 text-center mx-1"
                                ).tooltip(metric_descriptions.get(metric_name, ""))
                                ui.plotly(
                                    create_gauge_chart(round(score_value, 2) * 100, "")
                                ).classes("w-36 h-36")  # Slightly larger gauges

                # Trend Chart
                with ui.card().classes(
                    "col-span-12 md:col-span-8 shadow-sm border border-gray-200 bg-white p-0 flex flex-col"
                ):
                    with ui.row().classes(
                        "w-full p-4 border-b border-gray-200 items-center justify-between"
                    ):
                        ui.label("Latency Percentiles").classes(
                            "font-bold text-gray-700 text-lg"
                        ).tooltip(
                            "P50 (Green) = Typical. P99 (Red) = Worst Case. Wide gap = Instability."
                        )
                        ui.icon("show_chart", size="sm").classes("text-gray-400")
                    ui.plotly(create_trend_chart(raw_traces)).classes("w-full h-80")

                # Historical Trend Chart
                with ui.card().classes(
                    "col-span-12 shadow-sm border border-gray-200 bg-white p-0 flex flex-col"
                ):
                    with ui.row().classes(
                        "w-full p-4 border-b border-gray-200 items-center justify-between"
                    ):
                        ui.label("Long-term Stability History").classes(
                            "font-bold text-gray-700 text-lg"
                        ).tooltip("Evolution of PSS over multiple runs.")
                        ui.icon("history", size="sm").classes("text-gray-400")

                    ui.plotly(create_historical_chart(history_data)).classes(
                        "w-full h-64"
                    )

                # --- ROW 3: MODULE DETAILS & AI ---

                # AI Advisor
                with ui.card().classes(
                    "col-span-12 lg:col-span-4 shadow-sm border border-gray-200 bg-white p-6"
                ):
                    with ui.row().classes("items-center gap-3 mb-4"):
                        ui.icon("auto_awesome", size="md").classes("text-purple-600")
                        ui.label("AI Diagnostics").classes(
                            "text-xl font-bold text-gray-800"
                        )

                    analysis_text, recommendations_text = generate_ai_diagnostics(
                        report, df
                    )

                    ui.markdown(f"**Analysis:**\n{analysis_text}").classes(
                        "text-sm text-gray-600 leading-relaxed font-mono"
                    )
                    ui.markdown(
                        f"**Recommendations:**\n{recommendations_text}"
                    ).classes("text-sm text-gray-600 leading-relaxed font-mono mt-4")

                # Data Table
                with ui.card().classes(
                    "col-span-12 lg:col-span-8 shadow-sm border border-gray-200 bg-white p-0"
                ):
                    if df is not None and not df.empty:
                        table_rows = df.to_dict("records")
                        # Pre-format float values for display
                        for row in table_rows:
                            if "timing" in row:
                                row["timing"] = f"{row['timing']:.2f}"
                            if "errors" in row:
                                row["errors"] = f"{row['errors']:.2f}"

                        total_rows = len(table_rows)

                        # Pagination State (mutable dict to persist in closure)
                        pagination = {"page": 1, "per_page": 5}

                        # Calculate options
                        opts = {5, 10, 20, 50}
                        if total_rows > 0:
                            opts.add(total_rows)
                        options = sorted(list(opts))

                        # Default to showing all if small number of rows
                        if total_rows <= 50:
                            pagination["per_page"] = total_rows

                        # Safety fallback
                        if pagination["per_page"] not in options:
                            pagination["per_page"] = options[0] if options else 5

                        # Header with Selector
                        with ui.row().classes(
                            "w-full p-4 border-b border-gray-200 items-center justify-between"
                        ):
                            ui.label("Module Performance").classes(
                                "font-bold text-gray-700 text-lg"
                            )

                            def update_per_page(e):
                                pagination["per_page"] = e.value
                                pagination["page"] = 1
                                table_view.refresh()

                            ui.select(
                                options,
                                value=pagination["per_page"],
                                label="Per Page",
                                on_change=update_per_page,
                            ).classes("w-24")

                        # Refreshable Table View
                        @ui.refreshable
                        def table_view():
                            per_page = pagination["per_page"]
                            page = pagination["page"]

                            # Calculate Slice
                            start = (page - 1) * per_page
                            end = start + per_page
                            rows_slice = table_rows[start:end]

                            # Table
                            ui.table(
                                columns=[
                                    {
                                        "name": "module",
                                        "label": "Module Name",
                                        "field": "module",
                                        "align": "left",
                                        "sortable": True,
                                        "classes": "text-gray-700 cursor-pointer hover:text-blue-600 transition-colors",
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
                                rows=rows_slice,
                                row_key="module",
                                pagination=None,  # We handle pagination manually
                            ).classes("w-full flat-table").on(
                                "cell_click",
                                lambda e: show_module_detail_dialog(e.args[1]["module"])
                                if e.args[0]["name"] == "module"
                                else None,
                            )

                            # Navigation Controls
                            total_pages = (total_rows + per_page - 1) // per_page
                            # Ensure page is valid (if per_page increased)
                            if page > total_pages and total_pages > 0:
                                pagination["page"] = total_pages
                                # Trigger re-render? No, careful of recursion.
                                # Just rendering controls is fine, but content might be empty if we don't adjust `start`.
                                # Actually, better to adjust page before slice.
                                # For now, basic controls:

                            with ui.row().classes(
                                "w-full justify-between items-center p-4"
                            ):
                                ui.label(
                                    f"Page {pagination['page']} of {total_pages}"
                                ).classes("text-sm text-gray-600")

                                def go_page(new_page):
                                    pagination["page"] = max(
                                        1, min(new_page, total_pages)
                                    )
                                    table_view.refresh()

                                with ui.row().classes("items-center gap-2"):
                                    ui.button("<<", on_click=lambda: go_page(1)).props(
                                        "flat round dense"
                                    ).set_enabled(page > 1)
                                    ui.button(
                                        "<", on_click=lambda: go_page(page - 1)
                                    ).props("flat round dense").set_enabled(page > 1)
                                    ui.button(
                                        ">", on_click=lambda: go_page(page + 1)
                                    ).props("flat round dense").set_enabled(
                                        page < total_pages
                                    )
                                    ui.button(
                                        ">>", on_click=lambda: go_page(total_pages)
                                    ).props("flat round dense").set_enabled(
                                        page < total_pages
                                    )

                        table_view()

                    else:
                        with ui.row().classes("w-full p-4 border-b border-gray-200"):
                            ui.label("Module Performance").classes(
                                "font-bold text-gray-700 text-lg"
                            )
                        ui.label("No module performance data available.").classes(
                            "text-gray-500 italic p-4"
                        )

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

    # Start
    ui.run(
        title=GLOBAL_CONFIG.ui_title,
        reload=False,
        port=GLOBAL_CONFIG.ui_port,
        favicon="📊",
    )


if __name__ in {"__main__", "__mp_main__"}:
    import sys

    if len(sys.argv) > 1:
        start_board(sys.argv[1])
    else:
        print("Usage: python -m pypss.board.app <trace_file>")
