@echo off
REM Script de diagnóstico completo para problemas con ev_user

echo ========================================================================
echo           DIAGNOSTICO COMPLETO: ev_user
echo ========================================================================
echo.

REM Verificar que el contenedor está corriendo
docker ps --filter "name=mariadb" --format "{{.Names}}" | findstr /C:"mariadb" >nul
if %errorlevel% neq 0 (
    echo [ERROR] El contenedor mariadb no esta corriendo.
    echo Por favor, ejecuta primero: docker-compose up -d mariadb
    pause
    exit /b 1
)

echo [1/6] Verificando contenedor MariaDB...
docker ps --filter "name=mariadb" --format "table {{.Names}}\t{{.Status}}"
echo.

echo [2/6] Verificando usuarios ev_user existentes...
docker exec mariadb mysql -u root -proot -e "SELECT User, Host, plugin, authentication_string FROM mysql.user WHERE User = 'ev_user';"
echo.

echo [3/6] Verificando permisos de ev_user@localhost...
docker exec mariadb mysql -u root -proot -e "SHOW GRANTS FOR 'ev_user'@'localhost';"
echo.

echo [4/6] Verificando permisos de ev_user@%...
docker exec mariadb mysql -u root -proot -e "SHOW GRANTS FOR 'ev_user'@'%%';"
echo.

echo [5/6] Probando conexion desde dentro del contenedor (localhost)...
docker exec mariadb mysql -u ev_user -pev_user_pass -h localhost evcharging -e "SELECT 'Conexion localhost OK' AS resultado, USER() AS usuario, DATABASE() AS bd;" 2>&1
if %errorlevel% equ 0 (
    echo [OK] Conexion desde localhost funciona!
) else (
    echo [ERROR] No se pudo conectar desde localhost
)
echo.

echo [6/6] Probando conexion desde dentro del contenedor (127.0.0.1)...
docker exec mariadb mysql -u ev_user -pev_user_pass -h 127.0.0.1 evcharging -e "SELECT 'Conexion 127.0.0.1 OK' AS resultado, USER() AS usuario, DATABASE() AS bd;" 2>&1
if %errorlevel% equ 0 (
    echo [OK] Conexion desde 127.0.0.1 funciona!
) else (
    echo [ERROR] No se pudo conectar desde 127.0.0.1
)
echo.

echo ========================================================================
echo           VERIFICANDO BASE DE DATOS
echo ========================================================================
echo.
docker exec mariadb mysql -u root -proot -e "SHOW DATABASES LIKE 'evcharging';"
echo.
docker exec mariadb mysql -u root -proot -e "SELECT COUNT(*) AS num_tablas FROM information_schema.tables WHERE table_schema = 'evcharging';"
echo.

echo ========================================================================
echo           DIAGNOSTICO COMPLETADO
echo ========================================================================
echo.
pause



