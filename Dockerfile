FROM python:3.11-slim

# Prevent debconf warnings during build
ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_ROOT_USER_ACTION=ignore
ENV PIP_NO_WARN_SCRIPT_LOCATION=1

# Set working directory
WORKDIR /app

# Install system dependencies if needed
# (psycopg2-binary doesn't need libpq-dev, but include if you switch to psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8088

# Health check (optional)
HEALTHCHECK --interval=360s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8088/health')" || exit 1

# Run the application
CMD ["uvicorn", "app.api_server:app", "--host", "0.0.0.0", "--port", "8088"]
