.. _features:

###########
Key Features
###########

Core Capabilities
=================

- **Multi-dimensional Scoring**: Combines 5 distinct stability dimensions into one 0-100 score.
- **Timing Stability (TS)**: Penalizes high variance (CV) and long tail latencies (p95/p50).
- **Memory Stability (MS)**: Tracks erratic memory spikes and growth patterns.
- **Error Volatility (EV)**: Distinguishes between consistent failures and chaotic, bursty errors.
- **Branching Entropy (BE)**: Measures the unpredictability of code execution paths.
- **Async-Aware Instrumentation**: Natively handles `async` functions to measure event loop stability.
- **Concurrency Chaos (CC)**: *(Experimental)* Quantifies thread contention and locking overhead.
- **Alerting Engine**: Proactively monitors and notifies on stability changes with configurable rules and channels.
- **Adaptive Sampling**: Intelligent sampling modes (`balanced`, `high_load`, `error_triggered`, `surge`, `low_noise`) to optimize overhead.
- **Metric Auto-Tuning**: Automatically calibrates PSS metric weights and thresholds using Bayesian Optimization for optimal fault detection.
- **ML-based Pattern Detection**: Detects subtle, complex instability patterns using machine learning (e.g., anomaly detection).
- **Plugin System**: Extend PyPSS with custom metrics like `IOStability`, `DatabaseStability`, `KafkaLag`, `GPUSpikes`, etc.

Developer Experience
====================

- **Non-Intrusive Instrumentation**: Lightweight decorators and context managers.
- **Distributed Collection**: Built-in support for Redis, gRPC, and File-based trace collection for microservices.
- **CLI Analysis**: Analyze trace files from production logs or test runs.
- **Type Safe**: Fully typed codebase with `mypy` compliance.
- **Production Ready**: Minimal overhead for sampling stability in critical paths.