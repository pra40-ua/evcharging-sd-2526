@echo off
REM ============================================================
REM  SCRIPT DE EJECUCION PARA PC_B CON DOCKER
REM  
REM  Este script ejecuta los componentes del sistema usando Docker:
REM  - Construye las imagenes Docker (Engine, Monitor, Driver)
REM  - Abre terminal para Engine
REM  - Abre terminal para Driver
REM  - Abre terminal para Monitor
REM  
REM ============================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo    PC_B - EJECUCION CON DOCKER
echo ============================================================
echo.

REM ============================================================
REM  PASO 1: CONSTRUIR IMAGENES
REM ============================================================
echo ============================================================
echo [1/4] CONSTRUYENDO IMAGENES DOCKER
echo ============================================================
echo.

echo Construyendo imagen ev_engine:local...
docker build -t ev_engine:local -f ev_cp_engine/Dockerfile .
if %errorlevel% neq 0 (
    echo [ERROR] Fallo al construir imagen ev_engine
    pause
    exit /b 1
)

echo.
echo Construyendo imagen ev_monitor:local...
docker build -t ev_monitor:local -f ev_cp_monitor/Dockerfile .
if %errorlevel% neq 0 (
    echo [ERROR] Fallo al construir imagen ev_monitor
    pause
    exit /b 1
)

echo.
echo Construyendo imagen ev_driver:local...
docker build -t ev_driver:local -f ev_driver/Dockerfile .
if %errorlevel% neq 0 (
    echo [ERROR] Fallo al construir imagen ev_driver
    pause
    exit /b 1
)

echo.
echo [OK] Imagenes construidas exitosamente
echo.
timeout /t 2 /nobreak >nul

REM ============================================================
REM  PASO 2: LANZAR ENGINE EN TERMINAL SEPARADA
REM ============================================================
echo ============================================================
echo [2/4] LANZANDO ENGINE
echo ============================================================
echo.

start "Engine-PC_B" powershell -ExecutionPolicy Bypass -NoExit -Command "docker run --rm -p 5001:5001 --name engine -e ENGINE_PORT=5001 -e CP_ID=CP_001 -e KAFKA_SERVER='192.168.1.43:9092' ev_engine:local"

echo [OK] Engine iniciado en ventana separada
echo.
timeout /t 3 /nobreak >nul

REM ============================================================
REM  PASO 3: LANZAR DRIVER EN TERMINAL SEPARADA
REM ============================================================
echo ============================================================
echo [3/4] LANZANDO DRIVER
echo ============================================================
echo.

start "Driver-PC_B" powershell -ExecutionPolicy Bypass -NoExit -Command "docker run --rm --name driver -e KAFKA_BROKER='192.168.1.43:9092' -e DRIVER_ID=DRIVER_456 -e CP_ID=CP_001 -e MAT=ABC-1234 -e KW=1.0 -e LISTEN=true ev_driver:local"

echo [OK] Driver iniciado en ventana separada
echo.
timeout /t 3 /nobreak >nul

REM ============================================================
REM  PASO 4: LANZAR MONITOR EN TERMINAL SEPARADA
REM ============================================================
echo ============================================================
echo [4/4] LANZANDO MONITOR
echo ============================================================
echo.

start "Monitor-PC_B" powershell -ExecutionPolicy Bypass -NoExit -Command "docker run --rm --name monitor -e CP_ID=CP_001 -e CENTRAL_IP=192.168.1.43 -e CENTRAL_PORT=5000 -e ENGINE_IP=host.docker.internal -e ENGINE_PORT=5001 ev_monitor:local"

echo [OK] Monitor iniciado en ventana separada
echo.

REM ============================================================
REM  RESUMEN FINAL
REM ============================================================
echo.
echo ============================================================
echo      SISTEMA PC_B DOCKER INICIADO CORRECTAMENTE
echo ============================================================
echo.
echo Contenedores ejecutandose:
echo   - Engine:  CP_001 en puerto 5001
echo   - Driver:  DRIVER_456 (MAT: ABC-1234)
echo   - Monitor: CP_001
echo.
echo Ventanas abiertas (PowerShell):
echo   - Engine
echo   - Driver
echo   - Monitor
echo.
echo Para DETENER:
echo   - Presiona Ctrl+C en cada ventana de PowerShell
echo   - O ejecuta: docker stop engine driver monitor
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
echo (Los contenedores seguiran ejecutandose en sus ventanas)
echo.
pause

exit /b 0

