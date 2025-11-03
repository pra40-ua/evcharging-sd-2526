# Construir imÃ¡genes (si no existen)
docker build -t ev_engine:local -f ev_cp_engine/Dockerfile .
docker build -t ev_monitor:local -f ev_cp_monitor/Dockerfile .
docker build -t ev_driver:local -f ev_driver/Dockerfile .

# Arrancar Engine
docker run --rm -p 5001:5001 --name engine `
  -e ENGINE_PORT=5001 -e CP_ID=CP_001 `
  -e KAFKA_SERVER="172.21.42.5:9092" `
  ev_engine:local
