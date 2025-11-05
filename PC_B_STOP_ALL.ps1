# ============================================================
# Script PowerShell para detener todos los contenedores de PC_B
# ============================================================

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   DETENIENDO TODOS LOS CONTENEDORES DE PC_B" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Verificar que Docker está corriendo
try {
    $null = docker ps 2>&1
} catch {
    Write-Host "[ERROR] Docker no esta corriendo o no esta disponible." -ForegroundColor Red
    Write-Host ""
    Read-Host "Presiona Enter para continuar"
    exit 1
}

# Buscar contenedores con la etiqueta
Write-Host "Buscando contenedores de EV Charging PC_B..." -ForegroundColor Cyan
Write-Host ""

$containers = docker ps -q --filter "label=project=evcharging-pc-b"

if (-not $containers) {
    Write-Host "No se encontraron contenedores de PC_B en ejecucion." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Verifica que los CPs esten corriendo con: docker ps"
    Write-Host ""
    Read-Host "Presiona Enter para continuar"
    exit 0
}

# Mostrar contenedores que se van a detener
Write-Host "Contenedores que seran detenidos:" -ForegroundColor Yellow
Write-Host "----------------------------------------"
docker ps --filter "label=project=evcharging-pc-b" --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}"
Write-Host "----------------------------------------"
Write-Host ""

# Confirmar acción
$confirm = Read-Host "¿Estas seguro de que quieres detener TODOS estos contenedores? (S/N)"
if ($confirm -ne "S" -and $confirm -ne "s") {
    Write-Host ""
    Write-Host "Operacion cancelada." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Presiona Enter para continuar"
    exit 0
}

Write-Host ""
Write-Host "Deteniendo contenedores..." -ForegroundColor Cyan
Write-Host ""

# Detener todos los contenedores
$containerIds = docker ps -q --filter "label=project=evcharging-pc-b"
foreach ($id in $containerIds) {
    $name = docker inspect --format='{{.Name}}' $id
    $name = $name.TrimStart('/')
    Write-Host "Deteniendo: $name" -ForegroundColor Gray
    docker stop $id | Out-Null
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "     TODOS LOS CONTENEDORES DETENIDOS EXITOSAMENTE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Los contenedores han sido detenidos y eliminados." -ForegroundColor White
Write-Host "Las ventanas de PowerShell se cerraran automaticamente." -ForegroundColor White
Write-Host ""

Read-Host "Presiona Enter para cerrar"

