# Arrancar Monitor
docker run --rm --name monitor `
  -e CP_ID=CP_001 `
  -e CENTRAL_IP=172.21.42.5 -e CENTRAL_PORT=5000 `
  -e ENGINE_IP=172.28.224.1 -e ENGINE_PORT=5001 `
  ev_monitor:local
