@echo off
REM Script para ejecutar EV_Central con salida de mensajes visible
REM Este script se ejecuta en su propia ventana

cd /d "%~dp0"

REM Leer IP central
set /p CENTRAL_IP=<central_ip.txt
if "%CENTRAL_IP%"=="" set CENTRAL_IP=127.0.0.1

REM Limpiar pantalla y mostrar encabezado
cls
echo.
echo ========================================================================
echo                    EV CENTRAL - MENSAJES Y TELEMETRIA
echo ========================================================================
echo.
echo  IP Central:      %CENTRAL_IP%
echo  Puerto:          5000
echo  Kafka:           %CENTRAL_IP%:9092
echo  MySQL:           127.0.0.1:3306
echo.
echo  MODO: Consola con todos los mensajes visibles en tiempo real
echo.
echo ========================================================================
echo.
echo Iniciando servidor Central...
echo.
echo ========================================================================
echo.

REM Ejecutar EV_Central en modo consola (sin TUI)
REM Nota: La API REST se inicia automáticamente en el puerto 5001
REM Configurar REGISTRY_URL con HTTPS para conectarse con EV_Registry
set REGISTRY_URL=https://127.0.0.1:8000/api
py ev_central\EV_Central.py --port 5000 --kafka %CENTRAL_IP%:9092 --db "127.0.0.1:3306:root:root:evcharging" --no-tui

echo.
echo ========================================================================
echo  EV_Central ha finalizado.
echo ========================================================================
echo.
pause

