.. _metrics_explained:

###########
Understanding the Metrics
###########

The Python Program Stability Score (PSS) is a composite metric designed to provide a holistic view of a program's runtime stability. The final score is a weighted average of five individual sub-scores, each targeting a different dimension of stability.

.. list-table::
   :widths: 15 5 80
   :header-rows: 1

   * - Metric
     - Code
     - Description
   * - **Timing Stability**
     - ``TS``
     - **Goal:** Measures the consistency and predictability of your code's execution time.
       **How it's calculated:** It primarily uses the **Coefficient of Variation (CV)** of latencies. A lower CV means latencies are consistent, resulting in a higher score. It also penalizes high **tail latency** (p95/p50 ratio).
   * - **Memory Stability**
     - ``MS``
     - **Goal:** Measures how consistently the program uses memory.
       **How it's calculated:** The score is lowered by high memory fluctuation (standard deviation relative to the median) and is heavily penalized by large, sudden memory spikes (peak memory relative to the median).
   * - **Error Volatility**
     - ``EV``
     - **Goal:** Measures not just the presence of errors, but their frequency and tendency to occur in bursts.
       **How it's calculated:** It considers the overall **mean error rate** and uses the **Variance-to-Mean Ratio (VMR)** to penalize bursty, unpredictable errors more than consistent failures.
   * - **Branching Entropy**
     - ``BE``
     - **Goal:** Measures the predictability of the code paths taken at runtime.
       **How it's calculated:** This requires ``branch_tag`` s. It calculates the **Shannon entropy** of the branch tags that are executed. Lower entropy (more predictable paths) results in a higher score.
   * - **Concurrency Chaos**
     - ``CC``
     - **Goal:** Measures stability in concurrent applications by quantifying time spent waiting.
       **How it's calculated:** It analyzes the "wait time" (wall time minus CPU time). A high **Coefficient of Variation (CV)** of these wait times indicates inconsistent waiting periods and lowers the score.

Final PSS Calculation
=====================

1. Each of the five sub-scores is calculated, resulting in a value between 0.0 and 1.0.
2. These scores are combined using configurable weights (e.g., ``w_ts``, ``w_ms``, etc.) found in your ``pyproject.toml`` or ``pypss.toml``.
3. The final weighted average is normalized and scaled to produce the final PSS score from 0 to 100.