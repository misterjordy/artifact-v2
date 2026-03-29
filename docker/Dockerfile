FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"
COPY . .
# ZT Pillar 4: Run as non-root (prevent container escape privilege escalation)
RUN useradd -r -s /bin/false -d /app appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["uvicorn", "artiFACT.main:app", "--host", "0.0.0.0", "--port", "8000"]
