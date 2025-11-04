@echo off
setlocal
cd /d "%~dp0"

echo =========================================
echo   Iniciando PC_B - Charging Point
echo =========================================
echo.

REM Construir imagenes Docker
echo [1/4] Construyendo imagenes Docker...
echo.
docker build -t ev_engine:local -f ev_cp_engine/Dockerfile .
if %ERRORLEVEL% NEQ 0 (
    echo Error al construir ev_engine
    pause
    exit /b 1
)

docker build -t ev_monitor:local -f ev_cp_monitor/Dockerfile .
if %ERRORLEVEL% NEQ 0 (
    echo Error al construir ev_monitor
    pause
    exit /b 1
)

docker build -t ev_driver:local -f ev_driver/Dockerfile .
if %ERRORLEVEL% NEQ 0 (
    echo Error al construir ev_driver
    pause
    exit /b 1
)

echo.
echo Imagenes construidas correctamente.
echo.

REM Arrancar Engine en una nueva ventana
echo [2/4] Iniciando Engine en puerto 5001...
start "EV Engine CP_001" cmd /k "docker run --rm -p 5001:5001 --name engine -e ENGINE_PORT=5001 -e CP_ID=CP_001 -e KAFKA_SERVER=192.168.1.43:9092 ev_engine:local"

echo Esperando 10 segundos para que Engine este listo...
timeout /t 10 /nobreak >nul

REM Arrancar Monitor en una nueva ventana
echo [3/4] Iniciando Monitor para CP_001...
start "EV Monitor CP_001" cmd /k "docker run --rm --name monitor -e CP_ID=CP_001 -e CENTRAL_IP=192.168.1.43 -e CENTRAL_PORT=5000 -e ENGINE_IP=host.docker.internal -e ENGINE_PORT=5001 ev_monitor:local"

echo Esperando 5 segundos...
timeout /t 5 /nobreak >nul

REM Arrancar Driver en una nueva ventana
echo [4/4] Iniciando Driver DRIVER_456...
start "EV Driver DRIVER_456" cmd /k "docker run --rm --name driver -e KAFKA_BROKER=192.168.1.43:9092 -e DRIVER_ID=DRIVER_456 -e CP_ID=CP_001 -e MAT=ABC-1234 -e KW=1.0 -e LISTEN=true ev_driver:local"

echo.
echo =========================================
echo   Todos los componentes iniciados
echo =========================================
echo.
echo IP local (PC_B): 172.17.48.1
echo IP Central (PC_A): 192.168.1.43
echo Puerto Engine: 5001
echo Puerto Kafka: 9092 (en PC_A)
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
pause >nul
