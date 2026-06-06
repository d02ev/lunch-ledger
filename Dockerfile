# Use uv's official image — Python 3.12 on Debian slim
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Copy dependency manifest and lockfile first (layer caching)
COPY pyproject.toml uv.lock* ./

# Install dependencies into the system Python (no venv needed in container)
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code
COPY . .

# Final sync to install the project itself
RUN uv sync --frozen --no-dev

# Create data directory for SQLite persistence
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:api", "--host", "0.0.0.0", "--port", "8000"]