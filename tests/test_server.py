"""Comprehensive tests for Muzaic MCP Server."""

import pytest
from muzaic_mcp import __version__
from muzaic_mcp.server import (
    _validate_params,
    _format_generation_result,
    _handle_api_error,
    app_lifespan,
    mcp,
)
import httpx


def test_version():
    """Test that version is defined and correct."""
    assert __version__ == "1.0.0"
    assert isinstance(__version__, str)


def test_validate_params_valid():
    """Test parameter validation with valid inputs."""
    assert _validate_params({"intensity": 5, "tempo": 3}) is None
    assert _validate_params({"intensity": 1, "tempo": 9}) is None
    assert _validate_params({"rhythm": 5}) is None


def test_validate_params_out_of_range():
    """Test parameter validation rejects out-of-range values."""
    result = _validate_params({"intensity": 10})
    assert result is not None
    assert "out of range" in result
    
    result = _validate_params({"tempo": 0})
    assert result is not None
    assert "out of range" in result


def test_validate_params_invalid_key():
    """Test parameter validation rejects unknown parameters."""
    result = _validate_params({"volume": 5})
    assert result is not None
    assert "Unknown parameter" in result


def test_validate_params_keyframes():
    """Test parameter validation with valid keyframes."""
    assert _validate_params({"intensity": [[0, 2], [50, 5], [100, 9]]}) is None
    assert _validate_params({"rhythm": [[0, 1], [100, 9]]}) is None
    assert _validate_params({"tone": [[0, 5]]}) is None


def test_validate_params_keyframes_bad_position():
    """Test parameter validation rejects invalid keyframe positions."""
    result = _validate_params({"intensity": [[150, 5]]})
    assert result is not None
    assert "position" in result.lower()
    
    result = _validate_params({"intensity": [[-10, 5]]})
    assert result is not None
    assert "position" in result.lower()


def test_validate_params_keyframes_bad_value():
    """Test parameter validation rejects invalid keyframe values."""
    result = _validate_params({"intensity": [[0, 10]]})
    assert result is not None
    assert "value" in result.lower() or "range" in result.lower()


def test_validate_params_keyframes_bad_format():
    """Test parameter validation rejects malformed keyframes."""
    result = _validate_params({"intensity": [[0, 5, 10]]})  # 3 elements
    assert result is not None
    assert "pairs" in result.lower() or "position" in result.lower()
    
    result = _validate_params({"intensity": [5]})  # Not a list of lists
    assert result is not None


def test_validate_params_tempo_rejects_keyframes():
    """Test that tempo parameter rejects keyframes (static only)."""
    result = _validate_params({"tempo": [[0, 3], [100, 7]]})
    assert result is not None
    assert "static" in result.lower() or "keyframes" in result.lower()


def test_format_generation_result():
    """Test generation result formatting."""
    data = {"url": "https://example.com/audio.mp3", "hash": "abc123", "duration": 60}
    result = _format_generation_result(data)
    assert result["status"] == "success"
    assert result["audio_url"] == "https://example.com/audio.mp3"
    assert result["hash"] == "abc123"
    assert result["duration_seconds"] == 60
    assert result["tokens_used"] == 60
    assert "message" in result


def test_format_generation_result_alternative_keys():
    """Test generation result formatting with alternative key names."""
    data = {"audioUrl": "https://example.com/audio.mp3", "hash": "xyz789", "duration": 30}
    result = _format_generation_result(data)
    assert result["audio_url"] == "https://example.com/audio.mp3"
    assert result["hash"] == "xyz789"


def test_handle_api_error_401():
    """Test error handling for 401 Unauthorized."""
    response = httpx.Response(401, text="Unauthorized")
    error = httpx.HTTPStatusError("Unauthorized", request=httpx.Request("GET", "/"), response=response)
    result = _handle_api_error(error)
    assert "Invalid API key" in result or "401" in result


def test_handle_api_error_402():
    """Test error handling for 402 Payment Required."""
    response = httpx.Response(402, text="Insufficient tokens")
    error = httpx.HTTPStatusError("Payment Required", request=httpx.Request("GET", "/"), response=response)
    result = _handle_api_error(error)
    assert "Insufficient tokens" in result or "402" in result


def test_handle_api_error_429():
    """Test error handling for 429 Rate Limit."""
    response = httpx.Response(429, text="Too Many Requests")
    error = httpx.HTTPStatusError("Rate Limit", request=httpx.Request("GET", "/"), response=response)
    result = _handle_api_error(error)
    assert "Rate limit" in result or "429" in result


def test_handle_api_error_timeout():
    """Test error handling for timeout."""
    error = httpx.TimeoutException("Request timed out")
    result = _handle_api_error(error)
    assert "timed out" in result.lower() or "timeout" in result.lower()


def test_handle_api_error_generic():
    """Test error handling for generic exceptions."""
    error = ValueError("Something went wrong")
    result = _handle_api_error(error)
    assert "Error" in result
    assert "ValueError" in result or "Something went wrong" in result


def test_mcp_server_initialized():
    """Test that MCP server is properly initialized."""
    assert mcp is not None
    assert hasattr(mcp, "run")


def test_app_lifespan_signature():
    """Test that app_lifespan accepts the app parameter."""
    import inspect
    sig = inspect.signature(app_lifespan)
    params = list(sig.parameters.keys())
    assert "app" in params, "app_lifespan must accept 'app' parameter for FastMCP compatibility"
