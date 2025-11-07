# Script de ejecución para EV_Central en PC_A
# Este script debe ejecutarse desde el directorio raíz del proyecto

# Leer la IP central del archivo
$CENTRAL_IP = (Get-Content "central_ip.txt" -ErrorAction SilentlyContinue).Trim()
if ([string]::IsNullOrEmpty($CENTRAL_IP)) {
    $CENTRAL_IP = "127.0.0.1"
    Write-Host "[ADVERTENCIA] No se pudo leer central_ip.txt, usando 127.0.0.1" -ForegroundColor Yellow
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   EJECUTANDO EV_CENTRAL (PC_A)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Configuración:" -ForegroundColor Green
Write-Host "  - IP Central:  $CENTRAL_IP" -ForegroundColor White
Write-Host "  - Puerto:      5000" -ForegroundColor White
Write-Host "  - Kafka:       $CENTRAL_IP:9092" -ForegroundColor White
Write-Host "  - MySQL:       127.0.0.1:3306" -ForegroundColor White
Write-Host ""
Write-Host "El servidor Central estará escuchando conexiones de monitores..." -ForegroundColor Yellow
Write-Host ""

# Ejecutar EV_Central con Python (modo consola con mensajes visibles)
py ev_central\EV_Central.py `
  --port 5000 `
  --kafka "${CENTRAL_IP}:9092" `
  --db "127.0.0.1:3306:root:root:evcharging" `
  --no-tui

Write-Host ""
Write-Host "EV_Central ha finalizado." -ForegroundColor Red

