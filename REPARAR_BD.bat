@echo off
REM ========================================================================
REM  SCRIPT PARA REPARAR LA BASE DE DATOS
REM ========================================================================
REM  Este script crea las tablas faltantes en MySQL
REM ========================================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ========================================================================
echo   REPARANDO BASE DE DATOS - Creando tablas faltantes
echo ========================================================================
echo.

REM Verificar que Docker está corriendo
docker ps >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker no esta corriendo.
    echo.
    echo Por favor, inicia Docker Desktop y ejecuta este script nuevamente.
    pause
    exit /b 1
)

REM Verificar que el contenedor MySQL existe
docker ps -a | findstr mysql >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] El contenedor MySQL no existe.
    echo.
    echo Debes ejecutar primero PC_A_RUN.bat para crear los contenedores.
    pause
    exit /b 1
)

REM Verificar que MySQL está corriendo
docker ps | findstr mysql >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] El contenedor MySQL existe pero no esta corriendo.
    echo.
    echo Ejecuta: docker start mysql
    pause
    exit /b 1
)

echo [1/2] Verificando conexion a MySQL...
echo.

docker exec mysql mysqladmin ping -h localhost -uroot -proot >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] MySQL no responde.
    echo Esperando 5 segundos...
    timeout /t 5 /nobreak >nul
    
    docker exec mysql mysqladmin ping -h localhost -uroot -proot >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] MySQL sigue sin responder.
        pause
        exit /b 1
    )
)

echo [OK] MySQL esta activo y respondiendo
echo.

echo [2/2] Creando tablas faltantes...
echo.

REM Crear tabla cp_encryption_keys
echo - Creando tabla cp_encryption_keys...
docker exec mysql mysql -u root -proot evcharging -e "CREATE TABLE IF NOT EXISTS cp_encryption_keys (id INT AUTO_INCREMENT PRIMARY KEY, cp_id VARCHAR(50) UNIQUE NOT NULL, encryption_key VARCHAR(255) NOT NULL, fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP, fecha_ultima_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, activo BOOLEAN DEFAULT TRUE, INDEX idx_cp_id (cp_id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;" >nul 2>&1

if %errorlevel% equ 0 (
    echo   [OK] Tabla cp_encryption_keys creada/verificada
) else (
    echo   [ERROR] No se pudo crear cp_encryption_keys
)

REM Crear tabla audit_log
echo - Creando tabla audit_log...
docker exec mysql mysql -u root -proot evcharging -e "CREATE TABLE IF NOT EXISTS audit_log (id INT AUTO_INCREMENT PRIMARY KEY, fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP, origen_ip VARCHAR(45), cp_id VARCHAR(50), accion VARCHAR(100) NOT NULL, descripcion TEXT, resultado VARCHAR(50), INDEX idx_fecha_hora (fecha_hora), INDEX idx_cp_id (cp_id), INDEX idx_accion (accion)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;" >nul 2>&1

if %errorlevel% equ 0 (
    echo   [OK] Tabla audit_log creada/verificada
) else (
    echo   [ERROR] No se pudo crear audit_log
)

REM Crear tabla weather_alerts
echo - Creando tabla weather_alerts...
docker exec mysql mysql -u root -proot evcharging -e "CREATE TABLE IF NOT EXISTS weather_alerts (id INT AUTO_INCREMENT PRIMARY KEY, cp_id VARCHAR(50) NOT NULL, temperatura DECIMAL(5,2), alerta_activa BOOLEAN DEFAULT FALSE, fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP, INDEX idx_cp_id (cp_id), INDEX idx_alerta_activa (alerta_activa)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;" >nul 2>&1

if %errorlevel% equ 0 (
    echo   [OK] Tabla weather_alerts creada/verificada
) else (
    echo   [ERROR] No se pudo crear weather_alerts
)

echo.
echo ========================================================================
echo   VERIFICACION DE TABLAS
echo ========================================================================
echo.

REM Mostrar todas las tablas
echo Tablas en la base de datos evcharging:
echo.
docker exec mysql mysql -u root -proot evcharging -e "SHOW TABLES;"

echo.
echo ========================================================================
echo   REPARACION COMPLETADA
echo ========================================================================
echo.
echo Las tablas han sido creadas/verificadas correctamente.
echo.
echo SIGUIENTE PASO:
echo   - Si Central ya esta corriendo, reinicialo para que use las tablas
echo   - Si no esta corriendo, ejecuta PC_A_RUN.bat
echo.
pause

