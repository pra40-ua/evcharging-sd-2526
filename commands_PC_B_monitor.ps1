# 1. Leer IP de la Central desde central_ip.txt
$CENTRAL_IP = (Get-Content "central_ip.txt" -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
if (-not $CENTRAL_IP) {
    Write-Host "ERROR: No se pudo leer central_ip.txt" -ForegroundColor Red
    exit 1
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "PC_B: Monitor" -ForegroundColor Cyan
Write-Host "Central IP: $CENTRAL_IP" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Cyan

# 2. Esperar a que el Engine esté disponible
Write-Host "[WAIT] Esperando a que el Engine esté disponible en puerto 5001..." -ForegroundColor Yellow
$maxAttempts = 30
$attempt = 0
$engineReady = $false

while ($attempt -lt $maxAttempts) {
    $attempt++
    try {
        $connection = Test-NetConnection -ComputerName localhost -Port 5001 -WarningAction SilentlyContinue
        if ($connection.TcpTestSucceeded) {
            Write-Host "[OK] Engine disponible en localhost:5001" -ForegroundColor Green
            $engineReady = $true
            break
        }
    } catch {}
    Write-Host "  Intento $attempt/$maxAttempts..." -ForegroundColor Gray
    Start-Sleep -Seconds 2
}

if (-not $engineReady) {
    Write-Host "[ERROR] Engine no está disponible después de esperar 60s" -ForegroundColor Red
    Write-Host "Asegúrate de que la ventana Build+Engine esté ejecutándose" -ForegroundColor Yellow
    exit 1
}

# 3. Limpiar contenedor previo si existe
docker rm -f monitor 2>$null

# 4. Determinar ENGINE_IP
# Opción 1: host.docker.internal (recomendado para Docker Desktop Windows)
$ENGINE_IP = "host.docker.internal"

Write-Host "[RUN] Lanzando Monitor..." -ForegroundColor Yellow
Write-Host "  CP_ID:   CP_001" -ForegroundColor Gray
Write-Host "  CENTRAL: ${CENTRAL_IP}:5000" -ForegroundColor Gray
Write-Host "  ENGINE:  ${ENGINE_IP}:5001" -ForegroundColor Gray
Write-Host "" -ForegroundColor Gray
Write-Host "IMPORTANTE: Si el Monitor reporta 'Conexión con Engine perdida':" -ForegroundColor Yellow
Write-Host "  1. Verifica que Docker Desktop esté usando WSL2" -ForegroundColor Yellow
Write-Host "  2. Prueba cambiar ENGINE_IP en este script a:" -ForegroundColor Yellow
Write-Host "     - 172.17.0.1 (gateway Docker por defecto)" -ForegroundColor Yellow
Write-Host "     - Tu IP local del adaptador vEthernet (WSL)" -ForegroundColor Yellow
Write-Host "" -ForegroundColor Gray

# 5. Arrancar Monitor
docker run --rm --name monitor `
  -e CP_ID=CP_001 `
  -e CENTRAL_IP=$CENTRAL_IP -e CENTRAL_PORT=5000 `
  -e ENGINE_IP=$ENGINE_IP -e ENGINE_PORT=5001 `
  ev_monitor:local
