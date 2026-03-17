FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy package files
COPY pyproject.toml README.md LICENSE ./
COPY muzaic_mcp/ ./muzaic_mcp/

# Install the package
RUN pip install --no-cache-dir .

# Create non-root user for security
RUN adduser --disabled-password --gecos "" mcpuser
USER mcpuser

ENTRYPOINT ["muzaic-mcp"]
