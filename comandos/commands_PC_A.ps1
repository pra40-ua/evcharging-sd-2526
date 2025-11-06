# Script de ejecución para EV_Central en PC_A
# Este script debe ejecutarse desde el directorio raíz del proyecto

# Cambiar al directorio del script si es necesario
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
if ($projectRoot) {
    Set-Location $projectRoot
    Write-Host "Directorio cambiado a: $projectRoot" -ForegroundColor Gray
}

# Leer la IP central del archivo
$CENTRAL_IP = (Get-Content "central_ip.txt" -ErrorAction SilentlyContinue).Trim()
if ([string]::IsNullOrEmpty($CENTRAL_IP)) {
    $CENTRAL_IP = "127.0.0.1"
    Write-Host "[ADVERTENCIA] No se pudo leer central_ip.txt, usando 127.0.0.1" -ForegroundColor Yellow
}

# Configurar la ventana para que sea visible
$Host.UI.RawUI.WindowTitle = "EV_Central - PC_A - Terminal de Información"
Clear-Host

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
Write-Host "Directorio de trabajo: $projectRoot" -ForegroundColor Gray
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   INICIANDO SERVIDOR CENTRAL" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "El servidor Central estará escuchando conexiones de monitores..." -ForegroundColor Yellow
Write-Host "Toda la información se mostrará en esta ventana." -ForegroundColor Yellow
Write-Host ""
Write-Host "Presiona Ctrl+C para detener el servidor." -ForegroundColor Gray
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Ejecutar EV_Central con Python
try {
    # Intentar primero con 'py', luego con 'python'
    $pythonCmd = "py"
    if (-not (Get-Command $pythonCmd -ErrorAction SilentlyContinue)) {
        $pythonCmd = "python"
        if (-not (Get-Command $pythonCmd -ErrorAction SilentlyContinue)) {
            throw "No se encontró Python. Asegúrate de que Python esté instalado y en el PATH."
        }
    }
    
    Write-Host "Usando comando Python: $pythonCmd" -ForegroundColor Gray
    Write-Host ""
    
    & $pythonCmd ev_central\EV_Central.py `
      --port 5000 `
      --kafka "${CENTRAL_IP}:9092" `
      --db "127.0.0.1:3306:root:root:evcharging"
} catch {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "   ERROR AL EJECUTAR EV_CENTRAL" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Verifica que:" -ForegroundColor Yellow
    Write-Host "  1. Python está instalado y en el PATH" -ForegroundColor Yellow
    Write-Host "  2. Estás en el directorio correcto del proyecto" -ForegroundColor Yellow
    Write-Host "  3. Las dependencias están instaladas (pip install -r requirements.txt)" -ForegroundColor Yellow
    Write-Host ""
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Red
Write-Host "   EV_CENTRAL HA FINALIZADO" -ForegroundColor Red
Write-Host "========================================" -ForegroundColor Red
Write-Host ""
Write-Host "Presiona cualquier tecla para cerrar esta ventana..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

