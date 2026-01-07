@echo off
REM Script para verificar que la conexión con ev_user funciona correctamente

echo ========================================================================
echo           VERIFICAR CONEXION CON ev_user
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

echo [1/3] Verificando que MariaDB esta corriendo...
docker ps --filter "name=mariadb" --format "table {{.Names}}\t{{.Status}}"
echo.

echo [2/3] Probando conexion con ev_user...
echo.
docker exec mariadb mysql -u ev_user -pev_user_pass evcharging -e "SELECT 'Conexion exitosa!' AS resultado, DATABASE() AS base_datos, USER() AS usuario;"
if %errorlevel% equ 0 (
    echo.
    echo [OK] Conexion con ev_user funciona correctamente!
) else (
    echo.
    echo [ERROR] No se pudo conectar con ev_user.
    echo Verifica que el usuario existe y tiene los permisos correctos.
    pause
    exit /b 1
)

echo.
echo [3/3] Verificando tablas en la base de datos...
docker exec mariadb mysql -u ev_user -pev_user_pass evcharging -e "SHOW TABLES;"
if %errorlevel% equ 0 (
    echo.
    echo [OK] Acceso a tablas verificado correctamente!
) else (
    echo.
    echo [ERROR] No se pudo acceder a las tablas.
)

echo.
echo ========================================================================
echo           VERIFICACION COMPLETADA
echo ========================================================================
echo.
echo Si todo esta OK, ahora puedes:
echo   1. Reiniciar EV_Central (si esta corriendo, cerrarlo y volver a ejecutar)
echo   2. Verificar que no aparezcan errores 1045 Access denied
echo.
pause



