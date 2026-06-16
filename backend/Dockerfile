FROM python:3.11-slim

  WORKDIR /app

  # System deps
  RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libpq-dev curl && rm -rf /var/lib/apt/lists/*

  # Python deps (cached layer)
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt

  # App code
  COPY . .

  # Non-root user
  RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
  USER appuser

  EXPOSE 8000
  HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/healthz || exit 1

  CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
  