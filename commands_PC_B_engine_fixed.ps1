# ============================================================
# SCRIPT CORREGIDO: Arrancar Engine con network host
# ============================================================
# Este script arranca el Engine usando --network host para
# mejor compatibilidad con el Monitor

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
Write-Host "  INICIANDO ENGINE (CP_001) CON NETWORK HOST" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Configuracion:" -ForegroundColor Yellow
Write-Host "  - CP ID:      CP_001"
Write-Host "  - Puerto:     5001"
Write-Host "  - Kafka:      ${CENTRAL_IP}:9092"
Write-Host "  - Red:        host (acceso directo a red del PC)"
Write-Host ""

# Arrancar Engine con network host
docker run --rm --network host --name engine `
  -e ENGINE_PORT=5001 -e CP_ID=CP_001 `
  -e KAFKA_SERVER="${CENTRAL_IP}:9092" `
  ev_engine:local

