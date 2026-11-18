FROM python:3.11-slim

# Install system utilities needed for network scanning (ping, iproute), certificates, and timezone
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
    iproute2 \
    ca-certificates \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Jakarta \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy application source files
COPY server.py device_namer.py speedtest_util.py telegram_bot.py webhook.py ./
COPY static/ ./static/

# Data directory will be mounted as volume
RUN mkdir -p /app/data

EXPOSE 8080

CMD ["python3", "server.py"]
