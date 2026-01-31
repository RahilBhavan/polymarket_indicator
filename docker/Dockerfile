# CryptoSignal bot: production image
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN useradd -m -u 1000 appuser
COPY --chown=appuser:appuser . .
RUN pip install --no-cache-dir uv && uv sync --no-dev

USER appuser
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
