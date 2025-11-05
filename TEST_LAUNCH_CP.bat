@echo off
setlocal EnableDelayedExpansion

REM Script de prueba para lanzar un solo CP
echo ============================================================
echo TEST - LANZAR UN CP
echo ============================================================
echo.

set CENTRAL_IP=192.168.1.43
set BASE_PORT=5000
set KAFKA_SERVER=!CENTRAL_IP!:9092
set CP_NUM=1

REM Formatear ID
if %CP_NUM% LSS 10 (
    set CP_ID=CP_00%CP_NUM%
) else (
    set CP_ID=CP_%CP_NUM%
)

set /a ENGINE_PORT=%BASE_PORT%+%CP_NUM%

echo Variables configuradas:
echo   CP_ID: !CP_ID!
echo   ENGINE_PORT: !ENGINE_PORT!
echo   KAFKA_SERVER: !KAFKA_SERVER!
echo   CENTRAL_IP: !CENTRAL_IP!
echo.

REM Construir comandos
set "ENGINE_CMD=docker run --rm --network host --name engine_!CP_ID! -e ENGINE_PORT=!ENGINE_PORT! -e CP_ID=!CP_ID! -e KAFKA_SERVER=!KAFKA_SERVER! ev_engine:local"
set "MONITOR_CMD=docker run --rm --network host --name monitor_!CP_ID! -e CP_ID=!CP_ID! -e CENTRAL_IP=!CENTRAL_IP! -e CENTRAL_PORT=5000 -e ENGINE_IP=localhost -e ENGINE_PORT=!ENGINE_PORT! ev_monitor:local"

echo Comandos construidos:
echo.
echo ENGINE_CMD:
echo   !ENGINE_CMD!
echo.
echo MONITOR_CMD:
echo   !MONITOR_CMD!
echo.

REM Construir comando PowerShell para Engine
set "PS_ENGINE_CMD=Write-Host 'Iniciando Engine (!CP_ID!) en puerto !ENGINE_PORT!...' -ForegroundColor Cyan; Write-Host ''; !ENGINE_CMD!"

echo Comando PowerShell Engine:
echo   !PS_ENGINE_CMD!
echo.

echo Presiona cualquier tecla para lanzar Engine...
pause >nul

echo.
echo Lanzando Engine en nueva ventana PowerShell...
start "Engine_!CP_ID!" powershell -NoExit -Command "!PS_ENGINE_CMD!"

echo.
echo Ventana PowerShell abierta. Verifica que se ejecute correctamente.
echo.
echo Esperando 5 segundos...
timeout /t 5 /nobreak

REM Construir comando PowerShell para Monitor
set "PS_MONITOR_CMD=Write-Host 'Iniciando Monitor (!CP_ID!)...' -ForegroundColor Cyan; Write-Host ''; !MONITOR_CMD!"

echo.
echo Presiona cualquier tecla para lanzar Monitor...
pause >nul

echo.
echo Lanzando Monitor en nueva ventana PowerShell...
start "Monitor_!CP_ID!" powershell -NoExit -Command "!PS_MONITOR_CMD!"

echo.
echo Ventana PowerShell abierta. Verifica que se ejecute correctamente.
echo.
echo Presiona cualquier tecla para salir...
pause

