from typing import List, Dict, Any, Optional
import numpy as np
import warnings

# Use sklearn for ML models
try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

    class IsolationForest:  # type: ignore
        def __init__(self, *args, **kwargs):
            warnings.warn("Scikit-learn not available. ML features will be limited.")

        def fit(self, X):
            pass

        def decision_function(self, X):
            return np.zeros(len(X))

        def predict(self, X):
            return np.ones(len(X))

    class StandardScaler:  # type: ignore
        def fit_transform(self, X):
            return X


class PatternDetector:
    """
    Detects unusual patterns in application traces using machine learning.
    Currently focuses on anomaly detection.
    """

    def __init__(self, contamination: float = 0.1, random_state: int = 42):
        """
        Initializes the PatternDetector.

        Args:
            contamination (float): The proportion of outliers in the data set.
                                   Used by IsolationForest.
            random_state (int): Random seed for reproducibility.
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError(
                "Scikit-learn is not installed. Cannot use ML-based pattern detection. "
                "Install it via 'pip install scikit-learn'."
            )

        self.model: Optional[IsolationForest] = IsolationForest(
            contamination=contamination,
            random_state=random_state,
            n_jobs=-1,  # Use all available CPU cores
        )
        self.scaler: StandardScaler = StandardScaler()
        self.fitted = False

    def _extract_features(self, traces: List[Dict[str, Any]]) -> np.ndarray:
        """
        Extracts numerical features from a list of raw traces.
        For simplicity, initially focusing on key statistical properties.
        """
        if not traces:
            return np.array([])

        features = []
        for trace in traces:
            duration = float(trace.get("duration", 0.0))
            memory_diff = float(trace.get("memory_diff", 0.0))
            wait_time = float(trace.get("wait_time", 0.0))
            error_flag = 1.0 if trace.get("error", False) else 0.0

            # Simple feature vector for each trace
            features.append([duration, memory_diff, wait_time, error_flag])

        return np.array(features)

    def fit(self, traces: List[Dict[str, Any]]):
        """
        Fits the anomaly detection model to a dataset of 'normal' traces.

        Args:
            traces: A list of trace dictionaries representing normal behavior.
        """
        features = self._extract_features(traces)
        if features.size == 0:
            warnings.warn(
                "No traces provided to fit the PatternDetector model. Model will not be fitted."
            )
            return

        self.scaler.fit(features)
        scaled_features = self.scaler.transform(features)

        if self.model:  # Model might be None if sklearn not available
            self.model.fit(scaled_features)
            self.fitted = True

    def predict_anomalies(self, new_traces: List[Dict[str, Any]]) -> List[bool]:
        """
        Predicts if new traces are anomalous.

        Args:
            new_traces: A list of new trace dictionaries to evaluate.

        Returns:
            A list of booleans, where True indicates an anomaly.
        """
        if not self.fitted or self.model is None:
            warnings.warn(
                "PatternDetector model not fitted. Returning all False for predictions."
            )
            return [False] * len(new_traces)

        features = self._extract_features(new_traces)
        if features.size == 0:
            return [False] * len(new_traces)

        scaled_features = self.scaler.transform(features)

        # IsolationForest predict returns 1 for inliers, -1 for outliers
        predictions = self.model.predict(scaled_features)
        return [p == -1 for p in predictions]

    def anomaly_score(self, new_traces: List[Dict[str, Any]]) -> List[float]:
        """
        Calculates the anomaly score for new traces. Higher scores indicate more anomalous.

        Args:
            new_traces: A list of new trace dictionaries to evaluate.

        Returns:
            A list of anomaly scores.
        """
        if not self.fitted or self.model is None:
            warnings.warn(
                "PatternDetector model not fitted. Returning all 0.0 for anomaly scores."
            )
            return [0.0] * len(new_traces)

        features = self._extract_features(new_traces)
        if features.size == 0:
            return [0.0] * len(new_traces)

        scaled_features = self.scaler.transform(features)

        # IsolationForest decision_function returns negative for outliers, positive for inliers.
        # We want higher scores for more anomalous, so we negate it.
        scores = -self.model.decision_function(scaled_features)
        return scores.tolist()
