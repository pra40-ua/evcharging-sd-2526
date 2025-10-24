# syntax=docker/dockerfile:1
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Copiar e instalar dependencias mínimas
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código necesario
COPY ev_central/ ev_central/
COPY ev_common/ ev_common/

# Variables por defecto (pueden sobreescribirse en runtime)
ENV CENTRAL_PORT=5000 \
    KAFKA_BROKER=127.0.0.1:9092 \
    DB_URL=

EXPOSE 5000

CMD ["sh", "-c", "python ev_central/EV_Central.py --port ${CENTRAL_PORT} --kafka ${KAFKA_BROKER} ${DB_URL:+--db ${DB_URL}}"]
