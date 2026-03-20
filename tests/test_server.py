"""Comprehensive tests for Muzaic MCP Server."""

import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from muzaic_mcp import __version__
from muzaic_mcp.server import (
    _validate_params,
    _format_generation_result,
    _handle_api_error,
    app_lifespan,
    mcp,
    muzaic_get_tags,
    muzaic_generate_music,
    muzaic_create_soundtrack,
    muzaic_regenerate,
    muzaic_validate_tags,
    muzaic_account_info,
    GetTagsInput,
    GenerateMusicInput,
    CreateSoundtrackInput,
    SoundtrackRegion,
    RegenerateInput,
    ValidateTagsInput,
    AccountInfoInput,
    ResponseFormat,
    NormalizeMode,
    RegionAction,
    _get_client,
    _get_tags_cache,
    _lifespan_state,
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


# ---------------------------------------------------------------------------
# Integration Tests with Mocked HTTP Client
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    """Create a mocked httpx.AsyncClient."""
    client = AsyncMock(spec=httpx.AsyncClient)
    return client


@pytest.fixture
def mock_tags_response():
    """Sample tags API response."""
    return {
        "tags": [
            {"id": 1, "name": "Pop", "description": "Upbeat pop music"},
            {"id": 13, "name": "Cinematic", "description": "Epic cinematic soundtracks"},
        ],
        "tagRelations": [
            {"tag1": 1, "tag2": 2, "value": -1},  # Conflict example
        ],
    }


@pytest.fixture
def mock_generation_response():
    """Sample music generation API response."""
    return {
        "mp3": "https://example.com/audio.mp3",
        "wav": "https://example.com/audio.wav",
        "hash": "abc123def456",
        "duration": 60,
        "tokensUsed": 60,
    }


@pytest.fixture
def mock_account_response():
    """Sample account info API response."""
    return {
        "balance": 1000,
        "tokens": 1000,
        "used": 500,
    }


@pytest.mark.asyncio
async def test_muzaic_get_tags_success(mock_client, mock_tags_response):
    """Test muzaic_get_tags with successful API response."""
    mock_client.get = AsyncMock(return_value=MagicMock(
        raise_for_status=MagicMock(),
        json=MagicMock(return_value=mock_tags_response),
    ))
    
    # Set up lifespan state
    _lifespan_state["http_client"] = mock_client
    _lifespan_state["tags_cache"] = {}
    
    try:
        params = GetTagsInput(response_format=ResponseFormat.JSON)
        result = await muzaic_get_tags(params, ctx=None)
        
        data = json.loads(result)
        assert "tags" in data
        assert len(data["tags"]) == 2
        assert data["tags"][0]["id"] == 1
        assert data["tags"][0]["name"] == "Pop"
    finally:
        _lifespan_state.clear()


@pytest.mark.asyncio
async def test_muzaic_get_tags_markdown(mock_client, mock_tags_response):
    """Test muzaic_get_tags returns markdown format."""
    mock_client.get = AsyncMock(return_value=MagicMock(
        raise_for_status=MagicMock(),
        json=MagicMock(return_value=mock_tags_response),
    ))
    
    _lifespan_state["http_client"] = mock_client
    _lifespan_state["tags_cache"] = {}
    
    try:
        params = GetTagsInput(response_format=ResponseFormat.MARKDOWN)
        result = await muzaic_get_tags(params, ctx=None)
        
        assert "# Available Muzaic Tags" in result
        assert "Pop" in result
        assert "ID: 1" in result
    finally:
        _lifespan_state.clear()


@pytest.mark.asyncio
async def test_muzaic_get_tags_uses_cache(mock_client, mock_tags_response):
    """Test that muzaic_get_tags uses cached tags when available."""
    _lifespan_state["http_client"] = mock_client
    _lifespan_state["tags_cache"] = mock_tags_response
    
    try:
        params = GetTagsInput(response_format=ResponseFormat.JSON)
        result = await muzaic_get_tags(params, ctx=None)
        
        # Should not call API when cache exists
        mock_client.get.assert_not_called()
        
        data = json.loads(result)
        assert len(data["tags"]) == 2
    finally:
        _lifespan_state.clear()


@pytest.mark.asyncio
async def test_muzaic_generate_music_success(mock_client, mock_generation_response):
    """Test muzaic_generate_music with successful API response."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=mock_generation_response)
    mock_client.post = AsyncMock(return_value=mock_response)
    
    _lifespan_state["http_client"] = mock_client
    
    try:
        params = GenerateMusicInput(
            duration=60,
            tags=[1, 13],
            intensity=5,
            tempo=7,
        )
        result = await muzaic_generate_music(params, ctx=None)
        
        # Verify API was called with correct payload
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/singleFile"
        payload = call_args[1]["json"]
        assert payload["duration"] == 60
        assert payload["tags"] == [1, 13]
        assert payload["params"]["intensity"] == 5
        assert payload["params"]["tempo"] == 7
        
        # Verify response parsing
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["audio_url"] == "https://example.com/audio.wav"  # wav preferred
        assert result_data["hash"] == "abc123def456"
        assert result_data["duration_seconds"] == 60
        assert result_data["tokens_used"] == 60
    finally:
        _lifespan_state.clear()


@pytest.mark.asyncio
async def test_muzaic_generate_music_with_keyframes(mock_client, mock_generation_response):
    """Test muzaic_generate_music with keyframe parameters."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=mock_generation_response)
    mock_client.post = AsyncMock(return_value=mock_response)
    
    _lifespan_state["http_client"] = mock_client
    
    try:
        params = GenerateMusicInput(
            duration=30,
            tags=[1],
            intensity=[[0, 5], [50, 1], [100, 9]],  # Keyframes
            rhythm=[[0, 3], [100, 7]],
        )
        result = await muzaic_generate_music(params, ctx=None)
        
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["params"]["intensity"] == [[0, 5], [50, 1], [100, 9]]
        assert payload["params"]["rhythm"] == [[0, 3], [100, 7]]
        
        result_data = json.loads(result)
        assert result_data["status"] == "success"
    finally:
        _lifespan_state.clear()


@pytest.mark.asyncio
async def test_muzaic_create_soundtrack_success(mock_client, mock_generation_response):
    """Test muzaic_create_soundtrack with successful API response."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={
        **mock_generation_response,
        "soundtrackHash": "soundtrack123",
        "audioDuration": 120,
    })
    mock_client.post = AsyncMock(return_value=mock_response)
    
    _lifespan_state["http_client"] = mock_client
    
    try:
        params = CreateSoundtrackInput(
            regions=[
                SoundtrackRegion(
                    time=0,
                    duration=60,
                    tags=[1],
                    intensity=5,
                ),
                SoundtrackRegion(
                    time=60,
                    duration=60,
                    tags=[13],
                    intensity=9,
                ),
            ],
            normalize=NormalizeMode.AUTO,
        )
        result = await muzaic_create_soundtrack(params, ctx=None)
        
        # Verify API call
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/soundtrack"
        payload = call_args[1]["json"]
        assert payload["normalize"] == "auto"
        assert len(payload["regions"]) == 2
        assert payload["regions"][0]["time"] == 0
        assert payload["regions"][0]["duration"] == 60
        assert payload["regions"][0]["tags"] == [1]
        assert payload["regions"][1]["time"] == 60
        
        # Verify response
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["hash"] == "soundtrack123"
        assert result_data["duration_seconds"] == 120
    finally:
        _lifespan_state.clear()


@pytest.mark.asyncio
async def test_muzaic_create_soundtrack_with_copy_extend(mock_client, mock_generation_response):
    """Test soundtrack creation with copy/extend actions."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=mock_generation_response)
    mock_client.post = AsyncMock(return_value=mock_response)
    
    _lifespan_state["http_client"] = mock_client
    
    try:
        params = CreateSoundtrackInput(
            regions=[
                SoundtrackRegion(
                    time=0,
                    duration=30,
                    tags=[1],
                    action=RegionAction.GENERATE,
                ),
                SoundtrackRegion(
                    time=30,
                    duration=30,
                    source_hash="prev_hash123",
                    action=RegionAction.COPY,
                ),
            ],
        )
        result = await muzaic_create_soundtrack(params, ctx=None)
        
        payload = mock_client.post.call_args[1]["json"]
        assert payload["regions"][0].get("action") is None  # GENERATE is default
        assert payload["regions"][1]["action"] == "copy"
        assert payload["regions"][1]["sourceHash"] == "prev_hash123"
        
        result_data = json.loads(result)
        assert result_data["status"] == "success"
    finally:
        _lifespan_state.clear()


@pytest.mark.asyncio
async def test_muzaic_regenerate_success(mock_client, mock_generation_response):
    """Test muzaic_regenerate with successful API response."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=mock_generation_response)
    mock_client.post = AsyncMock(return_value=mock_response)
    
    _lifespan_state["http_client"] = mock_client
    
    try:
        params = RegenerateInput(hash="abc123def456")
        result = await muzaic_regenerate(params, ctx=None)
        
        # Verify API call
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/audioFromHash"
        assert call_args[1]["json"]["hash"] == "abc123def456"
        
        # Verify response
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["hash"] == "abc123def456"
    finally:
        _lifespan_state.clear()


@pytest.mark.asyncio
async def test_muzaic_validate_tags_valid(mock_client, mock_tags_response):
    """Test muzaic_validate_tags with valid tag combination."""
    mock_client.get = AsyncMock(return_value=MagicMock(
        raise_for_status=MagicMock(),
        json=MagicMock(return_value=mock_tags_response),
    ))
    
    _lifespan_state["http_client"] = mock_client
    _lifespan_state["tags_cache"] = mock_tags_response
    
    try:
        params = ValidateTagsInput(tag_ids=[1, 13])
        result = await muzaic_validate_tags(params, ctx=None)
        
        result_data = json.loads(result)
        assert result_data["valid"] is True
        assert "tags" in result_data
    finally:
        _lifespan_state.clear()


@pytest.mark.asyncio
async def test_muzaic_validate_tags_conflict(mock_client, mock_tags_response):
    """Test muzaic_validate_tags detects tag conflicts."""
    mock_tags_with_conflict = {
        **mock_tags_response,
        "tagRelations": [
            {"tag1": 1, "tag2": 13, "value": -1},  # Conflict
        ],
    }
    
    _lifespan_state["http_client"] = mock_client
    _lifespan_state["tags_cache"] = mock_tags_with_conflict
    
    try:
        params = ValidateTagsInput(tag_ids=[1, 13])
        result = await muzaic_validate_tags(params, ctx=None)
        
        result_data = json.loads(result)
        assert result_data["valid"] is False
        assert "conflicts" in result_data
        assert len(result_data["conflicts"]) > 0
    finally:
        _lifespan_state.clear()


@pytest.mark.asyncio
async def test_muzaic_validate_tags_unknown(mock_client, mock_tags_response):
    """Test muzaic_validate_tags handles unknown tag IDs."""
    _lifespan_state["http_client"] = mock_client
    _lifespan_state["tags_cache"] = mock_tags_response
    
    try:
        params = ValidateTagsInput(tag_ids=[1, 999])  # 999 doesn't exist
        result = await muzaic_validate_tags(params, ctx=None)
        
        result_data = json.loads(result)
        assert result_data["valid"] is False
        assert "error" in result_data
        assert "999" in result_data["error"]
    finally:
        _lifespan_state.clear()


@pytest.mark.asyncio
async def test_muzaic_account_info_success(mock_client, mock_account_response):
    """Test muzaic_account_info with successful API response."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=mock_account_response)
    mock_client.get = AsyncMock(return_value=mock_response)
    
    _lifespan_state["http_client"] = mock_client
    
    try:
        params = AccountInfoInput(response_format=ResponseFormat.JSON)
        result = await muzaic_account_info(params, ctx=None)
        
        # Verify API call
        mock_client.get.assert_called_once_with("/accountDetails")
        
        # Verify response
        result_data = json.loads(result)
        assert result_data["balance"] == 1000
        assert result_data["tokens"] == 1000
        assert result_data["used"] == 500
    finally:
        _lifespan_state.clear()


@pytest.mark.asyncio
async def test_muzaic_account_info_markdown(mock_client, mock_account_response):
    """Test muzaic_account_info returns markdown format."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=mock_account_response)
    mock_client.get = AsyncMock(return_value=mock_response)
    
    _lifespan_state["http_client"] = mock_client
    
    try:
        params = AccountInfoInput(response_format=ResponseFormat.MARKDOWN)
        result = await muzaic_account_info(params, ctx=None)
        
        assert "## Muzaic Account" in result
        assert "1000" in result
        assert "tokens" in result
    finally:
        _lifespan_state.clear()


@pytest.mark.asyncio
async def test_api_error_handling_401(mock_client):
    """Test that API 401 errors are handled correctly."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    error = httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=mock_response)
    mock_client.post = AsyncMock(side_effect=error)
    
    _lifespan_state["http_client"] = mock_client
    
    try:
        params = GenerateMusicInput(duration=60, tags=[1])
        result = await muzaic_generate_music(params, ctx=None)
        
        assert "Invalid API key" in result or "401" in result
    finally:
        _lifespan_state.clear()


@pytest.mark.asyncio
async def test_api_error_handling_402(mock_client):
    """Test that API 402 errors are handled correctly."""
    mock_response = MagicMock()
    mock_response.status_code = 402
    mock_response.text = "Payment Required"
    error = httpx.HTTPStatusError("Payment Required", request=MagicMock(), response=mock_response)
    mock_client.post = AsyncMock(side_effect=error)
    
    _lifespan_state["http_client"] = mock_client
    
    try:
        params = GenerateMusicInput(duration=60, tags=[1])
        result = await muzaic_generate_music(params, ctx=None)
        
        assert "Insufficient tokens" in result or "402" in result
    finally:
        _lifespan_state.clear()


@pytest.mark.asyncio
async def test_api_error_handling_timeout(mock_client):
    """Test that timeout errors are handled correctly."""
    error = httpx.TimeoutException("Request timed out")
    mock_client.post = AsyncMock(side_effect=error)
    
    _lifespan_state["http_client"] = mock_client
    
    try:
        params = GenerateMusicInput(duration=60, tags=[1])
        result = await muzaic_generate_music(params, ctx=None)
        
        assert "timed out" in result.lower() or "timeout" in result.lower()
    finally:
        _lifespan_state.clear()


# ---------------------------------------------------------------------------
# Error Handling Tests
# ---------------------------------------------------------------------------

def test_get_client_missing_lifespan():
    """Test _get_client raises clear error when lifespan state is missing."""
    _lifespan_state.clear()
    
    with pytest.raises(RuntimeError) as exc_info:
        _get_client(None)
    
    # Should raise RuntimeError with helpful message
    error_msg = str(exc_info.value)
    assert "not properly initialized" in error_msg or "HTTP client" in error_msg
    assert "MUZAIC_API_KEY" in error_msg or "lifespan" in error_msg.lower()


def test_get_tags_cache_missing_lifespan():
    """Test _get_tags_cache returns empty dict when cache is missing."""
    _lifespan_state.clear()
    
    result = _get_tags_cache(None)
    assert result == {}
