@echo off
REM Script para reparar/verificar el usuario ev_user en MariaDB
REM Soluciona problemas de autenticación 1045 Access denied

echo ========================================================================
echo           REPARAR USUARIO ev_user EN MARIADB
echo ========================================================================
echo.
echo Este script corregira el usuario ev_user para que pueda conectarse
echo desde cualquier host usando el plugin mysql_native_password.
echo.
echo ========================================================================
echo.

REM Verificar que el contenedor de MariaDB está corriendo
docker ps --filter "name=mariadb" --format "{{.Names}}" | findstr /C:"mariadb" >nul
if %errorlevel% neq 0 (
    echo [ERROR] El contenedor mariadb no esta corriendo.
    echo Por favor, inicia el contenedor primero con: docker-compose up -d mariadb
    pause
    exit /b 1
)

echo [1/3] Verificando contenedor mariadb...
docker ps --filter "name=mariadb" --format "table {{.Names}}\t{{.Status}}"
echo.

echo [2/3] Aplicando correccion al usuario ev_user...
docker exec -i mariadb mysql -u root -proot < db\fix_ev_user.sql
if %errorlevel% neq 0 (
    echo [ERROR] No se pudo ejecutar el script SQL.
    echo Intentando ejecutar comandos SQL directamente...
    echo.
    
    REM Ejecutar comandos SQL directamente
    docker exec mariadb mysql -u root -proot -e "DROP USER IF EXISTS 'ev_user'@'%%'; DROP USER IF EXISTS 'ev_user'@'localhost'; DROP USER IF EXISTS 'ev_user'@'127.0.0.1';"
    docker exec mariadb mysql -u root -proot -e "CREATE USER 'ev_user'@'%%' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';"
    docker exec mariadb mysql -u root -proot -e "CREATE USER 'ev_user'@'localhost' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';"
    docker exec mariadb mysql -u root -proot -e "CREATE USER 'ev_user'@'127.0.0.1' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';"
    docker exec mariadb mysql -u root -proot -e "GRANT SELECT, INSERT, UPDATE, DELETE ON evcharging.* TO 'ev_user'@'%%';"
    docker exec mariadb mysql -u root -proot -e "GRANT SELECT, INSERT, UPDATE, DELETE ON evcharging.* TO 'ev_user'@'localhost';"
    docker exec mariadb mysql -u root -proot -e "GRANT SELECT, INSERT, UPDATE, DELETE ON evcharging.* TO 'ev_user'@'127.0.0.1';"
    docker exec mariadb mysql -u root -proot -e "FLUSH PRIVILEGES;"
)

echo.
echo [3/3] Verificando usuario ev_user...
docker exec mariadb mysql -u root -proot -e "SELECT CONCAT('Usuario: ', User, '@', Host, ' | Plugin: ', plugin) AS usuario_info FROM mysql.user WHERE User = 'ev_user';"
echo.

echo ========================================================================
echo           REPARACION COMPLETADA
echo ========================================================================
echo.
echo El usuario ev_user ha sido configurado con:
echo   - Plugin: mysql_native_password (compatible con Python)
echo   - Host: %% (permite conexiones desde cualquier host)
echo   - Base de datos: evcharging
echo   - Contrasena: ev_user_pass
echo.
echo Ahora puedes intentar conectar nuevamente con EV_Central.
echo.
pause



