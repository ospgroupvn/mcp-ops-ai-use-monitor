FROM python:3.12-slim

WORKDIR /app

# Copy source code first (needed for pyproject.toml install)
COPY pyproject.toml .
COPY src/ ./src/

# Install dependencies
RUN pip install --no-cache-dir .

# Create tokens file
RUN touch /app/tokens.json && echo "[]" > /app/tokens.json

# Expose port
EXPOSE 8000

# Run simple server (SSE transport for Claude Code)
CMD ["python", "-m", "src.server_simple"]
