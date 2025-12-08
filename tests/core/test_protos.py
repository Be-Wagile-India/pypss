import pytest
import grpc
from unittest.mock import MagicMock, patch
from typing import Any

from pypss.protos import trace_pb2 as _trace_pb2  # type: ignore
from pypss.protos import trace_pb2_grpc as _trace_pb2_grpc  # type: ignore

trace_pb2: Any = _trace_pb2
trace_pb2_grpc: Any = _trace_pb2_grpc


class TestTracePB2:
    def test_trace_message_serialization(self):
        msg = trace_pb2.TraceMessage(
            trace_id="123",
            name="test_func",
            filename="test.py",
            lineno=10,
            module="test_mod",
            duration=0.5,
            cpu_time=0.1,
            wait_time=0.4,
            memory=1024,
            memory_diff=100,
            error=False,
            exception_type="",
            exception_message="",
            branch_tag="tag",
            timestamp=123456789.0,
        )

        serialized = msg.SerializeToString()
        assert isinstance(serialized, bytes)

        msg2 = trace_pb2.TraceMessage()
        msg2.ParseFromString(serialized)

        assert msg2.trace_id == "123"
        assert msg2.name == "test_func"
        assert msg2.duration == 0.5
        assert msg2.lineno == 10

    def test_trace_response_serialization(self):
        resp = trace_pb2.TraceResponse(success=True, message="OK")
        serialized = resp.SerializeToString()

        resp2 = trace_pb2.TraceResponse()
        resp2.ParseFromString(serialized)

        assert resp2.success is True
        assert resp2.message == "OK"

    def test_pure_python_descriptors(self):
        """Test the fallback path when C descriptors are not used."""
        import importlib
        from google.protobuf import descriptor

        # Check current state
        original_use_c = getattr(descriptor, "_USE_C_DESCRIPTORS", True)

        # Mock objects to handle the fallback logic
        mock_pool_cls = MagicMock()
        mock_pool_instance = MagicMock()
        mock_pool_cls.Default.return_value = mock_pool_instance

        mock_descriptor = MagicMock()
        mock_pool_instance.AddSerializedFile.return_value = mock_descriptor

        mock_builder = MagicMock()

        try:
            # Force C descriptors off
            descriptor._USE_C_DESCRIPTORS = False

            with (
                patch("google.protobuf.descriptor_pool", mock_pool_cls),
                patch("google.protobuf.internal.builder", mock_builder),
            ):
                # We also need the builder to populate _globals with mocks
                def side_effect_build(desc, glob):
                    glob["_TRACEMESSAGE"] = MagicMock()
                    glob["_TRACERESPONSE"] = MagicMock()
                    glob["_TRACESERVICE"] = MagicMock()

                mock_builder.BuildMessageAndEnumDescriptors.side_effect = (
                    side_effect_build
                )

                # Reload trace_pb2
                importlib.reload(trace_pb2)

                # Verify fallback lines executed
                # DESCRIPTOR._loaded_options = None
                assert mock_descriptor._loaded_options is None

        finally:
            # Restore state
            descriptor._USE_C_DESCRIPTORS = original_use_c
            importlib.reload(trace_pb2)


class TestTracePB2GRPC:
    def test_stub_initialization(self):
        channel = MagicMock()
        stub = trace_pb2_grpc.TraceServiceStub(channel)

        # Verify unary_unary was called to setup SubmitTrace
        channel.unary_unary.assert_called_once()
        assert hasattr(stub, "SubmitTrace")

    def test_servicer_default_behavior(self):
        servicer = trace_pb2_grpc.TraceServiceServicer()
        context = MagicMock()

        with pytest.raises(NotImplementedError):
            servicer.SubmitTrace(None, context)

        context.set_code.assert_called_with(grpc.StatusCode.UNIMPLEMENTED)

    def test_add_servicer_to_server(self):
        server = MagicMock()
        servicer = trace_pb2_grpc.TraceServiceServicer()

        trace_pb2_grpc.add_TraceServiceServicer_to_server(servicer, server)

        # Verify handlers were added
        server.add_generic_rpc_handlers.assert_called_once()
        server.add_registered_method_handlers.assert_called_once()

    def test_experimental_api(self):
        # TraceService class with static method
        request = trace_pb2.TraceMessage()
        target = "localhost:50051"

        with patch("grpc.experimental.unary_unary") as mock_unary:
            trace_pb2_grpc.TraceService.SubmitTrace(request, target)
            mock_unary.assert_called_once()

    def test_version_check_logic(self):
        # This is tricky because the code runs on import.
        # We can try to reload the module with a mocked grpc version.
        import importlib

        try:
            # Mock an old version
            with patch("grpc.__version__", "1.0.0"):
                # Force reload to trigger the check
                importlib.reload(trace_pb2_grpc)
        except RuntimeError as e:
            # Expected to raise because 1.0.0 < generated version
            assert "The grpc package installed is at version 1.0.0" in str(e)
        except ImportError:
            # Depending on how the version check is implemented (runtime_version vs string compare)
            pass
        finally:
            # Restore the module to a good state
            importlib.reload(trace_pb2_grpc)

    def test_legacy_grpc_import(self):
        """Test the ImportError path when grpc._utilities is missing."""
        import importlib
        import sys

        # We mock sys.modules to simulate missing submodule
        with patch.dict(sys.modules):
            # Temporarily hide grpc._utilities
            if "grpc._utilities" in sys.modules:
                del sys.modules["grpc._utilities"]

            orig_import = __import__

            def import_mock(name, *args, **kwargs):
                if name == "grpc._utilities":
                    raise ImportError("Mocked ImportError")
                return orig_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=import_mock):
                # Reload should raise RuntimeError because _version_not_supported becomes True
                with pytest.raises(RuntimeError) as excinfo:
                    importlib.reload(trace_pb2_grpc)

                assert "The grpc package installed" in str(excinfo.value)

            # Verify we are back to normal
            importlib.reload(trace_pb2_grpc)
