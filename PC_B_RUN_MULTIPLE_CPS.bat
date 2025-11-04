@echo off
REM ============================================================
REM  SCRIPT DE EJECUCION PARA PC_B - MULTIPLES CPS
REM  
REM  Este script permite lanzar hasta 5 CPs simultáneamente.
REM  Cada CP tiene su propia terminal interactiva que muestra:
REM  - Estado actual del CP
REM  - Comunicaciones OCPP-like (mensajes enviados/recibidos)
REM  - Menú interactivo para simular acciones del conductor
REM  
REM ============================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo    PC_B - LANZADOR DE MULTIPLES CHARGING POINTS
echo ============================================================
echo.

REM ============================================================
REM  DETECTAR IP DE LA CENTRAL (PC_A)
REM ============================================================
if exist central_ip.txt (
    set /p CENTRAL_IP=<central_ip.txt
    echo Central IP detectada: %CENTRAL_IP%
) else (
    set CENTRAL_IP=192.168.1.43
    echo No se encontro central_ip.txt. Usando IP por defecto: %CENTRAL_IP%
)
echo.

REM ============================================================
REM  PREGUNTAR CUANTOS CPS LANZAR
REM ============================================================
echo.
echo Cuantos Charging Points deseas lanzar? (1-5)
set /p NUM_CPS="Numero de CPs: "

REM Validar entrada
if "%NUM_CPS%"=="" set NUM_CPS=1
if %NUM_CPS% LSS 1 set NUM_CPS=1
if %NUM_CPS% GTR 5 set NUM_CPS=5

echo.
echo Se lanzaran %NUM_CPS% Charging Point(s)
echo.
timeout /t 2 /nobreak >nul

REM ============================================================
REM  PASO 1: CONSTRUIR IMAGENES DOCKER
REM ============================================================
echo ============================================================
echo [1/2] CONSTRUYENDO IMAGENES DOCKER
echo ============================================================
echo.

echo Construyendo imagen ev_engine:local...
docker build -t ev_engine:local -f ev_cp_engine/Dockerfile . >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Fallo al construir imagen ev_engine
    pause
    exit /b 1
)
echo [OK] Imagen ev_engine construida

echo.
echo Construyendo imagen ev_monitor:local...
docker build -t ev_monitor:local -f ev_cp_monitor/Dockerfile . >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Fallo al construir imagen ev_monitor
    pause
    exit /b 1
)
echo [OK] Imagen ev_monitor construida

echo.
echo Construyendo imagen ev_driver:local...
docker build -t ev_driver:local -f ev_driver/Dockerfile . >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Fallo al construir imagen ev_driver
    pause
    exit /b 1
)
echo [OK] Imagen ev_driver construida

echo.
timeout /t 2 /nobreak >nul

REM ============================================================
REM  PASO 2: DETECTAR CPS EXISTENTES
REM ============================================================
echo ============================================================
echo [2/3] DETECTANDO CPS EXISTENTES
echo ============================================================
echo.

REM Contar cuantos CPs (engines) ya existen
set CP_OFFSET=0
for /f %%i in ('docker ps -q --filter "label=component=engine" 2^>nul ^| find /c /v ""') do set CP_OFFSET=%%i

if %CP_OFFSET% GTR 0 (
    echo Se detectaron %CP_OFFSET% CP(s) ya en ejecucion.
    echo Los nuevos CPs comenzaran desde CP_%CP_OFFSET:~-3%
) else (
    echo No hay CPs en ejecucion. Comenzando desde CP_001
)
echo.
timeout /t 2 /nobreak >nul

REM ============================================================
REM  PASO 3: LANZAR CPS EN TERMINALES SEPARADAS
REM ============================================================
echo ============================================================
echo [3/3] LANZANDO CHARGING POINTS
echo ============================================================
echo.

REM Definir puerto base para los engines (5001, 5002, 5003, ...)
set BASE_PORT=5000

REM Lanzar cada CP en su propia terminal
for /L %%i in (1,1,%NUM_CPS%) do (
    set /a CP_NUM=%CP_OFFSET%+%%i
    call :LANZAR_CP !CP_NUM!
    timeout /t 2 /nobreak >nul
)

echo.
echo ============================================================
echo      %NUM_CPS% CHARGING POINT(S) INICIADO(S) CORRECTAMENTE
echo ============================================================
echo.
echo Ventanas abiertas (PowerShell):
for /L %%i in (1,1,%NUM_CPS%) do (
    set /a PORT=BASE_PORT+%%i
    echo   - CP_00%%i en puerto !PORT!
)
echo.
echo Para DETENER:
echo   - Presiona Ctrl+C en cada ventana de PowerShell
echo   - O ejecuta: PC_B_STOP_ALL.bat (para detener todos a la vez)
echo   - O ejecuta: docker stop $(docker ps -q --filter "label=project=evcharging-pc-b")
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
echo (Los CPs seguiran ejecutandose en sus ventanas)
echo.
pause

exit /b 0

REM ============================================================
REM  FUNCIÓN PARA LANZAR UN CP
REM ============================================================
:LANZAR_CP
setlocal EnableDelayedExpansion
set CP_NUM=%1

REM Formatear ID con padding (CP_001, CP_002, etc.)
if %CP_NUM% LSS 10 (
    set CP_ID=CP_00%CP_NUM%
) else if %CP_NUM% LSS 100 (
    set CP_ID=CP_0%CP_NUM%
) else (
    set CP_ID=CP_%CP_NUM%
)

set /a ENGINE_PORT=BASE_PORT+%CP_NUM%
set KAFKA_SERVER=%CENTRAL_IP%:9092

REM Calcular numero para display (relativo a esta ejecucion)
set /a DISPLAY_NUM=%CP_NUM%-%CP_OFFSET%
echo [!DISPLAY_NUM!/%NUM_CPS%] Lanzando %CP_ID% (Puerto %ENGINE_PORT%)...

REM Lanzar Engine en terminal separada
start "CP_%CP_ID%_Engine" powershell -ExecutionPolicy Bypass -NoExit -Command ^
"Write-Host '================================================================' -ForegroundColor Cyan; ^
Write-Host '  ENGINE - %CP_ID% (Puerto %ENGINE_PORT%)' -ForegroundColor Yellow; ^
Write-Host '================================================================' -ForegroundColor Cyan; ^
Write-Host ''; ^
docker run --rm --name engine_%CP_ID% ^
--label project=evcharging-pc-b ^
--label component=engine ^
--label cp_id=%CP_ID% ^
-p %ENGINE_PORT%:%ENGINE_PORT% ^
-e ENGINE_PORT=%ENGINE_PORT% ^
-e CP_ID=%CP_ID% ^
-e KAFKA_SERVER='%KAFKA_SERVER%' ^
ev_engine:local"

REM Esperar un poco para que el Engine esté listo
timeout /t 3 /nobreak >nul

REM Lanzar Monitor en terminal separada
start "CP_%CP_ID%_Monitor" powershell -ExecutionPolicy Bypass -NoExit -Command ^
"Write-Host '================================================================' -ForegroundColor Cyan; ^
Write-Host '  MONITOR - %CP_ID%' -ForegroundColor Green; ^
Write-Host '================================================================' -ForegroundColor Cyan; ^
Write-Host ''; ^
docker run --rm --name monitor_%CP_ID% ^
--label project=evcharging-pc-b ^
--label component=monitor ^
--label cp_id=%CP_ID% ^
-e CP_ID=%CP_ID% ^
-e CENTRAL_IP=%CENTRAL_IP% ^
-e CENTRAL_PORT=5000 ^
-e ENGINE_IP=host.docker.internal ^
-e ENGINE_PORT=%ENGINE_PORT% ^
ev_monitor:local"

echo [OK] %CP_ID% lanzado exitosamente

endlocal
goto :eof

