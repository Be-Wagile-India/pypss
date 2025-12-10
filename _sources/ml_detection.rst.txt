.. _ml_detection:

ML-based Pattern Detection
==========================

PyPSS introduces Machine Learning based pattern detection to identify subtle and complex anomalies in your application's behavior that might be hard to capture with static rules or thresholds. This feature currently leverages unsupervised anomaly detection techniques.

How it Works
------------

The `pypss ml-detect` command trains an anomaly detection model on a set of "baseline" (healthy) traces. Once trained, it can then analyze new "target" traces and identify those that deviate significantly from the learned normal behavior.

The core steps are:

1.  **Feature Extraction:** Key numerical metrics (like duration, memory changes, wait times, error flags) are extracted from each trace, forming a numerical representation suitable for machine learning.
2.  **Model Training (Fitting):** An unsupervised anomaly detection model (currently `IsolationForest`) is trained on the baseline traces. This process learns the characteristics of "normal" operation.
3.  **Anomaly Prediction:** When new traces are provided, the trained model evaluates how "normal" each trace is. Traces that deviate significantly are flagged as anomalies, and an anomaly score is provided (higher score = more anomalous).

CLI Usage
---------

The `pypss ml-detect` command provides the interface for this feature.

.. code-block:: bash

    pypss ml-detect --help

    Usage: pypss ml-detect [OPTIONS]

      Detects anomalous patterns in target traces using a Machine Learning model
      trained on baseline traces.

    Options:
      --baseline-file PATH      Path to the JSON trace file containing baseline
                                (normal) behavior.  [required]
      --target-file PATH        Path to the JSON trace file containing traces to
                                detect anomalies in.  [required]
      --contamination FLOAT     The proportion of outliers in the baseline dataset.
                                Used by IsolationForest.  [default: 0.1]
      --random-state INTEGER    Random seed for reproducibility of ML model
                                training.  [default: 42]
      --help                    Show this message and exit.

**Example:**

First, generate some baseline traces (e.g., from a healthy test run):

.. code-block:: bash

    # Assuming you have an instrumented app.py running normally
    pypss run app.py --output baseline_traces.json

Then, generate some target traces (e.g., from a potentially problematic run):

.. code-block:: bash

    # Run app.py again, perhaps with some injected faults or under load
    pypss run app.py --output target_traces.json

Finally, use `ml-detect` to find anomalies:

.. code-block:: bash

    pypss ml-detect --baseline-file baseline_traces.json --target-file target_traces.json

The command will output a summary indicating if anomalies were detected in the `target_traces` and their respective anomaly scores.

Configuration
-------------

The `PatternDetector` itself has a few configurable parameters, which can be passed via the CLI:

*   `--contamination`: This is a crucial parameter for IsolationForest. It's the expected proportion of outliers in your training data. A value of 0.1 (10%) means the model expects 10% of the training data to be anomalous. Adjust this based on your understanding of your baseline data.
*   `--random-state`: A seed for the random number generator, useful for reproducibility.

Further Customization (Advanced)
---------------------------------

For more advanced use cases, you can programmatically use the `PatternDetector` class in your own Python code.

.. code-block:: python

    from pypss.ml.detector import PatternDetector
    from pypss.cli.utils import load_traces # Helper to load JSON traces
    import pypss

    pypss.init()

    # 1. Load your baseline and target traces
    baseline_traces = load_traces("baseline_traces.json")
    target_traces = load_traces("target_traces.json")

    # 2. Initialize and fit the detector
    detector = PatternDetector(contamination=0.05, random_state=123)
    detector.fit(baseline_traces)

    # 3. Predict anomalies and get scores for new traces
    is_anomaly = detector.predict_anomalies(target_traces)
    anomaly_scores = detector.anomaly_score(target_traces)

    for i, trace in enumerate(target_traces):
        print(f"Trace: {trace.get('name', f'Trace #{i}')}, Anomaly: {is_anomaly[i]}, Score: {anomaly_scores[i]:.2f}")

This allows for custom feature engineering, integration with different ML models, or more complex anomaly scoring logic.

Installation Note
-----------------

ML-based pattern detection requires the `scikit-learn` library. If you encounter an `ImportError`, ensure it's installed:

.. code-block:: bash

    pip install "pypss[ml]"
    # Or directly:
    # pip install scikit-learn
