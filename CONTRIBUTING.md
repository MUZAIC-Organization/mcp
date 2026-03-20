# Contributing to Muzaic MCP Server

Thank you for your interest in contributing! Here's how to get started.

## Development Setup

```bash
git clone https://github.com/MUZAIC-Organization/muzaic-mcp.git
cd muzaic-mcp
uv sync
```

## Running Locally

**macOS/Linux:**
```bash
export MUZAIC_API_KEY=your_key
uv run mcp dev muzaic_mcp/server.py
# Or with pip:
python -m muzaic_mcp.server
```

**Windows:**
```powershell
$env:MUZAIC_API_KEY="your_key"
uv run mcp dev muzaic_mcp/server.py
# Or with pip:
python -m muzaic_mcp.server
```

## Testing

```bash
uv run pytest
```

## Pull Requests

1. Fork the repo and create your branch from `main`
2. Add tests if you've added functionality
3. Ensure the test suite passes
4. Submit your pull request

## Code Style

- Use type hints for all function signatures
- Follow existing patterns for tool definitions
- Keep tool descriptions clear and concise

## Reporting Issues

Open an issue at [github.com/MUZAIC-Organization/muzaic-mcp/issues](https://github.com/MUZAIC-Organization/muzaic-mcp/issues) with:
- Steps to reproduce
- Expected vs actual behavior
- Python version and MCP client used

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
