# RevenueGuard — Cloud Run image.
# Build context is the REPO ROOT:  docker build -f deploy/Dockerfile -t revenueguard .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    FIVETRAN_MCP_DIR=/app/vendor/fivetran-mcp \
    ADK_AGENTS_DIR=/app/agents

WORKDIR /app

# Runtime deps installed directly (the app runs from /app source, not site-packages,
# so we don't pip-install the project itself). uv provides uvx for the MCP server.
RUN pip install --upgrade pip && pip install \
    "google-adk>=1.0.0" \
    "mcp>=1.25.0" \
    "google-cloud-bigquery>=3.25.0" \
    "google-genai>=1.0.0" \
    "python-dotenv>=1.0.0" \
    "uv>=0.5.0"

# App code + the vendored Fivetran MCP server (launched as a stdio child).
# The agent package lives under /app/agents so ADK lists only real apps.
COPY revenueguard ./agents/revenueguard
COPY main.py ./
COPY vendor ./vendor

# Pre-build the MCP server's uvx environment so cold starts don't pay the build.
# The server exits cleanly on stdin EOF, which is all we need to warm the cache.
RUN uvx --from /app/vendor/fivetran-mcp fivetran-mcp </dev/null || true

EXPOSE 8080
CMD ["python", "main.py"]
