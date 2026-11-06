# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src ./src
COPY datos ./datos
RUN useradd --create-home app && mkdir -p /data/evidencias && chown -R app /data /app

# --- Imagen de pruebas: docker compose --profile tests up --exit-code-from tests ---
FROM base AS pruebas
COPY requirements-dev.txt pyproject.toml ./
RUN pip install -r requirements-dev.txt
COPY tests ./tests
COPY docs ./docs
USER app
CMD ["python", "-m", "pytest", "--cov=src", "--cov-fail-under=80", "--cov-report=term-missing"]

# --- Imagen de producción (última etapa: es la que se construye por defecto) ---
FROM base AS produccion
USER app
ENV EVIDENCIAS_DIR=/data/evidencias
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\",\"8000\")}/salud')"
CMD ["sh", "-c", "uvicorn --factory src.api.main:crear_app --host 0.0.0.0 --port ${PORT:-8000}"]
