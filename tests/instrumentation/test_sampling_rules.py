import pytest

from pypss.instrumentation.instrumentation import _get_effective_sample_rate
from pypss.utils.config import GLOBAL_CONFIG, SamplingStrategy


@pytest.fixture(autouse=True)
def setup_teardown_global_config():
    """Fixture to reset GLOBAL_CONFIG before and after each test."""

    # Store original values
    original_sample_rate = GLOBAL_CONFIG.sample_rate
    original_error_sample_rate = GLOBAL_CONFIG.error_sample_rate
    original_context_sampling_rules = list(GLOBAL_CONFIG.context_sampling_rules)  # Deep copy

    # Ensure defaults for testing
    GLOBAL_CONFIG.sample_rate = 1.0
    GLOBAL_CONFIG.error_sample_rate = 1.0
    GLOBAL_CONFIG.context_sampling_rules = []

    yield  # Run the test

    # Restore original values
    GLOBAL_CONFIG.sample_rate = original_sample_rate
    GLOBAL_CONFIG.error_sample_rate = original_error_sample_rate
    GLOBAL_CONFIG.context_sampling_rules = original_context_sampling_rules


class TestGetEffectiveSampleRate:
    def test_error_traces_always_get_error_sample_rate(self):
        GLOBAL_CONFIG.error_sample_rate = 0.5
        GLOBAL_CONFIG.sample_rate = 0.1  # Should be ignored

        rate = _get_effective_sample_rate(is_error=True, trace_name="test", trace_module="test_mod")
        assert rate == 0.5

    def test_context_rule_always_strategy(self):
        GLOBAL_CONFIG.context_sampling_rules = [
            {"pattern": ".*always_trace.*", "strategy": SamplingStrategy.ALWAYS.value}
        ]
        GLOBAL_CONFIG.sample_rate = 0.0  # Should be ignored

        rate = _get_effective_sample_rate(is_error=False, trace_name="my_always_trace", trace_module="mod")
        assert rate == 1.0

    def test_context_rule_never_strategy(self):
        GLOBAL_CONFIG.context_sampling_rules = [
            {"pattern": ".*never_trace.*", "strategy": SamplingStrategy.NEVER.value}
        ]
        GLOBAL_CONFIG.sample_rate = 1.0  # Should be ignored

        rate = _get_effective_sample_rate(is_error=False, trace_name="my_never_trace", trace_module="mod")
        assert rate == 0.0

    def test_context_rule_on_error_strategy_with_error(self):
        GLOBAL_CONFIG.context_sampling_rules = [
            {
                "pattern": ".*on_error_trace.*",
                "strategy": SamplingStrategy.ON_ERROR.value,
            }
        ]
        GLOBAL_CONFIG.sample_rate = 0.0  # Should be ignored

        rate = _get_effective_sample_rate(is_error=True, trace_name="my_on_error_trace", trace_module="mod")
        assert rate == 1.0

    def test_context_rule_on_error_strategy_no_error(self):
        GLOBAL_CONFIG.context_sampling_rules = [
            {
                "pattern": ".*on_error_trace.*",
                "strategy": SamplingStrategy.ON_ERROR.value,
            }
        ]
        GLOBAL_CONFIG.sample_rate = 1.0  # Should be ignored

        rate = _get_effective_sample_rate(is_error=False, trace_name="my_on_error_trace", trace_module="mod")
        assert rate == 0.0

    def test_context_rule_random_strategy_with_rule_sample_rate(self):
        GLOBAL_CONFIG.context_sampling_rules = [
            {
                "pattern": ".*random_trace.*",
                "strategy": SamplingStrategy.RANDOM.value,
                "sample_rate": 0.75,
            }
        ]
        GLOBAL_CONFIG.sample_rate = 0.1  # Should be ignored

        rate = _get_effective_sample_rate(is_error=False, trace_name="my_random_trace", trace_module="mod")
        assert rate == 0.75

    def test_context_rule_random_strategy_no_rule_sample_rate_fallback_to_global(self):
        GLOBAL_CONFIG.context_sampling_rules = [
            {
                "pattern": ".*random_trace.*",
                "strategy": SamplingStrategy.RANDOM.value,
            }  # No sample_rate here
        ]
        GLOBAL_CONFIG.sample_rate = 0.6
        GLOBAL_CONFIG.error_sample_rate = 0.9  # Should be ignored for non-error

        rate = _get_effective_sample_rate(is_error=False, trace_name="my_random_trace", trace_module="mod")
        assert rate == 0.6

    def test_no_matching_context_rules_fallback_to_global_sample_rate(self):
        GLOBAL_CONFIG.context_sampling_rules = [{"pattern": "unmatched", "strategy": SamplingStrategy.ALWAYS.value}]
        GLOBAL_CONFIG.sample_rate = 0.3
        GLOBAL_CONFIG.error_sample_rate = 0.9  # Should be ignored for non-error

        rate = _get_effective_sample_rate(is_error=False, trace_name="some_trace", trace_module="some_mod")
        assert rate == 0.3

    def test_multiple_context_rules_precedence(self):
        # First matching rule should take precedence
        GLOBAL_CONFIG.context_sampling_rules = [
            {"pattern": ".*specific.*", "strategy": SamplingStrategy.NEVER.value},
            {"pattern": ".*general.*", "strategy": SamplingStrategy.ALWAYS.value},
        ]

        rate = _get_effective_sample_rate(is_error=False, trace_name="specific_general_trace", trace_module="mod")
        assert rate == 0.0  # NEVER rule should hit first

    def test_pattern_matching_trace_module(self):
        GLOBAL_CONFIG.context_sampling_rules = [
            {"pattern": ".*module_match.*", "strategy": SamplingStrategy.ALWAYS.value}
        ]
        rate = _get_effective_sample_rate(is_error=False, trace_name="some_trace", trace_module="my_module_match")
        assert rate == 1.0

    def test_pattern_no_match(self):
        GLOBAL_CONFIG.context_sampling_rules = [{"pattern": "nomatch", "strategy": SamplingStrategy.ALWAYS.value}]
        GLOBAL_CONFIG.sample_rate = 0.5
        rate = _get_effective_sample_rate(is_error=False, trace_name="some_trace", trace_module="some_mod")
        assert rate == 0.5
