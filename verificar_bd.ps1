# Script para verificar el estado del CP en la base de datos
# Ejecutar con: powershell .\verificar_bd.ps1

Write-Host "=== Verificando estado de CP_001 en la BD ===" -ForegroundColor Cyan

# Conectar al contenedor MySQL y consultar el estado
docker exec mysql mysql -u root -proot evcharging -e "SELECT cp_id, estado, fecha_ultima_conexion FROM charging_points WHERE cp_id='CP_001';"

Write-Host "`n=== Todos los CPs en la BD ===" -ForegroundColor Cyan
docker exec mysql mysql -u root -proot evcharging -e "SELECT cp_id, estado, ubicacion, fecha_ultima_conexion FROM charging_points ORDER BY fecha_ultima_conexion DESC;"

