# Script para limpiar la base de datos del sistema de carga EV
# Ejecutar con: powershell .\limpiar_bd.ps1

Write-Host "=== LIMPIANDO BASE DE DATOS ===" -ForegroundColor Yellow
Write-Host "Este script eliminará todos los datos de las tablas." -ForegroundColor Yellow
Write-Host ""

# Confirmar acción
$confirmacion = Read-Host "¿Estás seguro de que deseas limpiar la base de datos? (S/N)"

if ($confirmacion -eq "S" -or $confirmacion -eq "s") {
    Write-Host "`nObteniendo lista de tablas existentes..." -ForegroundColor Cyan
    
    # Obtener lista de tablas existentes
    $tablas = docker exec mysql mysql -u root -proot evcharging -N -e "SHOW TABLES;" 2>$null | Where-Object { $_ -ne "" }
    
    if ($tablas.Count -eq 0) {
        Write-Host "No se encontraron tablas en la base de datos." -ForegroundColor Yellow
        exit
    }
    
    Write-Host "`nEliminando datos de las tablas..." -ForegroundColor Cyan
    
    $tablasLimpias = @()
    foreach ($tabla in $tablas) {
        Write-Host "  - $tabla..." -ForegroundColor White
        $resultado = docker exec mysql mysql -u root -proot evcharging -e "TRUNCATE TABLE $tabla;" 2>&1
        if ($LASTEXITCODE -eq 0) {
            $tablasLimpias += $tabla
        } else {
            Write-Host "    (Error al limpiar $tabla, pero continuando...)" -ForegroundColor Yellow
        }
    }
    
    Write-Host "`n=== BASE DE DATOS LIMPIADA EXITOSAMENTE ===" -ForegroundColor Green
    Write-Host "Tablas limpiadas: $($tablasLimpias.Count) de $($tablas.Count)" -ForegroundColor Green
    
    # Verificar que las tablas están vacías
    Write-Host "`nVerificando estado de las tablas..." -ForegroundColor Cyan
    $queries = $tablas | ForEach-Object { "SELECT '$_' as tabla, COUNT(*) as registros FROM $_" }
    $query = $queries -join " UNION ALL "
    docker exec mysql mysql -u root -proot evcharging -e $query 2>$null
} else {
    Write-Host "`nOperación cancelada." -ForegroundColor Red
}


