FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml /app/pyproject.toml
COPY backend /app

RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir . \
    && python -c "import langgraph, psycopg_pool"

EXPOSE 8000

CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]
