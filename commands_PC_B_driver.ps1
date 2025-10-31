# Arrancar Driver
docker run --rm --name driver `
  -e KAFKA_BROKER="172.21.42.5:9092" `
  -e DRIVER_ID=DRIVER_456 -e CP_ID=CP_001 -e MAT=ABC-1234 -e KW=1.0 -e LISTEN=true `
  ev_driver:local
