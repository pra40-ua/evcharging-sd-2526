# syntax=docker/dockerfile:1
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ev_driver/ ev_driver/
COPY ev_common/ ev_common/

ENV KAFKA_BROKER=127.0.0.1:9092 \
    DRIVER_ID=DRIVER_456 \
    CP_ID=CP_001 \
    MAT=ABC-1234 \
    KW=1.0 \
    LISTEN=false

# Comando por defecto: enviar una solicitud simple; sobreescribe con docker run ... si quieres otro flujo
CMD ["sh", "-c", "python ev_driver/EV_Driver.py --kafka ${KAFKA_BROKER} --id ${DRIVER_ID} --cp ${CP_ID} --mat ${MAT} --kw ${KW} ${LISTEN:+--listen}"]


