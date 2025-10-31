# 1. Leer IP de la Central desde central_ip.txt
$CENTRAL_IP = (Get-Content "central_ip.txt" -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
if (-not $CENTRAL_IP) {
    Write-Host "ERROR: No se pudo leer central_ip.txt" -ForegroundColor Red
    exit 1
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "PC_B: Driver" -ForegroundColor Cyan
Write-Host "Central IP: $CENTRAL_IP" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Cyan

# 2. Esperar un momento para que Monitor se registre
Write-Host "[WAIT] Esperando 10 segundos a que el Monitor se registre con la Central..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# 3. Limpiar contenedor previo si existe
docker rm -f driver 2>$null

# 4. Arrancar Driver
Write-Host "[RUN] Lanzando Driver..." -ForegroundColor Yellow
Write-Host "  DRIVER_ID: DRIVER_456" -ForegroundColor Gray
Write-Host "  CP_ID:     CP_001" -ForegroundColor Gray
Write-Host "  KAFKA:     ${CENTRAL_IP}:9092" -ForegroundColor Gray
Write-Host "  KW:        1.0 kWh" -ForegroundColor Gray
Write-Host "  MAT:       ABC-1234" -ForegroundColor Gray
Write-Host ""

docker run --rm --name driver `
  -e KAFKA_BROKER="${CENTRAL_IP}:9092" `
  -e DRIVER_ID=DRIVER_456 -e CP_ID=CP_001 -e MAT=ABC-1234 -e KW=1.0 -e LISTEN=true `
  ev_driver:local
