FROM python:3.11-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# ------------------------------
# 🚀 FINAL STAGE
# ------------------------------
FROM python:3.11-slim

# Create a non-root user and working directory
RUN useradd -m -u 1000 agrosense && \
    mkdir -p /app && \
    chown -R agrosense:agrosense /app

WORKDIR /app

# Basic tools
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies from builder
COPY --from=builder /root/.local /home/agrosense/.local

# Copy source files
COPY --chown=agrosense:agrosense . .

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/home/agrosense/.local/bin:$PATH \
    PORT=8000

USER agrosense
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

EXPOSE ${PORT}

CMD ["uvicorn", "src.agrosense.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
