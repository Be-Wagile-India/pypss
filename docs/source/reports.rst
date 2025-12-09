.. _reports:

###########
Sample PSS Report
###########

Example 1: An Unstable Program (Low PSS)
========================================

.. code-block:: text

    Python Program Stability Score (PSS) Report
    ===========================================
    PSS: 61/100

    Breakdown:
      - Timing Stability: 0.27
      - Memory Stability: 0.99
      - Error Volatility: 0.59
      - Branching Entropy: 1.00
      - Concurrency Chaos: 0.42

    🧠 AI Stability Diagnosis
    =========================
    ⚠️ System is exhibiting significant flakiness. Reliability is at risk.

    🔍 Observations:
    - Severe latency jitter detected (High variance or heavy tail).
    - High Error Volatility: Failures are bursty and unpredictable.
    - Severe Concurrency Chaos: Thread/Process wait times are highly inconsistent.

Example 2: A Stable Program (High PSS)
======================================

.. code-block:: text

    Python Program Stability Score (PSS) Report
    ===========================================
    PSS: 98/100

    Breakdown:
      - Timing Stability: 0.95
      - Memory Stability: 0.99
      - Error Volatility: 1.00
      - Branching Entropy: 1.00
      - Concurrency Chaos: 0.98

    🧠 AI Stability Diagnosis
    =========================
    ✅ System is stable. No significant issues detected.