FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system worthit && useradd --system --gid worthit --home-dir /app worthit

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=worthit:worthit . .
RUN mkdir -p /app/data && chown worthit:worthit /app/data \
    && chmod +x /app/scripts/container_entrypoint.sh

USER worthit
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/healthz', timeout=3)"]

ENTRYPOINT ["/app/scripts/container_entrypoint.sh"]
