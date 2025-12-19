# Script PowerShell para eliminar y recrear la base de datos MySQL
# Este script elimina la base de datos y el usuario, y los recrea con permisos correctos

$ErrorActionPreference = "Stop"

Write-Host "=========================================================================" -ForegroundColor Cyan
Write-Host "              RESET COMPLETO DE BASE DE DATOS MYSQL" -ForegroundColor Cyan
Write-Host "=========================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Este script va a:" -ForegroundColor Yellow
Write-Host "  1. Eliminar la base de datos 'evcharging' si existe"
Write-Host "  2. Eliminar usuarios existentes"
Write-Host "  3. Crear la base de datos y usuario con permisos correctos"
Write-Host "  4. Crear todas las tablas necesarias"
Write-Host ""
Write-Host "ADVERTENCIA: Se perderan todos los datos existentes en la BD" -ForegroundColor Red
Write-Host ""
$null = Read-Host "Presiona Enter para continuar o Ctrl+C para cancelar"

Write-Host ""
Write-Host "Verificando que el contenedor MySQL esté corriendo..." -ForegroundColor Yellow

$mysqlRunning = docker ps --filter "name=mysql" --format "{{.Names}}" | Select-String -Pattern "mysql"
if (-not $mysqlRunning) {
    Write-Host "ERROR: El contenedor MySQL no está corriendo." -ForegroundColor Red
    Write-Host "Por favor, inicia Docker Compose primero:" -ForegroundColor Yellow
    Write-Host "  docker-compose up -d mysql" -ForegroundColor White
    Read-Host "Presiona Enter para salir"
    exit 1
}

Write-Host "Contenedor MySQL encontrado: $mysqlRunning" -ForegroundColor Green
Write-Host ""
Write-Host "Ejecutando script de reset..." -ForegroundColor Yellow
Write-Host ""

try {
    # Ejecutar el script SQL de reset
    Get-Content "db\reset_database.sql" | docker exec -i mysql mysql -u root -proot
    
    if ($LASTEXITCODE -ne 0) {
        throw "Error ejecutando el script SQL"
    }
    
    Write-Host ""
    Write-Host "=========================================================================" -ForegroundColor Green
    Write-Host "  Base de datos resetada correctamente" -ForegroundColor Green
    Write-Host "=========================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "La base de datos 'evcharging' ha sido recreada con:" -ForegroundColor White
    Write-Host "  - Usuario: root" -ForegroundColor White
    Write-Host "  - Contraseña: root" -ForegroundColor White
    Write-Host "  - Permisos desde cualquier host (incluyendo Docker)" -ForegroundColor White
    Write-Host "  - Todas las tablas necesarias creadas" -ForegroundColor White
    Write-Host ""
    
} catch {
    Write-Host ""
    Write-Host "ERROR: No se pudo ejecutar el script de reset." -ForegroundColor Red
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host "Verifica que el contenedor MySQL esté corriendo y accesible." -ForegroundColor Yellow
    Read-Host "Presiona Enter para salir"
    exit 1
}

Read-Host "Presiona Enter para salir"

