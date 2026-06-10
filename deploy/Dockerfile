# RevenueGuard — Cloud Run image.
# Build context is the REPO ROOT:  docker build -f deploy/Dockerfile -t revenueguard .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

# Install deps first for layer caching.
COPY pyproject.toml README.md ./
RUN pip install --upgrade pip && pip install .

# App code + the vendored Fivetran MCP server (launched as a stdio child).
COPY revenueguard ./revenueguard
COPY main.py ./
COPY vendor ./vendor

# Cloud Run injects PORT; uvicorn binds it.
EXPOSE 8080
CMD ["python", "main.py"]
