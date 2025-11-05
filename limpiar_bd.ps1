# Script para limpiar la base de datos del sistema de carga EV
# Ejecutar con: powershell .\limpiar_bd.ps1

Write-Host "=== LIMPIANDO BASE DE DATOS ===" -ForegroundColor Yellow
Write-Host "Este script eliminará todos los datos de las tablas." -ForegroundColor Yellow
Write-Host ""

# Confirmar acción
$confirmacion = Read-Host "¿Estás seguro de que deseas limpiar la base de datos? (S/N)"

if ($confirmacion -eq "S" -or $confirmacion -eq "s") {
    Write-Host "`nEliminando datos de la tabla charging_points..." -ForegroundColor Cyan
    docker exec mysql mysql -u root -proot evcharging -e "TRUNCATE TABLE charging_points;"
    
    Write-Host "Eliminando datos de la tabla telemetria_log..." -ForegroundColor Cyan
    docker exec mysql mysql -u root -proot evcharging -e "TRUNCATE TABLE telemetria_log;"
    
    Write-Host "`n=== BASE DE DATOS LIMPIADA EXITOSAMENTE ===" -ForegroundColor Green
    
    # Verificar que las tablas están vacías
    Write-Host "`nVerificando estado de las tablas..." -ForegroundColor Cyan
    docker exec mysql mysql -u root -proot evcharging -e "SELECT COUNT(*) as charging_points_count FROM charging_points; SELECT COUNT(*) as telemetria_log_count FROM telemetria_log;"
} else {
    Write-Host "`nOperación cancelada." -ForegroundColor Red
}

