@echo off
setlocal ENABLEDELAYEDEXPANSION
cd /d "%~dp0"

rem ====== Parametros opcionales ======
set CP_ID=%~1
if "%CP_ID%"=="" set CP_ID=CP_001

set ENGINE_PORT=%~2
if "%ENGINE_PORT%"=="" set ENGINE_PORT=5001

set DRIVER_ID=%~3
if "%DRIVER_ID%"=="" set DRIVER_ID=DRIVER_456

set DRIVER_KW=%~4
if "%DRIVER_KW%"=="" set DRIVER_KW=25.0

set DRIVER_MAT=%~5
if "%DRIVER_MAT%"=="" set DRIVER_MAT=ABC-1234

rem ====== Cargar IP de la central (PC_A) ======
for /f "usebackq tokens=1" %%i in ("%~dp0central_ip.txt") do set CENTRAL_IP=%%i
if "%CENTRAL_IP%"=="" (
  echo ERROR: No se pudo leer central_ip.txt o esta vacio.
  exit /b 1
)

rem ====== Determinar ENGINE_IP para que el monitor alcance al engine ======
rem Por defecto usar host.docker.internal (Docker en Windows lo resuelve dentro de contenedores)
set ENGINE_IP=%~6
if "%ENGINE_IP%"=="" set ENGINE_IP=host.docker.internal

echo ================================================
echo Unificador PC_B  -  CP_ID=%CP_ID%  ENGINE_PORT=%ENGINE_PORT%
echo CENTRAL=%CENTRAL_IP%  ENGINE_IP=%ENGINE_IP%
echo DRIVER: %DRIVER_ID%  KW=%DRIVER_KW%  MAT=%DRIVER_MAT%
echo ================================================

rem ====== 1) Build de imagenes necesarias ======
echo [BUILD] Construyendo imagen ev_engine:local ...
docker build -t ev_engine:local -f ev_cp_engine/Dockerfile . || goto :fail

echo [BUILD] Construyendo imagen ev_monitor:local ...
docker build -t ev_monitor:local -f ev_cp_monitor/Dockerfile . || goto :fail

echo [BUILD] Construyendo imagen ev_driver:local ...
docker build -t ev_driver:local -f ev_driver/Dockerfile . || goto :fail

rem ====== Helper: esperar puerto TCP (usa PowerShell) ======
:wait_port
rem %1 host, %2 port, %3 etiqueta, %4 segundos time-out (opcional)
set _WAIT_HOST=%~1
set _WAIT_PORT=%~2
set _WAIT_NAME=%~3
set _WAIT_TIMEOUT=%~4
if "%_WAIT_TIMEOUT%"=="" set _WAIT_TIMEOUT=60
set /a _WAIT_ELAPSED=0
echo [WAIT] Esperando a %_WAIT_NAME% en %_WAIT_HOST%:%_WAIT_PORT% (timeout %_WAIT_TIMEOUT%s)...
:_wp_loop
powershell -NoLogo -Command "$succ=(Test-NetConnection -ComputerName '%_WAIT_HOST%' -Port %_WAIT_PORT%).TcpTestSucceeded; if($succ){exit 0}else{Start-Sleep -s 2; exit 1}"
if %ERRORLEVEL%==0 (
  echo [WAIT] %_WAIT_NAME% disponible.
) else (
  set /a _WAIT_ELAPSED+=2
  if %_WAIT_ELAPSED% GEQ %_WAIT_TIMEOUT% (
    echo [WAIT] TIMEOUT esperando %_WAIT_NAME%.
    exit /b 1
  )
  goto :_wp_loop
)
exit /b 0

rem ====== 2) Lanzar Engine (detached) ======
echo [RUN] Lanzando Engine ...
rem Si ya existiera un contenedor previo, eliminarlo
docker rm -f engine >nul 2>&1
docker run -d --rm --name engine -p %ENGINE_PORT%:%ENGINE_PORT% ^
  -e ENGINE_PORT=%ENGINE_PORT% -e CP_ID=%CP_ID% ^
  -e KAFKA_SERVER=%CENTRAL_IP%:9092 ^
  ev_engine:local || goto :fail

call :wait_port 127.0.0.1 %ENGINE_PORT% ENGINE 90 || goto :fail

rem ====== 3) Lanzar Monitor (detached) ======
echo [RUN] Lanzando Monitor ...
docker rm -f monitor >nul 2>&1
docker run -d --rm --name monitor ^
  -e CP_ID=%CP_ID% ^
  -e CENTRAL_IP=%CENTRAL_IP% -e CENTRAL_PORT=5000 ^
  -e ENGINE_IP=%ENGINE_IP% -e ENGINE_PORT=%ENGINE_PORT% ^
  ev_cp_monitor:local 2>nul
if errorlevel 1 (
  rem fallback al nombre de imagen estandar
  docker run -d --rm --name monitor ^
    -e CP_ID=%CP_ID% ^
    -e CENTRAL_IP=%CENTRAL_IP% -e CENTRAL_PORT=5000 ^
    -e ENGINE_IP=%ENGINE_IP% -e ENGINE_PORT=%ENGINE_PORT% ^
    ev_monitor:local || goto :fail
)

rem Espera corta (el monitor es TCP cliente hacia central/engine)
echo [WAIT] Esperando 5s a que el monitor se inicialice...
timeout /t 5 /nobreak >nul

rem ====== 4) Lanzar Driver (detached) ======
echo [RUN] Lanzando Driver ...
docker rm -f driver >nul 2>&1
docker run -d --rm --name driver ^
  -e KAFKA_BROKER=%CENTRAL_IP%:9092 ^
  -e DRIVER_ID=%DRIVER_ID% -e CP_ID=%CP_ID% ^
  -e MAT=%DRIVER_MAT% -e KW=%DRIVER_KW% -e LISTEN=true ^
  ev_driver:local || goto :fail

echo.
echo Todo lanzado correctamente.
echo - Engine:   http://localhost:%ENGINE_PORT% (si expone API)
echo - Monitor:  container 'monitor' en marcha
echo - Driver:   container 'driver' en marcha
echo.
echo Sugerencia: usa "docker logs -f engine|monitor|driver" para ver logs.
exit /b 0

:fail
echo ERROR durante la ejecucion.
exit /b 1


