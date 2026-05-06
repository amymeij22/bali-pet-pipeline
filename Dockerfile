FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py config.py database.py storage.py bmkg_client.py preprocessing.py \
    biometeo_engine.py classification.py logger.py destinations.py ./
COPY scripts ./scripts/

RUN chown -R nobody /app
USER nobody
CMD ["python", "main.py"]
