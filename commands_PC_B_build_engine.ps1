# 1. Leer IP de la Central desde central_ip.txt
$CENTRAL_IP = (Get-Content "central_ip.txt" -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
if (-not $CENTRAL_IP) {
    Write-Host "ERROR: No se pudo leer central_ip.txt" -ForegroundColor Red
    exit 1
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "PC_B: Build + Engine" -ForegroundColor Cyan
Write-Host "Central IP: $CENTRAL_IP" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Cyan

# 2. Construir imágenes
Write-Host "[BUILD] Construyendo ev_engine:local..." -ForegroundColor Green
docker build -t ev_engine:local -f ev_cp_engine/Dockerfile .
if ($LASTEXITCODE -ne 0) { 
    Write-Host "ERROR en build engine" -ForegroundColor Red
    pause
    exit 1
}

Write-Host "[BUILD] Construyendo ev_monitor:local..." -ForegroundColor Green
docker build -t ev_monitor:local -f ev_cp_monitor/Dockerfile .
if ($LASTEXITCODE -ne 0) { 
    Write-Host "ERROR en build monitor" -ForegroundColor Red
    pause
    exit 1
}

Write-Host "[BUILD] Construyendo ev_driver:local..." -ForegroundColor Green
docker build -t ev_driver:local -f ev_driver/Dockerfile .
if ($LASTEXITCODE -ne 0) { 
    Write-Host "ERROR en build driver" -ForegroundColor Red
    pause
    exit 1
}

Write-Host "[BUILD] Todas las imágenes construidas correctamente." -ForegroundColor Green
Write-Host ""

# 3. Limpiar contenedor previo si existe
docker rm -f engine 2>$null

# 4. Arrancar Engine
Write-Host "[RUN] Lanzando Engine en puerto 5001..." -ForegroundColor Yellow
Write-Host "  CP_ID: CP_001" -ForegroundColor Gray
Write-Host "  KAFKA: ${CENTRAL_IP}:9092" -ForegroundColor Gray
Write-Host ""

docker run --rm -p 5001:5001 --name engine `
  -e ENGINE_PORT=5001 -e CP_ID=CP_001 `
  -e KAFKA_SERVER="${CENTRAL_IP}:9092" `
  ev_engine:local
