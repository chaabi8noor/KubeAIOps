FROM python:3.12-slim

ARG APP_VERSION=0.1.0

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

LABEL org.opencontainers.image.title="capacity-api" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.vendor="KubeAIOps"

RUN addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app app

COPY requirements.txt .
RUN pip install --no-cache-dir --retries 5 --timeout 100 -r requirements.txt

COPY --chown=10001:10001 app ./app

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
