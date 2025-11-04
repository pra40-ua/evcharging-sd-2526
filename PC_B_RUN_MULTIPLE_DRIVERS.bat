@echo off
setlocal EnableDelayedExpansion
REM ============================================================
REM  SCRIPT DE EJECUCION PARA PC_B - MULTIPLES DRIVERS
REM  
REM  Este script permite lanzar hasta 5 Drivers simultáneamente.
REM  Los drivers se asignan aleatoriamente a los CPs disponibles.
REM  
REM ============================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo    PC_B - LANZADOR DE MULTIPLES DRIVERS
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
REM  PREGUNTAR CUANTOS DRIVERS LANZAR
REM ============================================================
echo.
echo Cuantos Drivers deseas lanzar? (1-5)
set /p NUM_DRIVERS="Numero de Drivers: "

REM Validar entrada
if "%NUM_DRIVERS%"=="" set NUM_DRIVERS=1
if %NUM_DRIVERS% LSS 1 set NUM_DRIVERS=1
if %NUM_DRIVERS% GTR 5 set NUM_DRIVERS=5

echo.
echo Cuantos Charging Points estan disponibles? (1-10)
set /p NUM_CPS="Numero de CPs disponibles: "

REM Validar entrada
if "%NUM_CPS%"=="" set NUM_CPS=5
if %NUM_CPS% LSS 1 set NUM_CPS=1
if %NUM_CPS% GTR 10 set NUM_CPS=10

echo.
echo Se lanzaran %NUM_DRIVERS% Driver(s) para %NUM_CPS% CP(s) disponibles
echo Los drivers se asignaran aleatoriamente a los CPs
echo.
timeout /t 2 /nobreak >nul

REM ============================================================
REM  PASO 1: CONSTRUIR IMAGEN DOCKER DEL DRIVER
REM ============================================================
echo ============================================================
echo [1/3] CONSTRUYENDO IMAGEN DOCKER
echo ============================================================
echo.

echo Construyendo imagen ev_driver:local...
docker build -t ev_driver:local -f ev_driver/Dockerfile .
if !errorlevel! neq 0 (
    echo.
    echo [ERROR] Fallo al construir imagen ev_driver
    echo.
    pause
    exit /b 1
)
echo [OK] Imagen ev_driver construida

echo.
timeout /t 2 /nobreak >nul

REM ============================================================
REM  PASO 2: DETECTAR DRIVERS EXISTENTES
REM ============================================================
echo ============================================================
echo [2/3] DETECTANDO DRIVERS EXISTENTES
echo ============================================================
echo.

REM Contar cuantos drivers ya existen
set DRIVER_OFFSET=0
for /f %%i in ('docker ps -q --filter "label=component=driver" 2^>nul ^| find /c /v ""') do set DRIVER_OFFSET=%%i

if %DRIVER_OFFSET% GTR 0 (
    echo Se detectaron %DRIVER_OFFSET% driver(s) ya en ejecucion.
    echo Los nuevos drivers comenzaran desde DRIVER_%DRIVER_OFFSET:~-3%
) else (
    echo No hay drivers en ejecucion. Comenzando desde DRIVER_001
)
echo.
timeout /t 2 /nobreak >nul

REM ============================================================
REM  PASO 3: LANZAR DRIVERS EN TERMINALES SEPARADAS
REM ============================================================
echo ============================================================
echo [3/3] LANZANDO DRIVERS
echo ============================================================
echo.

set KAFKA_SERVER=%CENTRAL_IP%:9092

REM Lanzar cada Driver en su propia terminal
for /L %%i in (1,1,%NUM_DRIVERS%) do (
    set /a DRIVER_NUM=%DRIVER_OFFSET%+%%i
    call :LANZAR_DRIVER !DRIVER_NUM! %%i
    timeout /t 1 /nobreak >nul
)

echo.
echo ============================================================
echo      %NUM_DRIVERS% DRIVER(S) INICIADO(S) CORRECTAMENTE
echo ============================================================
echo.
echo Ventanas abiertas (PowerShell):
set /a FIRST_DRIVER=%DRIVER_OFFSET%+1
set /a LAST_DRIVER=%DRIVER_OFFSET%+%NUM_DRIVERS%
for /L %%i in (%FIRST_DRIVER%,1,%LAST_DRIVER%) do (
    if %%i LSS 10 (
        echo   - DRIVER_00%%i
    ) else if %%i LSS 100 (
        echo   - DRIVER_0%%i
    ) else (
        echo   - DRIVER_%%i
    )
)
echo.
echo Los drivers se detendran automaticamente al recibir su ticket.
echo Para detener manualmente: PC_B_STOP_ALL.bat
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
echo (Los Drivers seguiran ejecutandose en sus ventanas)
echo.
pause

exit /b 0

REM ============================================================
REM  FUNCIÓN PARA LANZAR UN DRIVER
REM ============================================================
:LANZAR_DRIVER
set DRIVER_NUM=%1
set DISPLAY_NUM=%2

REM Formatear ID con padding (DRIVER_001, DRIVER_002, etc.)
if %DRIVER_NUM% LSS 10 (
    set DRIVER_ID=DRIVER_00%DRIVER_NUM%
) else if %DRIVER_NUM% LSS 100 (
    set DRIVER_ID=DRIVER_0%DRIVER_NUM%
) else (
    set DRIVER_ID=DRIVER_%DRIVER_NUM%
)

REM Asignar CP aleatorio entre 1 y NUM_CPS
set /a RANDOM_CP=%RANDOM% %% %NUM_CPS% + 1

REM Formatear CP_ID con padding
if %RANDOM_CP% LSS 10 (
    set CP_ID=CP_00%RANDOM_CP%
) else if %RANDOM_CP% LSS 100 (
    set CP_ID=CP_0%RANDOM_CP%
) else (
    set CP_ID=CP_%RANDOM_CP%
)

REM kW aleatorios entre 10 y 50
set /a RANDOM_KW=%RANDOM% %% 41 + 10

REM Matrícula aleatoria
set /a MAT_NUM=%RANDOM% %% 9000 + 1000
set MAT=%MAT_NUM%-ABC

echo [!DISPLAY_NUM!/%NUM_DRIVERS%] Lanzando !DRIVER_ID! -^> !CP_ID! (!RANDOM_KW! kWh)...

REM Lanzar Driver en terminal separada con variables expandidas
set "CMD_DRIVER=Write-Host '================================================================' -ForegroundColor Cyan; Write-Host '  DRIVER - !DRIVER_ID!' -ForegroundColor Magenta; Write-Host '  CP Solicitado: !CP_ID!' -ForegroundColor Yellow; Write-Host '  kWh Deseados: !RANDOM_KW!' -ForegroundColor Yellow; Write-Host '================================================================' -ForegroundColor Cyan; Write-Host ''; docker run --rm --name driver_!DRIVER_ID! --label project=evcharging-pc-b --label component=driver --label driver_id=!DRIVER_ID! -e KAFKA_BROKER='!KAFKA_SERVER!' -e DRIVER_ID=!DRIVER_ID! -e CP_ID=!CP_ID! -e MAT=!MAT! -e KW=!RANDOM_KW! -e LISTEN=true ev_driver:local"

start "Driver_!DRIVER_ID!" powershell -ExecutionPolicy Bypass -NoExit -Command "!CMD_DRIVER!"
echo [OK] !DRIVER_ID! lanzado exitosamente

goto :eof

