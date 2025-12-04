# ========================================================================
#  SCRIPT PARA INICIAR SOLO EV_Registry (PowerShell)
# ========================================================================
#  Este script inicia EV_Registry que es necesario para que los CPs
#  puedan registrarse antes de conectarse a EV_Central.
# ========================================================================

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "  INICIANDO EV_Registry" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

# Detectar IP de la base de datos (Central)
$CENTRAL_IP_BD = "127.0.0.1"
if (Test-Path "central_ip.txt") {
    $CENTRAL_IP_BD = Get-Content "central_ip.txt" -First 1
}

Write-Host "[INFO] Configuración:" -ForegroundColor Yellow
Write-Host "  - Base de datos: ${CENTRAL_IP_BD}:3306"
Write-Host "  - Base de datos: evcharging"
Write-Host "  - Puerto Registry: 6000"
Write-Host ""

# Verificar si hay certificados SSL
$certPath = "certificados\registry_cert.pem"
$keyPath = "certificados\registry_key.pem"

if (Test-Path $certPath) {
    if (Test-Path $keyPath) {
        Write-Host "[INFO] Certificados SSL encontrados. Iniciando con HTTPS..." -ForegroundColor Green
        Write-Host ""
        Start-Process -FilePath "python" -ArgumentList "ev_registry\EV_Registry.py", "--db-host", $CENTRAL_IP_BD, "--db-port", "3306", "--db-user", "root", "--db-password", "root", "--db-name", "evcharging", "--port", "6000", "--ssl", "--ssl-cert", $certPath, "--ssl-key", $keyPath -WindowStyle Normal
        Write-Host "[OK] EV_Registry iniciado con HTTPS (puerto 6000)" -ForegroundColor Green
        Write-Host "  - API REST: https://localhost:6000/api" -ForegroundColor Cyan
    } else {
        Write-Host "[INFO] Certificado encontrado pero falta la clave. Iniciando con HTTP..." -ForegroundColor Yellow
        Start-Process -FilePath "python" -ArgumentList "ev_registry\EV_Registry.py", "--db-host", $CENTRAL_IP_BD, "--db-port", "3306", "--db-user", "root", "--db-password", "root", "--db-name", "evcharging", "--port", "6000" -WindowStyle Normal
        Write-Host "[OK] EV_Registry iniciado con HTTP (puerto 6000)" -ForegroundColor Green
        Write-Host "  - API REST: http://localhost:6000/api" -ForegroundColor Cyan
    }
} else {
    Write-Host "[INFO] No se encontraron certificados SSL. Iniciando con HTTP..." -ForegroundColor Yellow
    Write-Host "[ADVERTENCIA] Para usar HTTPS, ejecuta: generar_certificados_ssl.bat" -ForegroundColor Yellow
    Write-Host ""
    Start-Process -FilePath "python" -ArgumentList "ev_registry\EV_Registry.py", "--db-host", $CENTRAL_IP_BD, "--db-port", "3306", "--db-user", "root", "--db-password", "root", "--db-name", "evcharging", "--port", "6000" -WindowStyle Normal
    Write-Host "[OK] EV_Registry iniciado con HTTP (puerto 6000)" -ForegroundColor Green
    Write-Host "  - API REST: http://localhost:6000/api" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "  EV_Registry iniciado en ventana separada" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[IMPORTANTE] Espera unos segundos a que EV_Registry se inicie completamente" -ForegroundColor Yellow
Write-Host "  antes de ejecutar los CPs." -ForegroundColor Yellow
Write-Host ""
Write-Host "Presiona cualquier tecla para continuar..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

