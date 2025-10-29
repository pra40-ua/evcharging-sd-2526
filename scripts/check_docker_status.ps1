<#
.SYNOPSIS
    Verifica el estado de los contenedores Docker de EV Charging
#>

Write-Host "=" * 60
Write-Host "Verificando contenedores Docker" -ForegroundColor Cyan
Write-Host "=" * 60

Write-Host "`n[1] Contenedores corriendo:" -ForegroundColor Yellow
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | Select-String -Pattern "central|mysql|kafka|engine|monitor|driver"

Write-Host "`n[2] Todos los contenedores (incluyendo detenidos):" -ForegroundColor Yellow
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | Select-String -Pattern "central|mysql|kafka|engine|monitor|driver"

Write-Host "`n[3] Verificando si el puerto 5000 está en uso:" -ForegroundColor Yellow
$port5000 = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
if ($port5000) {
    Write-Host "✓ El puerto 5000 está siendo usado por:" -ForegroundColor Green
    $port5000 | Format-Table LocalAddress, LocalPort, State, OwningProcess -AutoSize
} else {
    Write-Host "✗ No hay nada escuchando en el puerto 5000" -ForegroundColor Red
}

Write-Host "`n[4] Verificando con netstat:" -ForegroundColor Yellow
netstat -an | Select-String ":5000"

Write-Host "`n" + ("=" * 60)
Write-Host "Consejos:" -ForegroundColor Cyan
Write-Host "- Si no ves 'central' en la lista, necesitas iniciar la Central" -ForegroundColor Gray
Write-Host "- El comando para iniciarla está en commands_PC_A.txt" -ForegroundColor Gray
Write-Host "- Asegúrate de estar en el directorio evcharging-sd-2526" -ForegroundColor Gray

