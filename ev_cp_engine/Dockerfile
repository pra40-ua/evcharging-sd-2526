# syntax=docker/dockerfile:1
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ev_cp_engine/ ev_cp_engine/
COPY ev_common/ ev_common/

ENV ENGINE_PORT=5001 \
    CP_ID=CP001 \
    KAFKA_SERVER=127.0.0.1:9092

EXPOSE 5001

CMD ["sh", "-c", "python ev_cp_engine/EV_CP_E.py --port ${ENGINE_PORT} --cp-id ${CP_ID} --kafka ${KAFKA_SERVER}"]

