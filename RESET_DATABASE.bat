@echo off
REM Script para eliminar y recrear la base de datos MySQL
REM Este script elimina la base de datos y el usuario, y los recrea con permisos correctos

cd /d "%~dp0"

echo ========================================================================
echo              RESET COMPLETO DE BASE DE DATOS MYSQL
echo ========================================================================
echo.
echo Este script va a:
echo   1. Eliminar la base de datos 'evcharging' si existe
echo   2. Eliminar usuarios existentes
echo   3. Crear la base de datos y usuario con permisos correctos
echo   4. Crear todas las tablas necesarias
echo.
echo ADVERTENCIA: Se perderan todos los datos existentes en la BD
echo.
pause

echo.
echo Verificando que el contenedor MySQL esté corriendo...
docker ps | findstr mysql >nul
if errorlevel 1 (
    echo ERROR: El contenedor MySQL no está corriendo.
    echo Por favor, inicia Docker Compose primero:
    echo   docker-compose up -d mysql
    pause
    exit /b 1
)

echo.
echo Ejecutando script de reset...
echo.

REM Ejecutar el script SQL de reset
Get-Content db\reset_database.sql | docker exec -i mysql mysql -u root -proot

if errorlevel 1 (
    echo.
    echo ERROR: No se pudo ejecutar el script de reset.
    echo Verifica que el contenedor MySQL esté corriendo y accesible.
    pause
    exit /b 1
)

echo.
echo ========================================================================
echo  Base de datos resetada correctamente
echo ========================================================================
echo.
echo La base de datos 'evcharging' ha sido recreada con:
echo   - Usuario: root
echo   - Contraseña: root
echo   - Permisos desde cualquier host (incluyendo Docker)
echo   - Todas las tablas necesarias creadas
echo.
pause

