import math

from pypss.utils import (
    calculate_cv,
    calculate_entropy,
    exponential_decay_score,
    normalize_score,
)


class TestUtils:
    def test_calculate_cv_empty(self):
        assert calculate_cv([]) == 0.0

    def test_calculate_cv_zeros(self):
        # Mean is 0, should avoid division by zero
        assert calculate_cv([0, 0, 0]) == 0.0

    def test_calculate_cv_constant(self):
        # CV of constant non-zero values is 0
        assert calculate_cv([10, 10, 10]) == 0.0

    def test_calculate_cv_basic(self):
        # Data: [10, 20]
        # Mean: 15
        # Variance: ((10-15)^2 + (20-15)^2) / 2 = (25 + 25) / 2 = 25
        # StdDev: 5
        # CV: sqrt(50) / 15 = 0.4714...
        cv = calculate_cv([10, 20])
        assert math.isclose(cv, math.sqrt(50) / 15, rel_tol=1e-5)

    def test_calculate_entropy_empty(self):
        assert calculate_entropy([]) == 0.0

    def test_calculate_entropy_zero_entropy(self):
        # All same tags -> 0 entropy
        assert calculate_entropy(["A", "A", "A"]) == 0.0

    def test_calculate_entropy_high(self):
        # Two values, 50/50 probability. Entropy should be 1.0 (bits)
        # -0.5 * log2(0.5) - 0.5 * log2(0.5) = -0.5 * -1 - 0.5 * -1 = 0.5 + 0.5 = 1.0
        assert math.isclose(calculate_entropy(["A", "B"]), 1.0)

    def test_normalize_score(self):
        assert normalize_score(1.5) == 1.0
        assert normalize_score(-0.5) == 0.0
        assert normalize_score(0.5) == 0.5

    def test_exponential_decay(self):
        # exp(-alpha * 0) should be 1.0
        assert exponential_decay_score(0, alpha=1.0) == 1.0
        # exp(-1 * 1) = 1/e ~= 0.367
        assert math.isclose(exponential_decay_score(1, alpha=1.0), 0.367879, rel_tol=1e-4)

    def test_parse_time_string_valid_formats(self):
        from pypss.utils.utils import parse_time_string

        assert parse_time_string("5s") == 5
        assert parse_time_string("2m") == 120
        assert parse_time_string("1.5h") == 5400
        assert parse_time_string("1d") == 86400
        assert parse_time_string("1w") == 604800
        assert parse_time_string("0s") == 0
        assert parse_time_string("1.0s") == 1.0

    def test_parse_time_string_case_insensitivity(self):
        from pypss.utils.utils import parse_time_string

        assert parse_time_string("10S") == 10
        assert parse_time_string("3M") == 180
        assert parse_time_string("0.5H") == 1800

    def test_parse_time_string_none_input(self):
        from pypss.utils.utils import parse_time_string

        assert parse_time_string(None) is None
        assert parse_time_string("None") is None
        assert parse_time_string("none ") is None

    def test_parse_time_string_invalid_formats(self):
        import pytest

        from pypss.utils.utils import parse_time_string

        with pytest.raises(ValueError, match="Invalid time string format"):
            parse_time_string("5x")
        with pytest.raises(ValueError, match="Invalid time string format"):
            parse_time_string("abc")
        with pytest.raises(ValueError, match="Invalid time string format"):
            parse_time_string("1.2")
        with pytest.raises(ValueError, match="Invalid time string format"):
            parse_time_string("1y")
