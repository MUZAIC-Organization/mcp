# 🎵 Muzaic MCP Server

[![PyPI version](https://img.shields.io/pypi/v/muzaic-mcp.svg)](https://pypi.org/project/muzaic-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-brightgreen)](https://modelcontextprotocol.io/)

> **Official [MCP](https://modelcontextprotocol.io/) server for [Muzaic AI](https://muzaic.ai) — generate custom music for video content**

<!-- mcp-name: io.github.muzaic-ai/muzaic-mcp -->

---

## ✨ What is this?

**Muzaic MCP Server** connects the Muzaic AI music generation API to any LLM or agent that speaks the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). Generate AI-powered soundtracks for videos — directly from Claude, Cursor, VS Code, or any MCP client.

- 🎶 Generate single tracks or multi-region soundtracks
- 🏷️ Browse 30+ music tags (style, mood, genre, cultural)
- 🎛️ Fine-tune with 5 parameters: intensity, tempo, rhythm, tone, variance
- 📈 Dynamic keyframes for parameter changes over time
- ✅ Tag compatibility validation
- 💰 Check account balance and token usage

> ⚠️ **Note:** Muzaic tokens are needed to generate music. Get your API key from [adminpanel.muzaic.ai](https://adminpanel.muzaic.ai/).

---

## 📦 Quick Install

```bash
pip install muzaic-mcp
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv pip install muzaic-mcp
```

---

## 🏃 Quick Start

```bash
export MUZAIC_API_KEY=your_api_key_here
muzaic-mcp
```

---

## 🔧 Configuration

### Claude Desktop

Go to **Claude → Settings → Developer → Edit Config** and add:

```json
{
  "mcpServers": {
    "Muzaic": {
      "command": "uvx",
      "args": ["muzaic-mcp"],
      "env": {
        "MUZAIC_API_KEY": "<your-api-key>"
      }
    }
  }
}
```

### Cursor

**Windows:** Add to `%USERPROFILE%\.cursor\mcp.json` (e.g., `C:\Users\YourName\.cursor\mcp.json`)

**macOS/Linux:** Add to `~/.cursor/mcp.json`

```json
{
  "mcpServers": {
    "Muzaic": {
      "command": "uvx",
      "args": ["muzaic-mcp"],
      "env": {
        "MUZAIC_API_KEY": "<your-api-key>"
      }
    }
  }
}
```

**Note:** If `uvx` is not in your PATH, use the full path. On Windows with Python installed, you can find it with:
```powershell
where.exe uvx
# Or if using uv:
where.exe uv
# Then use: "C:\\path\\to\\uv.exe" with args: ["tool", "run", "muzaic-mcp"]
```

Alternatively, if you have Python installed, you can use:
```json
{
  "mcpServers": {
    "Muzaic": {
      "command": "python",
      "args": ["-m", "muzaic_mcp.server"],
      "env": {
        "MUZAIC_API_KEY": "<your-api-key>"
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add-json "Muzaic" '{"command":"uvx","args":["muzaic-mcp"],"env":{"MUZAIC_API_KEY":"<your-api-key>"}}'
```

### VS Code

Create `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "Muzaic": {
      "command": "uvx",
      "args": ["muzaic-mcp"],
      "env": {
        "MUZAIC_API_KEY": "<your-api-key>"
      }
    }
  }
}
```

---

## 🛠️ Available Tools

| Tool | Description | Cost |
|------|-------------|------|
| `muzaic_get_tags` | List all available music tags with descriptions | Free |
| `muzaic_validate_tags` | Check tag combination compatibility | Free |
| `muzaic_account_info` | Check token balance and usage | Free |
| `muzaic_generate_music` | Generate a single AI music track | 1 token/sec |
| `muzaic_create_soundtrack` | Create multi-region soundtrack with different styles | 1 token/sec |
| `muzaic_regenerate` | Regenerate music from a previous hash | 1 token/sec |

---

## 💬 Example Prompts

Try these with Claude, Cursor, or any MCP client:

- `"What music styles can you generate with Muzaic?"`
- `"Create a 60-second upbeat pop track for a product video"`
- `"Generate a cinematic soundtrack that starts calm and builds to epic over 2 minutes"`
- `"Make a 30-second chill ambient track for a meditation app intro"`
- `"Create a soundtrack with 3 sections: calm intro, energetic middle, peaceful outro"`

---

## 🎛️ Music Parameters

All parameters range from **1** (low) to **9** (high):

| Parameter | 1 | 9 |
|-----------|---|---|
| **intensity** | Calm, ambient | High energy, powerful |
| **tempo** | Very slow | Very fast |
| **rhythm** | Simple, steady | Complex patterns |
| **tone** | Dark, moody | Bright, cheerful |
| **variance** | Repetitive | Diverse, changing |

### Dynamic Keyframes

All parameters **except tempo** support keyframes — values that change over the duration of the track. Positions are expressed as percentages (0–100%) of the track duration.

```
# 30-second track: intensity drops at 10s, then rises to max at the end
intensity: [[0, 5], [33, 1], [100, 9]]
          ↑ start at 5  ↑ drop to 1 at 33% (=10s)  ↑ rise to 9 at 100% (=30s)
```

**Tempo** only accepts a static value (1–9) — keyframes are not supported for tempo.

---

## 🐛 Troubleshooting

### API key not set

```
Error: MUZAIC_API_KEY is not set
```

Make sure the `MUZAIC_API_KEY` environment variable is configured in your MCP client settings.

### `uvx` not found

**Windows:**
```powershell
# Find uvx location
where.exe uvx

# If not found, install uv first:
# pip install uv
# Or download from: https://github.com/astral-sh/uv/releases

# Then use full path in mcp.json:
# "command": "C:\\Users\\YourName\\AppData\\Local\\Programs\\uv\\uv.exe"
# "args": ["tool", "run", "muzaic-mcp"]
```

**macOS/Linux:**
```bash
# Find uvx location
which uvx

# If not found, install uv:
# curl -LsSf https://astral.sh/uv/install.sh | sh

# Then use full path in config:
# "command": "/usr/local/bin/uvx"
```

**Alternative:** Use Python directly if `uvx` is unavailable:
```json
{
  "mcpServers": {
    "Muzaic": {
      "command": "python",
      "args": ["-m", "muzaic_mcp.server"],
      "env": {
        "MUZAIC_API_KEY": "<your-api-key>"
      }
    }
  }
}
```

### Timeout on long tracks

Music generation can take up to 5 minutes for 20-minute tracks. This is normal. If using MCP Inspector in dev mode, you may see timeout errors even though the generation completes.

---

## 🧪 Development

```bash
# Clone
git clone https://github.com/MUZAIC-Organization/muzaic-mcp.git
cd muzaic-mcp

# Install with dev dependencies
uv sync
# Or with pip:
# pip install -e ".[dev]"

# Run in dev mode
# Windows PowerShell:
$env:MUZAIC_API_KEY="your_key"
# macOS/Linux:
export MUZAIC_API_KEY=your_key

uv run mcp dev muzaic_mcp/server.py
# Or with pip:
# python -m muzaic_mcp.server

# Run tests
uv run pytest
# Or with pip:
# pytest
```

### Local Development Setup

If you're developing locally and want to test without publishing to PyPI:

**Windows:**
```powershell
# Install in editable mode
pip install -e .

# Test the command
$env:MUZAIC_API_KEY="your_key"
muzaic-mcp
```

**macOS/Linux:**
```bash
# Install in editable mode
pip install -e .

# Test the command
export MUZAIC_API_KEY=your_key
muzaic-mcp
```

### Testing with MCP Inspector

```bash
npx @modelcontextprotocol/inspector
# → Transport: stdio
# → Command: uv run muzaic-mcp
# Or: python -m muzaic_mcp.server
```

**Windows Note:** If you encounter issues with `npx`, ensure Node.js is installed and in your PATH. You can also use the full path to `npx` if needed.

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.

---

## 🔗 Links

- **Website**: [muzaic.ai](https://muzaic.ai)
- **API Docs**: [docs.muzaic.ai](https://docs.muzaic.ai)
- **Get API Key**: [adminpanel.muzaic.ai](https://adminpanel.muzaic.ai)
- **Support**: [service@muzaic.ai](mailto:service@muzaic.ai)
