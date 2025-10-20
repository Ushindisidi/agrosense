FROM python:3.11-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim

RUN useradd -m -u 1000 agrosense && \
    mkdir -p /app && \
    chown -R agrosense:agrosense /app

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /home/agrosense/.local

COPY --chown=agrosense:agrosense . .

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/home/agrosense/.local/bin:$PATH \
    PORT=8000

USER agrosense

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose port
EXPOSE ${PORT}

# Run the application
CMD ["uvicorn", "src.agrosense.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]