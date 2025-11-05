# ============================================================
# SCRIPT CORREGIDO: Arrancar Monitor con network host
# ============================================================
# Este script corrige el problema de conexion usando --network host
# para que el contenedor pueda acceder a la IP externa del Central

# Leer IP del Central desde central_ip.txt
if (Test-Path "central_ip.txt") {
    $CENTRAL_IP = (Get-Content "central_ip.txt" -First 1).Trim()
    Write-Host "[OK] IP del Central: $CENTRAL_IP" -ForegroundColor Green
} else {
    Write-Host "[ERROR] No se encuentra central_ip.txt" -ForegroundColor Red
    Write-Host "        Copia este archivo desde PC_A primero." -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  INICIANDO MONITOR (CP_001) CON NETWORK HOST" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Configuracion:" -ForegroundColor Yellow
Write-Host "  - CP ID:      CP_001"
Write-Host "  - Central:    ${CENTRAL_IP}:5000"
Write-Host "  - Engine:     localhost:5001"
Write-Host "  - Red:        host (acceso directo a red del PC)"
Write-Host ""
Write-Host "NOTA: Con --network host, el contenedor usa la red del PC directamente"
Write-Host ""

# Arrancar Monitor con network host
docker run --rm --network host --name monitor `
  -e CP_ID=CP_001 `
  -e CENTRAL_IP=$CENTRAL_IP -e CENTRAL_PORT=5000 `
  -e ENGINE_IP=localhost -e ENGINE_PORT=5001 `
  ev_monitor:local


