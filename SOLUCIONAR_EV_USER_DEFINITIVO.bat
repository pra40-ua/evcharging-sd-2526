@echo off
REM Script para solucionar definitivamente el problema de ev_user
REM Elimina y recrea el usuario con todas las configuraciones correctas

echo ========================================================================
echo           SOLUCION DEFINITIVA: ev_user
echo ========================================================================
echo.
echo Este script eliminara y recreara el usuario ev_user completamente.
echo.
pause

REM Verificar que el contenedor está corriendo
docker ps --filter "name=mariadb" --format "{{.Names}}" | findstr /C:"mariadb" >nul
if %errorlevel% neq 0 (
    echo [ERROR] El contenedor mariadb no esta corriendo.
    echo Por favor, ejecuta primero: docker-compose up -d mariadb
    pause
    exit /b 1
)

echo [1/5] Eliminando usuario ev_user existente...
docker exec mariadb mysql -u root -proot -e "DROP USER IF EXISTS 'ev_user'@'%%';" 2>&1
docker exec mariadb mysql -u root -proot -e "DROP USER IF EXISTS 'ev_user'@'localhost';" 2>&1
docker exec mariadb mysql -u root -proot -e "DROP USER IF EXISTS 'ev_user'@'127.0.0.1';" 2>&1
echo [OK] Usuarios eliminados.
echo.

echo [2/5] Asegurando que la base de datos evcharging existe...
docker exec mariadb mysql -u root -proot -e "CREATE DATABASE IF NOT EXISTS evcharging;" 2>&1
echo [OK] Base de datos verificada.
echo.

echo [3/5] Creando usuario ev_user con mysql_native_password...
REM Crear usuario con contraseña explícita usando IDENTIFIED BY (más compatible)
docker exec mariadb mysql -u root -proot -e "CREATE USER 'ev_user'@'%%' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';" 2>&1
docker exec mariadb mysql -u root -proot -e "CREATE USER 'ev_user'@'localhost' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';" 2>&1
docker exec mariadb mysql -u root -proot -e "CREATE USER 'ev_user'@'127.0.0.1' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';" 2>&1
echo [OK] Usuarios creados.
echo.

echo [4/5] Otorgando permisos en evcharging...
docker exec mariadb mysql -u root -proot -e "GRANT ALL PRIVILEGES ON evcharging.* TO 'ev_user'@'%%';" 2>&1
docker exec mariadb mysql -u root -proot -e "GRANT ALL PRIVILEGES ON evcharging.* TO 'ev_user'@'localhost';" 2>&1
docker exec mariadb mysql -u root -proot -e "GRANT ALL PRIVILEGES ON evcharging.* TO 'ev_user'@'127.0.0.1';" 2>&1
echo [OK] Permisos otorgados.
echo.

echo [5/5] Aplicando cambios (FLUSH PRIVILEGES)...
docker exec mariadb mysql -u root -proot -e "FLUSH PRIVILEGES;" 2>&1
echo [OK] Cambios aplicados.
echo.

echo ========================================================================
echo           VERIFICANDO CONFIGURACION
echo ========================================================================
echo.
echo Usuarios creados:
docker exec mariadb mysql -u root -proot -e "SELECT User, Host, plugin FROM mysql.user WHERE User = 'ev_user';" 2>&1
echo.

echo Probando conexion desde localhost...
docker exec mariadb mysql -u ev_user -pev_user_pass -h localhost evcharging -e "SELECT 'Conexion OK' AS resultado, USER() AS usuario;" 2>&1
if %errorlevel% equ 0 (
    echo [OK] Conexion desde localhost funciona correctamente!
) else (
    echo [ERROR] Aun hay problemas con la conexion desde localhost.
    echo.
    echo Intentando solucion alternativa...
    REM Intentar cambiar la contraseña usando ALTER USER
    docker exec mariadb mysql -u root -proot -e "ALTER USER 'ev_user'@'localhost' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';" 2>&1
    docker exec mariadb mysql -u root -proot -e "FLUSH PRIVILEGES;" 2>&1
    echo.
    echo Probando nuevamente...
    docker exec mariadb mysql -u ev_user -pev_user_pass -h localhost evcharging -e "SELECT 'Conexion OK' AS resultado;" 2>&1
)

echo.
echo ========================================================================
echo           SOLUCION APLICADA
echo ========================================================================
echo.
echo Si la conexion funciona ahora, reinicia EV_Central.
echo.
pause



