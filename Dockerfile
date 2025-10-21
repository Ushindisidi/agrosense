FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim

RUN useradd -m -u 1000 agrosense && \
    mkdir -p /app && \
    chown -R agrosense:agrosense /app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /home/agrosense/.local

RUN chown -R agrosense:agrosense /home/agrosense/.local && \
    chmod -R 755 /home/agrosense/.local

COPY --chown=agrosense:agrosense . .

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/home/agrosense/.local/bin:/usr/local/bin:$PATH \
    PORT=8000 \
    CREWAI_STORAGE_DIR=/home/agrosense/.local/share/crewai

USER agrosense

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

EXPOSE ${PORT}

CMD ["uvicorn", "src.agrosense.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "75"]