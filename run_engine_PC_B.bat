@echo off
setlocal
cd /d "%~dp0"

set CP_ID=%~1
if "%CP_ID%"=="" set CP_ID=CP_001

set ENGINE_PORT=%~2
if "%ENGINE_PORT%"=="" set ENGINE_PORT=5001

for /f "usebackq tokens=1" %%i in ("%~dp0central_ip.txt") do set CENTRAL_IP=%%i
if "%CENTRAL_IP%"=="" (
  echo ERROR: No se pudo leer central_ip.txt o esta vacio.
  exit /b 1
)

echo Ejecutando Engine con CP_ID=%CP_ID%, puerto=%ENGINE_PORT%, central=%CENTRAL_IP%:9092
docker run --rm -p %ENGINE_PORT%:%ENGINE_PORT% --name engine ^
  -e ENGINE_PORT=%ENGINE_PORT% ^
  -e CP_ID=%CP_ID% ^
  -e KAFKA_SERVER=%CENTRAL_IP%:9092 ^
  ev_engine:local

exit /b %errorlevel%


