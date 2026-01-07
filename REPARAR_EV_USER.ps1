# Script PowerShell para reparar/verificar el usuario ev_user en MariaDB
# Soluciona problemas de autenticación 1045 Access denied

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "           REPARAR USUARIO ev_user EN MARIADB" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Este script corregirá el usuario ev_user para que pueda conectarse" -ForegroundColor Yellow
Write-Host "desde cualquier host usando el plugin mysql_native_password." -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

# Verificar que el contenedor de MariaDB está corriendo
$mariadbRunning = docker ps --filter "name=mariadb" --format "{{.Names}}" | Select-String "mariadb"
if (-not $mariadbRunning) {
    Write-Host "[ERROR] El contenedor mariadb no está corriendo." -ForegroundColor Red
    Write-Host "Por favor, inicia el contenedor primero con: docker-compose up -d mariadb" -ForegroundColor Yellow
    Read-Host "Presiona Enter para salir"
    exit 1
}

Write-Host "[1/3] Verificando contenedor mariadb..." -ForegroundColor Green
docker ps --filter "name=mariadb" --format "table {{.Names}}\t{{.Status}}"
Write-Host ""

Write-Host "[2/3] Aplicando corrección al usuario ev_user..." -ForegroundColor Green
$scriptPath = Join-Path $PSScriptRoot "db\fix_ev_user.sql"
if (Test-Path $scriptPath) {
    Get-Content $scriptPath | docker exec -i mariadb mysql -u root -proot
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ADVERTENCIA] No se pudo ejecutar el script SQL. Intentando comandos directos..." -ForegroundColor Yellow
        Write-Host ""
        
        # Ejecutar comandos SQL directamente
        docker exec mariadb mysql -u root -proot -e "DROP USER IF EXISTS 'ev_user'@'%'; DROP USER IF EXISTS 'ev_user'@'localhost'; DROP USER IF EXISTS 'ev_user'@'127.0.0.1';"
        docker exec mariadb mysql -u root -proot -e "CREATE USER 'ev_user'@'%' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';"
        docker exec mariadb mysql -u root -proot -e "CREATE USER 'ev_user'@'localhost' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';"
        docker exec mariadb mysql -u root -proot -e "CREATE USER 'ev_user'@'127.0.0.1' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';"
        docker exec mariadb mysql -u root -proot -e "GRANT SELECT, INSERT, UPDATE, DELETE ON evcharging.* TO 'ev_user'@'%';"
        docker exec mariadb mysql -u root -proot -e "GRANT SELECT, INSERT, UPDATE, DELETE ON evcharging.* TO 'ev_user'@'localhost';"
        docker exec mariadb mysql -u root -proot -e "GRANT SELECT, INSERT, UPDATE, DELETE ON evcharging.* TO 'ev_user'@'127.0.0.1';"
        docker exec mariadb mysql -u root -proot -e "FLUSH PRIVILEGES;"
    }
} else {
    Write-Host "[ERROR] No se encontró el archivo db\fix_ev_user.sql" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[3/3] Verificando usuario ev_user..." -ForegroundColor Green
docker exec mariadb mysql -u root -proot -e "SELECT CONCAT('Usuario: ', User, '@', Host, ' | Plugin: ', plugin) AS usuario_info FROM mysql.user WHERE User = 'ev_user';"
Write-Host ""

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "           REPARACIÓN COMPLETADA" -ForegroundColor Green
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "El usuario ev_user ha sido configurado con:" -ForegroundColor Yellow
Write-Host "  - Plugin: mysql_native_password (compatible con Python)" -ForegroundColor White
Write-Host "  - Host: % (permite conexiones desde cualquier host)" -ForegroundColor White
Write-Host "  - Base de datos: evcharging" -ForegroundColor White
Write-Host "  - Contraseña: ev_user_pass" -ForegroundColor White
Write-Host ""
Write-Host "Ahora puedes intentar conectar nuevamente con EV_Central." -ForegroundColor Green
Write-Host ""
Read-Host "Presiona Enter para salir"



