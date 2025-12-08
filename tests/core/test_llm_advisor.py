import sys  # Added this import
from unittest.mock import patch, MagicMock
import pytest

from pypss.core.llm_advisor import (
    get_llm_diagnosis,
    TraceSummarizer,
    OpenAIClient,
)


class TestLLMAdvisor:
    def test_trace_summarizer_no_traces(self):
        summary = TraceSummarizer.summarize([])
        assert "No traces collected." in summary

    def test_trace_summarizer_basic_stats(self):
        traces = [
            {
                "duration": 0.1,
                "error": False,
                "cpu_time": 0.05,
                "wait_time": 0.05,
                "memory_diff": 100,
                "filename": "a.py",
                "lineno": 1,
            },
            {
                "duration": 0.2,
                "error": True,
                "cpu_time": 0.1,
                "wait_time": 0.1,
                "memory_diff": 200,
                "filename": "a.py",
                "lineno": 1,
            },
            {
                "duration": 0.15,
                "error": False,
                "cpu_time": 0.07,
                "wait_time": 0.08,
                "memory_diff": 150,
                "filename": "a.py",
                "lineno": 1,
            },
        ]
        summary = TraceSummarizer.summarize(traces, "test_mod")

        assert "Execution Count: 3" in summary
        assert "P50 Latency: 0.1500s" in summary
        assert "P99 Latency: 0.2000s" in summary
        assert "Error Rate: 33.3%" in summary
        assert (
            "Avg Memory Growth: 0.00 MB" in summary
        )  # 100/1MB, 200/1MB, 150/1MB, so average is about 150B which is 0MB
        assert "Source Code (extracted from a.py:1)" in summary

    def test_get_llm_diagnosis_openai(self):
        # Mock openai module in sys.modules to prevent ModuleNotFoundError
        mock_openai_module = MagicMock()
        with patch.dict(sys.modules, {"openai": mock_openai_module}):
            # Patch the OpenAI class inside the mocked module
            mock_openai_cls = mock_openai_module.OpenAI
            mock_openai_instance = MagicMock()
            mock_openai_cls.return_value = mock_openai_instance
            mock_openai_instance.chat.completions.create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content="It's broken."))]
            )

            # Re-import OpenAIClient inside the patched context if necessary,
            # or rely on dynamic import in __init__.
            # Since OpenAIClient imports inside __init__, this patch dict should work.

            # Call the function under test
            diagnosis = get_llm_diagnosis([], provider="openai", api_key="fake")

            assert diagnosis == "It's broken."
            mock_openai_cls.assert_called_with(api_key="fake")
            mock_openai_instance.chat.completions.create.assert_called_once()

    @patch("pypss.core.llm_advisor.OllamaClient")
    def test_get_llm_diagnosis_ollama(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.generate_diagnosis.return_value = "It's slow."

        diagnosis = get_llm_diagnosis([], provider="ollama")

        assert diagnosis == "It's slow."

    def test_get_llm_diagnosis_unknown_provider(self):
        diagnosis = get_llm_diagnosis([], provider="unknown")
        assert diagnosis is not None
        assert "Unknown provider" in diagnosis

    def test_openai_client_import_error(self):
        # Simulate openai module missing by setting it to None in sys.modules
        with patch.dict(sys.modules, {"openai": None}):
            with pytest.raises(ImportError, match="Install 'openai' package"):
                # We need to reload or re-import the module or just instantiate logic that imports it
                # Because the import happens inside __init__, instantiating should trigger it.
                OpenAIClient()

    def test_ollama_client_connection_error(self):
        # Mock requests so OllamaClient can be instantiated without real requests
        with patch.dict(sys.modules, {"requests": MagicMock()}):
            from pypss.core.llm_advisor import OllamaClient

            # Create client (will use mocked requests from sys.modules)
            client = OllamaClient()

            # Now mock the instance's requests object to raise
            client.requests.post.side_effect = Exception("Connection refused")

            diagnosis = client.generate_diagnosis("context")

            assert diagnosis is not None
            assert "Ollama Connection Failed" in diagnosis

    def test_ollama_client_api_error(self):
        with patch.dict(sys.modules, {"requests": MagicMock()}):  # Mock requests
            from pypss.core.llm_advisor import OllamaClient

            client = OllamaClient()

            # Mock successful response object but with error status
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "API Error"
            client.requests.post.return_value = mock_response

            diagnosis = client.generate_diagnosis("context")

            assert diagnosis is not None
            assert "Ollama Error: API Error" in diagnosis

    def test_ollama_client_success(self):
        with patch.dict(sys.modules, {"requests": MagicMock()}):
            from pypss.core.llm_advisor import OllamaClient

            client = OllamaClient()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "response": "Ollama says metrics are bad."
            }
            client.requests.post.return_value = mock_response

            diagnosis = client.generate_diagnosis("metrics...")
            assert diagnosis is not None
            assert "Ollama says metrics are bad" in diagnosis
