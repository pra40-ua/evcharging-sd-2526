# Arrancar Monitor
docker run --rm --name monitor `
  -e CP_ID=CP_001 `
  -e CENTRAL_IP=192.168.1.43 -e CENTRAL_PORT=5000 `
  -e ENGINE_IP=host.docker.internal -e ENGINE_PORT=5001 `
  ev_monitor:local
