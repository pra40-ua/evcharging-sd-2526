@echo off
REM Script para verificar y configurar MySQL 5.7
REM MySQL 5.7 se configura automáticamente al iniciar, este script solo verifica

echo ============================================================
echo   VERIFICANDO MYSQL 5.7
echo ============================================================
echo.

echo Esperando a que MySQL esté listo...
timeout /t 3 /nobreak >nul

docker exec mysql mysqladmin ping -h localhost -uroot -proot --silent 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] MySQL no está respondiendo
    echo Verifica que el contenedor esté corriendo: docker ps
    pause
    exit /b 1
)

echo [OK] MySQL 5.7 está listo
echo.

echo Verificando configuración...
docker exec mysql mysql -uroot -proot -e "SELECT User, Host FROM mysql.user WHERE User='root';" 2>nul
echo.
docker exec mysql mysql -uroot -proot evcharging -e "SHOW TABLES;" 2>nul
echo.

echo [OK] MySQL 5.7 está configurado y listo para usar
echo.
pause
