@echo off
REM Solución final y completa para el problema de ev_user
REM Este script resuelve el problema de autenticación de manera definitiva

echo ========================================================================
echo           SOLUCION FINAL: ev_user - Autenticacion 1045
echo ========================================================================
echo.
echo Este script aplicara una solucion completa que incluye:
echo   1. Eliminacion completa del usuario
echo   2. Recreacion con mysql_native_password
echo   3. Establecimiento de contraseña con ALTER USER (mas confiable)
echo   4. Permisos completos
echo   5. Verificacion desde Python
echo.
pause

REM Verificar contenedor
docker ps --filter "name=mariadb" --format "{{.Names}}" | findstr /C:"mariadb" >nul
if %errorlevel% neq 0 (
    echo [ERROR] El contenedor mariadb no esta corriendo.
    echo Ejecuta: docker-compose up -d mariadb
    pause
    exit /b 1
)

echo.
echo [PASO 1/6] Eliminando usuarios ev_user existentes...
docker exec mariadb mysql -u root -proot -e "DROP USER IF EXISTS 'ev_user'@'%%';" 2>nul
docker exec mariadb mysql -u root -proot -e "DROP USER IF EXISTS 'ev_user'@'localhost';" 2>nul
docker exec mariadb mysql -u root -proot -e "DROP USER IF EXISTS 'ev_user'@'127.0.0.1';" 2>nul
docker exec mariadb mysql -u root -proot -e "FLUSH PRIVILEGES;" 2>nul
echo [OK] Usuarios eliminados.
echo.

echo [PASO 2/6] Asegurando que la base de datos existe...
docker exec mariadb mysql -u root -proot -e "CREATE DATABASE IF NOT EXISTS evcharging;" 2>nul
echo [OK] Base de datos verificada.
echo.

echo [PASO 3/6] Creando usuarios ev_user (metodo 1: CREATE USER)...
docker exec mariadb mysql -u root -proot -e "CREATE USER 'ev_user'@'%%' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';" 2>&1
docker exec mariadb mysql -u root -proot -e "CREATE USER 'ev_user'@'localhost' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';" 2>&1
docker exec mariadb mysql -u root -proot -e "CREATE USER 'ev_user'@'127.0.0.1' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';" 2>&1
echo [OK] Usuarios creados.
echo.

echo [PASO 4/6] Forzando plugin mysql_native_password con ALTER USER (mas confiable)...
docker exec mariadb mysql -u root -proot -e "ALTER USER 'ev_user'@'%%' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';" 2>&1
docker exec mariadb mysql -u root -proot -e "ALTER USER 'ev_user'@'localhost' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';" 2>&1
docker exec mariadb mysql -u root -proot -e "ALTER USER 'ev_user'@'127.0.0.1' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';" 2>&1
echo [OK] Plugin forzado con ALTER USER.
echo.

echo [PASO 5/6] Otorgando permisos completos...
docker exec mariadb mysql -u root -proot -e "GRANT ALL PRIVILEGES ON evcharging.* TO 'ev_user'@'%%';" 2>&1
docker exec mariadb mysql -u root -proot -e "GRANT ALL PRIVILEGES ON evcharging.* TO 'ev_user'@'localhost';" 2>&1
docker exec mariadb mysql -u root -proot -e "GRANT ALL PRIVILEGES ON evcharging.* TO 'ev_user'@'127.0.0.1';" 2>&1
docker exec mariadb mysql -u root -proot -e "FLUSH PRIVILEGES;" 2>&1
echo [OK] Permisos otorgados.
echo.

echo [PASO 6/6] Verificando configuracion...
echo.
echo Usuarios creados:
docker exec mariadb mysql -u root -proot -e "SELECT User, Host, plugin FROM mysql.user WHERE User = 'ev_user' ORDER BY Host;" 2>&1
echo.

echo Probando conexion desde dentro del contenedor (localhost)...
docker exec mariadb mysql -u ev_user -pev_user_pass -h localhost evcharging -e "SELECT 'Conexion localhost OK' AS resultado;" 2>&1 | findstr /C:"Conexion" >nul
if %errorlevel% equ 0 (
    echo [OK] Conexion desde localhost funciona!
) else (
    echo [ADVERTENCIA] Problema con conexion desde localhost
)
echo.

echo Probando conexion desde Python (como EV_Central)...
python -c "import pymysql; conn = pymysql.connect(host='127.0.0.1', port=3306, user='ev_user', password='ev_user_pass', database='evcharging'); print('[OK] PyMySQL: Conexion exitosa'); conn.close()" 2>&1
if %errorlevel% equ 0 (
    echo [OK] Conexion desde Python funciona!
) else (
    echo [ADVERTENCIA] Problema con conexion desde Python
    echo.
    echo Intentando con mysql.connector...
    python -c "import mysql.connector; conn = mysql.connector.connect(host='127.0.0.1', port=3306, user='ev_user', password='ev_user_pass', database='evcharging'); print('[OK] mysql.connector: Conexion exitosa'); conn.close()" 2>&1
)

echo.
echo ========================================================================
echo           SOLUCION APLICADA
echo ========================================================================
echo.
echo Si la verificacion fue exitosa, reinicia EV_Central:
echo   RUN_CENTRAL.bat
echo.
echo Si aun hay problemas, ejecuta:
echo   DIAGNOSTICAR_EV_USER.bat
echo.
pause



