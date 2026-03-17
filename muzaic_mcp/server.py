"""
Muzaic AI — MCP Server
=======================
Model Context Protocol server for the Muzaic AI music generation API.
Exposes music generation tools to any MCP-compatible client
(Claude Desktop, Cursor, Windsurf, VS Code, OpenAI Agents, etc.)

API:  https://m10.muzaic.ai/
Docs: https://docs.muzaic.ai/
"""

from __future__ import annotations

import json
import os
import logging
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.getenv("MUZAIC_API_URL", "https://m10.muzaic.ai")
API_KEY = os.getenv("MUZAIC_API_KEY", "")
HTTP_TIMEOUT = int(os.getenv("MUZAIC_HTTP_TIMEOUT", "300"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger("muzaic_mcp")

PARAM_MIN = 1
PARAM_MAX = 9
MAX_DURATION = 1200
MIN_DURATION = 1


# ---------------------------------------------------------------------------
# Lifespan — shared httpx client & tag cache
# ---------------------------------------------------------------------------

@asynccontextmanager
async def app_lifespan(app):
    """Manage the httpx client and pre-fetch tags on startup."""
    if not API_KEY:
        logger.warning("MUZAIC_API_KEY is not set — tools will fail at runtime.")

    headers = {
        "MuzaicAPI-Secret-Key": API_KEY,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers=headers,
        timeout=httpx.Timeout(HTTP_TIMEOUT, connect=10.0),
    ) as client:
        tags_cache: Dict[str, Any] = {}
        try:
            resp = await client.get("/getTags")
            resp.raise_for_status()
            tags_cache = resp.json()
            logger.info("Tags pre-fetched: %d tags loaded", len(tags_cache.get("tags", [])))
        except Exception as exc:
            logger.warning("Failed to pre-fetch tags (server will still work): %s", exc)

        state = {"http_client": client, "tags_cache": tags_cache}
        _lifespan_state.update(state)
        try:
            yield state
        finally:
            _lifespan_state.clear()


# ---------------------------------------------------------------------------
# FastMCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Muzaic",
    instructions=(
        "Muzaic AI music generation server. Generate custom AI music for videos "
        "using tags, parameters (intensity/tempo/rhythm/tone/variance 1-9), and "
        "keyframes for dynamic changes over time (all params except tempo). "
        "Keyframe positions are percentages of track duration (0-100). "
        "1 token = 1 second of audio. "
        "Use muzaic_get_tags to discover available styles before generating."
    ),
    lifespan=app_lifespan,
)


# ---------------------------------------------------------------------------
# Helpers — lifespan state fallback when ctx is not passed (e.g. by some MCP clients)
# ---------------------------------------------------------------------------

_lifespan_state: Dict[str, Any] = {}


def _get_client(ctx) -> httpx.AsyncClient:
    if ctx is not None and hasattr(ctx, "request_context"):
        return ctx.request_context.lifespan_state["http_client"]
    return _lifespan_state["http_client"]


def _get_tags_cache(ctx) -> Dict[str, Any]:
    if ctx is not None and hasattr(ctx, "request_context"):
        return ctx.request_context.lifespan_state["tags_cache"]
    return _lifespan_state.get("tags_cache", {})


def _handle_api_error(e: Exception) -> str:
    """Consistent error formatting across all tools."""
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 401:
            return "Error: Invalid API key. Check your MUZAIC_API_KEY."
        if status == 402:
            return "Error: Insufficient tokens. Top up at https://adminpanel.muzaic.ai/"
        if status == 429:
            return "Error: Rate limit exceeded. Please wait before retrying."
        return f"Error: API returned status {status}. Details: {e.response.text[:200]}"
    if isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. Try a shorter duration."
    return f"Error: {type(e).__name__}: {str(e)[:200]}"


def _validate_params(params: Dict[str, Any]) -> Optional[str]:
    """Validate music parameter values. Returns error string or None."""
    valid_keys = {"intensity", "tempo", "rhythm", "tone", "variance"}
    keyframe_keys = {"intensity", "rhythm", "tone", "variance"}  # tempo is static only
    for key, value in params.items():
        if key not in valid_keys:
            return f"Error: Unknown parameter '{key}'. Valid: {', '.join(valid_keys)}"
        if isinstance(value, (int, float)):
            if not (PARAM_MIN <= value <= PARAM_MAX):
                return f"Error: {key}={value} out of range. Must be {PARAM_MIN}-{PARAM_MAX}."
        elif isinstance(value, list):
            if key not in keyframe_keys:
                return f"Error: '{key}' only accepts a static value (1-9), not keyframes."
            for kf in value:
                if not isinstance(kf, list) or len(kf) != 2:
                    return f"Error: Keyframe for '{key}' must be [position%, value] pairs."
                pos, val = kf
                if not (0 <= pos <= 100):
                    return f"Error: Keyframe position {pos} out of range (0-100%). Position represents percentage of track duration."
                if not (PARAM_MIN <= val <= PARAM_MAX):
                    return f"Error: Keyframe value {val} out of range ({PARAM_MIN}-{PARAM_MAX})."
        else:
            return f"Error: {key} must be int or list of keyframes."
    return None


def _format_generation_result(data: Dict[str, Any]) -> Dict[str, Any]:
    """Standardize the generation response."""
    # Check multiple possible field names for audio URL (API v2.0 uses "mp3" or "wav")
    # Prioritize wav over mp3 for higher quality, then fallback to legacy field names
    audio_url = data.get("wav") or data.get("mp3") or data.get("url") or data.get("audioUrl") or ""
    # Check for hash (soundtrackHash for soundtracks, hash for single files)
    hash_value = data.get("soundtrackHash") or data.get("hash") or ""
    # Check for duration (audioDuration for soundtracks, duration for single files)P
    duration = data.get("audioDuration") or data.get("duration") or 0
    # Tokens used (tokensUsed in API v2.0, or fallback to duration)
    tokens_used = data.get("tokensUsed") or duration
    
    result = {
        "status": "success",
        "audio_url": audio_url,
        "hash": hash_value,
        "duration_seconds": duration,
        "tokens_used": tokens_used,
        "message": "Music generated successfully. Use the audio_url to download/embed.",
    }
    # Include raw API response for debugging if URL is missing
    if not audio_url:
        result["_debug_raw_api_response"] = data
    return result


# ---------------------------------------------------------------------------
# Enums & Input Models
# ---------------------------------------------------------------------------

class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"


class NormalizeMode(str, Enum):
    NONE = "none"
    AUTO = "auto"
    HIGH = "high"


class RegionAction(str, Enum):
    GENERATE = "generate"
    COPY = "copy"
    EXTEND = "extend"


class GetTagsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'",
    )


class GenerateMusicInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    duration: int = Field(..., description="Track duration in seconds (1-1200)", ge=MIN_DURATION, le=MAX_DURATION)
    tags: List[int] = Field(..., description="Tag IDs (use muzaic_get_tags to discover). E.g. [1, 13]", min_length=1)
    intensity: Optional[Union[int, List[List[int]]]] = Field(default=5, description="Energy level 1-9, or keyframes [[position%, value], ...]. Position is % of duration (0-100). E.g. for 30s track, drop at 10s then rise: [[0, 5], [33, 1], [100, 9]]")
    tempo: Optional[int] = Field(default=5, description="Speed 1-9. Static only — does not support keyframes.", ge=PARAM_MIN, le=PARAM_MAX)
    rhythm: Optional[Union[int, List[List[int]]]] = Field(default=5, description="Complexity 1-9, or keyframes [[position%, value], ...]")
    tone: Optional[Union[int, List[List[int]]]] = Field(default=5, description="Emotional color 1-9 (dark→bright), or keyframes [[position%, value], ...]")
    variance: Optional[Union[int, List[List[int]]]] = Field(default=5, description="Variation 1-9, or keyframes [[position%, value], ...]")


class SoundtrackRegion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    time: int = Field(..., description="Start time in seconds", ge=0)
    duration: int = Field(..., description="Region duration in seconds", ge=1)
    tags: Optional[List[int]] = Field(default=None, description="Tag IDs for this region")
    intensity: Optional[Union[int, List[List[int]]]] = Field(default=None, description="Energy level 1-9, or keyframes [[position%, value], ...]")
    tempo: Optional[int] = Field(default=None, description="Speed 1-9. Static only — no keyframes.", ge=PARAM_MIN, le=PARAM_MAX)
    rhythm: Optional[Union[int, List[List[int]]]] = Field(default=None, description="Complexity 1-9, or keyframes")
    tone: Optional[Union[int, List[List[int]]]] = Field(default=None, description="Emotional color 1-9, or keyframes")
    variance: Optional[Union[int, List[List[int]]]] = Field(default=None, description="Variation 1-9, or keyframes")
    source_hash: Optional[str] = Field(default=None, description="Hash from previous generation (for copy/extend)")
    action: RegionAction = Field(default=RegionAction.GENERATE, description="generate, copy, or extend")


class CreateSoundtrackInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    regions: List[SoundtrackRegion] = Field(..., description="Time-based regions composing the soundtrack", min_length=1)
    normalize: NormalizeMode = Field(default=NormalizeMode.AUTO, description="Loudness normalization: none, auto, high")


class RegenerateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hash: str = Field(..., description="Hash from a previous generation result", min_length=10)


class ValidateTagsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tag_ids: List[int] = Field(..., description="Tag IDs to check for compatibility", min_length=2)


class AccountInfoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool(
    name="muzaic_get_tags",
    annotations={
        "title": "List Available Music Tags",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def muzaic_get_tags(params: GetTagsInput, ctx=None) -> str:
    """List all available music tags with IDs, names, descriptions, and compatibility info.

    Call this first to discover tag IDs before generating music. Tags cover
    Style/Genre, Mood/Energy, Purpose, and Cultural categories.
    """
    try:
        cache = _get_tags_cache(ctx)
        if not cache or "tags" not in cache:
            client = _get_client(ctx)
            resp = await client.get("/getTags")
            resp.raise_for_status()
            cache = resp.json()

        tags = cache.get("tags", [])
        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"tags": tags, "total": len(tags)}, indent=2)

        lines = [f"# Available Muzaic Tags ({len(tags)} total)\n"]
        for tag in tags:
            lines.append(f"- **{tag.get('name', '?')}** (ID: {tag.get('id', '?')}): {tag.get('description', '')}")
        lines.append("\n> Use tag IDs when calling muzaic_generate_music or muzaic_create_soundtrack.")
        return "\n".join(lines)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="muzaic_generate_music",
    annotations={
        "title": "Generate Single Music Track",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def muzaic_generate_music(params: GenerateMusicInput, ctx=None) -> str:
    """Generate a single AI music track optimized for video content.

    Creates a stereo 192kbps MP3. Cost: 1 token per second of audio.
    Generation speed: ~5-7 seconds per minute of audio.

    Parameters intensity, rhythm, tone, and variance support keyframes for dynamic changes.
    Tempo is static only (no keyframes). Keyframe format: [[position%, value], ...]
    where position is a percentage of the track duration (0-100).

    Example: For a 30s track where intensity drops at 10s then rises to max at the end:
    intensity=[[0, 5], [33, 1], [100, 9]]  (33% of 30s = 10s)
    """
    music_params: Dict[str, Any] = {}
    for key in ("intensity", "tempo", "rhythm", "tone", "variance"):
        val = getattr(params, key, None)
        if val is not None:
            music_params[key] = val

    err = _validate_params(music_params)
    if err:
        return err

    try:
        client = _get_client(ctx)
        resp = await client.post("/singleFile", json={
            "duration": params.duration,
            "tags": params.tags,
            "params": music_params,
        })
        resp.raise_for_status()
        response_data = resp.json()
        logger.debug("API response data: %s", json.dumps(response_data, indent=2))
        return json.dumps(_format_generation_result(response_data), indent=2)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="muzaic_create_soundtrack",
    annotations={
        "title": "Create Multi-Region Soundtrack",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def muzaic_create_soundtrack(params: CreateSoundtrackInput, ctx=None) -> str:
    """Create an advanced multi-region soundtrack with different styles per section.

    Each region can have its own tags, parameters, and timing. Regions can also
    copy or extend a previous generation using its hash. Cost: 1 token per total second.
    """
    regions_payload = []
    for region in params.regions:
        r: Dict[str, Any] = {"time": region.time, "duration": region.duration}
        if region.tags:
            r["tags"] = region.tags

        music_params: Dict[str, Any] = {}
        for key in ("intensity", "tempo", "rhythm", "tone", "variance"):
            val = getattr(region, key, None)
            if val is not None:
                music_params[key] = val
        if music_params:
            err = _validate_params(music_params)
            if err:
                return err
            r["params"] = music_params

        if region.source_hash:
            r["sourceHash"] = region.source_hash
        if region.action != RegionAction.GENERATE:
            r["action"] = region.action.value

        regions_payload.append(r)

    try:
        client = _get_client(ctx)
        resp = await client.post("/soundtrack", json={
            "normalize": params.normalize.value,
            "regions": regions_payload,
        })
        resp.raise_for_status()
        response_data = resp.json()
        logger.debug("API response data: %s", json.dumps(response_data, indent=2))
        return json.dumps(_format_generation_result(response_data), indent=2)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="muzaic_regenerate",
    annotations={
        "title": "Regenerate Music from Hash",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def muzaic_regenerate(params: RegenerateInput, ctx=None) -> str:
    """Regenerate a previously created music track using its hash.

    Useful for retrieving audio generated earlier. Cost: 1 token per second.
    """
    try:
        client = _get_client(ctx)
        resp = await client.post("/audioFromHash", json={"hash": params.hash})
        resp.raise_for_status()
        return json.dumps(_format_generation_result(resp.json()), indent=2)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="muzaic_validate_tags",
    annotations={
        "title": "Validate Tag Combination",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def muzaic_validate_tags(params: ValidateTagsInput, ctx=None) -> str:
    """Check whether a combination of tags is compatible before generating music.

    Some tag pairs conflict (e.g. Happy + Dark). Returns conflicts if any found.
    """
    try:
        cache = _get_tags_cache(ctx)
        if not cache or "tags" not in cache:
            client = _get_client(ctx)
            resp = await client.get("/getTags")
            resp.raise_for_status()
            cache = resp.json()

        tags = cache.get("tags", [])
        relations = cache.get("tagRelations", [])
        tag_map = {t["id"]: t.get("name", str(t["id"])) for t in tags}

        unknown = [tid for tid in params.tag_ids if tid not in tag_map]
        if unknown:
            return json.dumps({"valid": False, "error": f"Unknown tag IDs: {unknown}. Use muzaic_get_tags."})

        conflicts = []
        for i, id_a in enumerate(params.tag_ids):
            for id_b in params.tag_ids[i + 1:]:
                for rel in relations:
                    if (rel.get("tag1") == id_a and rel.get("tag2") == id_b) or \
                       (rel.get("tag1") == id_b and rel.get("tag2") == id_a):
                        if rel.get("value", 0) == -1:
                            conflicts.append(f"{tag_map[id_a]} ↔ {tag_map[id_b]}")

        if conflicts:
            return json.dumps({"valid": False, "conflicts": conflicts}, indent=2)
        return json.dumps({"valid": True, "tags": [tag_map[tid] for tid in params.tag_ids]}, indent=2)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="muzaic_account_info",
    annotations={
        "title": "Check Account Balance",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def muzaic_account_info(params: AccountInfoInput, ctx=None) -> str:
    """Check account token balance and usage. Free — no tokens consumed."""
    try:
        client = _get_client(ctx)
        resp = await client.get("/accountDetails")
        resp.raise_for_status()
        data = resp.json()

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(data, indent=2)

        balance = data.get("balance", data.get("tokens", "?"))
        used = data.get("used", "?")
        return f"## Muzaic Account\n\n- **Balance**: {balance} tokens\n- **Used**: {used} tokens\n- 1 token = 1 second of audio"
    except Exception as e:
        return _handle_api_error(e)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """CLI entry point for running the Muzaic MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
