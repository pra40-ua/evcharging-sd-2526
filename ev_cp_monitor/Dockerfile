# syntax=docker/dockerfile:1
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ev_cp_monitor/ ev_cp_monitor/
COPY ev_common/ ev_common/

ENV CENTRAL_IP=127.0.0.1 \
    CENTRAL_PORT=5000 \
    ENGINE_IP=127.0.0.1 \
    ENGINE_PORT=5001 \
    CP_ID=CP001

CMD ["sh", "-c", "python ev_cp_monitor/EV_CP_M.py --cp_id ${CP_ID} --central_ip ${CENTRAL_IP} --central_port ${CENTRAL_PORT} --engine_ip ${ENGINE_IP} --engine_port ${ENGINE_PORT}"]

