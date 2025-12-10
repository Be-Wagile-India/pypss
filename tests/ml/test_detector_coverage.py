import importlib
import sys

import pytest

from pypss.ml import detector


class TestDetectorCoverage:
    @pytest.mark.filterwarnings("ignore:Scikit-learn not available.*:UserWarning")
    def test_sklearn_missing_import(self, monkeypatch):
        # Mock sklearn missing
        monkeypatch.setitem(sys.modules, "sklearn.ensemble", None)
        monkeypatch.setitem(sys.modules, "sklearn.preprocessing", None)

        # Reload detector module
        importlib.reload(detector)

        assert detector.SKLEARN_AVAILABLE is False

        # Verify fallback classes
        clf = detector.IsolationForest()
        clf.fit([])
        assert clf.decision_function([1])[0] == 0.0
        assert clf.predict([1])[0] == 1.0

        scaler = detector.StandardScaler()
        assert scaler.fit_transform([1]) == [1]

        # Verify __init__ raises ImportError
        with pytest.raises(ImportError):
            detector.PatternDetector()

    def test_extract_features_empty_returns_array(self):
        # Ensure SKLEARN is available for this test (reload if needed)
        if not detector.SKLEARN_AVAILABLE:
            importlib.reload(detector)

        det = detector.PatternDetector()
        features = det._extract_features([])
        assert features.size == 0
        assert features.shape == (0,)
