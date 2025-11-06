@echo off
setlocal EnableDelayedExpansion

REM Cambiar al directorio del script
cd /d "%~dp0"

REM ============================================================
REM  CONFIGURAR ARCHIVO DE LOG
REM ============================================================
set LOG_DIR=logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM Crear nombre de archivo con timestamp
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value 2^>nul') do set datetime=%%I
if not defined datetime set datetime=00000000_000000
set TIMESTAMP=%datetime:~0,8%_%datetime:~8,6%
set LOG_FILE=%LOG_DIR%\PC_C_RUN_%TIMESTAMP%.log

REM Iniciar log
echo ============================================================ > "%LOG_FILE%"
echo  LOG DE EJECUCION - PC_C_RUN.bat >> "%LOG_FILE%"
echo  Fecha/Hora: %date% %time% >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

REM Verificar que Docker este disponible
docker --version >> "%LOG_FILE%" 2>&1
if !errorlevel! neq 0 (
    echo.
    echo [ERROR] Docker no esta instalado o no esta en el PATH
    echo.
    pause
    exit /b 1
)

REM ============================================================
REM  PANTALLA PRINCIPAL
REM ============================================================
echo.
echo ============================================================
echo    PC_C - EJECUCION DE DRIVERS
echo ============================================================
echo.
echo [LOG] Archivo de log: %LOG_FILE%
echo.

REM Detectar IP de la Central
if exist central_ip.txt (
    set /p CENTRAL_IP=<central_ip.txt
    echo Central IP detectada: !CENTRAL_IP!
) else (
    set CENTRAL_IP=192.168.1.43
    echo No se encontro central_ip.txt. Usando IP por defecto: !CENTRAL_IP!
    echo [ADVERTENCIA] Ejecuta PC_C_INSTALL.bat primero para configurar la IP.
)
echo.

REM ============================================================
REM  CONFIGURACION DE DRIVERS
REM ============================================================
echo ============================================================
echo    CONFIGURACION DE DRIVERS
echo ============================================================
echo.

echo Cuantos Drivers deseas lanzar? (1-5)
set /p NUM_DRIVERS="Numero de Drivers: "

echo [INPUT] Usuario ingreso: NUM_DRIVERS=!NUM_DRIVERS! >> "%LOG_FILE%"

REM Validar entrada
if "%NUM_DRIVERS%"=="" set NUM_DRIVERS=1
if !NUM_DRIVERS! LSS 1 set NUM_DRIVERS=1
if !NUM_DRIVERS! GTR 5 set NUM_DRIVERS=5

echo [VALIDADO] NUM_DRIVERS final: !NUM_DRIVERS! >> "%LOG_FILE%"

echo.
echo Cuantos Charging Points estan disponibles? (1-10)
echo (Debe coincidir con el numero de CPs ejecutandose en PC_B)
set /p NUM_CPS_DISPONIBLES="Numero de CPs disponibles: "

echo [INPUT] Usuario ingreso: NUM_CPS_DISPONIBLES=!NUM_CPS_DISPONIBLES! >> "%LOG_FILE%"

REM Validar entrada
if "%NUM_CPS_DISPONIBLES%"=="" set NUM_CPS_DISPONIBLES=5
if !NUM_CPS_DISPONIBLES! LSS 1 set NUM_CPS_DISPONIBLES=1
if !NUM_CPS_DISPONIBLES! GTR 10 set NUM_CPS_DISPONIBLES=10

echo [VALIDADO] NUM_CPS_DISPONIBLES final: !NUM_CPS_DISPONIBLES! >> "%LOG_FILE%"

echo.
echo Se lanzaran !NUM_DRIVERS! Driver(s) para !NUM_CPS_DISPONIBLES! CP(s) disponibles
echo Los drivers se asignaran aleatoriamente a los CPs
echo.
timeout /t 2 /nobreak >nul

REM CONSTRUIR IMAGEN
echo ============================================================
echo [1/3] CONSTRUYENDO IMAGEN DOCKER
echo ============================================================
echo.

echo [BUILD] Iniciando construccion de imagen ev_driver >> "%LOG_FILE%"
echo [BUILD] Fecha/Hora: %date% %time% >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

echo Construyendo imagen ev_driver:local...
echo [BUILD] Ejecutando: docker build -t ev_driver:local -f ev_driver/Dockerfile . >> "%LOG_FILE%"
echo [BUILD] ---- INICIO OUTPUT DOCKER BUILD DRIVER ---- >> "%LOG_FILE%"
docker build -t ev_driver:local -f ev_driver/Dockerfile . >> "%LOG_FILE%" 2>&1
set BUILD_RESULT=!errorlevel!
echo [BUILD] ---- FIN OUTPUT DOCKER BUILD DRIVER ---- >> "%LOG_FILE%"
echo [BUILD] Resultado (errorlevel): !BUILD_RESULT! >> "%LOG_FILE%"
if !BUILD_RESULT! neq 0 (
    echo [ERROR] Fallo al construir imagen ev_driver
    echo [BUILD ERROR] Construccion de ev_driver fallo con errorlevel: !BUILD_RESULT! >> "%LOG_FILE%"
    echo Revisa el archivo de log: %LOG_FILE%
    pause
    exit /b 1
)
echo [OK] Imagen ev_driver construida
echo [BUILD OK] ev_driver construido exitosamente >> "%LOG_FILE%"
echo.

timeout /t 2 /nobreak >nul

REM DETECTAR DRIVERS EXISTENTES
echo ============================================================
echo [2/3] DETECTANDO DRIVERS EXISTENTES
echo ============================================================
echo.

echo [DEBUG] Ejecutando: docker ps -q --filter "label=component=driver" >> "%LOG_FILE%"

set DRIVER_OFFSET=0
for /f %%i in ('docker ps -q --filter "label=component=driver" 2^>nul ^| find /c /v ""') do set DRIVER_OFFSET=%%i

echo [DEBUG] DRIVER_OFFSET detectado: !DRIVER_OFFSET! >> "%LOG_FILE%"
echo [LOG] Drivers existentes: !DRIVER_OFFSET! >> "%LOG_FILE%"

echo Drivers existentes: !DRIVER_OFFSET!
echo Comenzando lanzamiento...
echo.
timeout /t 2 /nobreak >nul

REM LANZAR DRIVERS
echo ============================================================
echo [3/3] LANZANDO DRIVERS
echo ============================================================
echo.

set KAFKA_SERVER=!CENTRAL_IP!:9092

echo. >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"
echo [MAIN] INICIANDO LANZAMIENTO DE !NUM_DRIVERS! DRIVERS >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"
echo [DEBUG] KAFKA_SERVER=!KAFKA_SERVER! >> "%LOG_FILE%"
echo [DEBUG] DRIVER_OFFSET=!DRIVER_OFFSET! >> "%LOG_FILE%"
echo [DEBUG] NUM_DRIVERS=!NUM_DRIVERS! >> "%LOG_FILE%"
echo [DEBUG] NUM_CPS_DISPONIBLES=!NUM_CPS_DISPONIBLES! >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

for /L %%i in (1,1,!NUM_DRIVERS!) do (
    set /a DRIVER_NUM=!DRIVER_OFFSET!+%%i
    echo. >> "%LOG_FILE%"
    echo [MAIN] ================================================ >> "%LOG_FILE%"
    echo [MAIN] Iteracion %%i de !NUM_DRIVERS! >> "%LOG_FILE%"
    echo [MAIN] DRIVER_NUM calculado: !DRIVER_NUM! >> "%LOG_FILE%"
    echo [MAIN] ================================================ >> "%LOG_FILE%"
    echo [DEBUG] A punto de llamar a LANZAR_DRIVER con DRIVER_NUM=!DRIVER_NUM! >> "%LOG_FILE%"
    
    call :LANZAR_DRIVER !DRIVER_NUM! !NUM_CPS_DISPONIBLES!
    
    echo [DEBUG] Retorno de LANZAR_DRIVER completado >> "%LOG_FILE%"
    echo [MAIN] Esperando 1 segundo antes del siguiente driver... >> "%LOG_FILE%"
    timeout /t 1 /nobreak >nul
)

echo [DEBUG] Bucle FOR completado >> "%LOG_FILE%"

echo.
echo ============================================================
echo      !NUM_DRIVERS! DRIVER(S) INICIADO(S) CORRECTAMENTE
echo ============================================================
echo.
echo Ventanas abiertas (PowerShell): !NUM_DRIVERS! Drivers
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
REM  FUNCION PARA LANZAR UN DRIVER
REM ============================================================
:LANZAR_DRIVER
setlocal EnableDelayedExpansion
set DRIVER_NUM=%1
set NUM_CPS_TOTAL=%2

echo. >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"
echo [FUNCION] LANZAR_DRIVER INICIADA >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"
echo [DEBUG] LANZAR_DRIVER llamado con DRIVER_NUM=%1, NUM_CPS_TOTAL=%2 >> "%LOG_FILE%"

REM Formatear ID con padding (DRIVER_001, DRIVER_002, etc.)
if %DRIVER_NUM% LSS 10 (
    set DRIVER_ID=DRIVER_00%DRIVER_NUM%
) else if %DRIVER_NUM% LSS 100 (
    set DRIVER_ID=DRIVER_0%DRIVER_NUM%
) else (
    set DRIVER_ID=DRIVER_%DRIVER_NUM%
)

REM Asignar CP aleatorio entre 1 y NUM_CPS_TOTAL
set /a RANDOM_CP=%RANDOM% %% %NUM_CPS_TOTAL% + 1
if %RANDOM_CP% LSS 10 (
    set CP_ID=CP_00%RANDOM_CP%
) else if %RANDOM_CP% LSS 100 (
    set CP_ID=CP_0%RANDOM_CP%
) else (
    set CP_ID=CP_%RANDOM_CP%
)

REM kW aleatorios entre 10 y 50
set /a RANDOM_KW=%RANDOM% %% 41 + 10

REM Matricula aleatoria
set /a MAT_NUM=%RANDOM% %% 9000 + 1000
set MAT=%MAT_NUM%-ABC

echo [DEBUG] DRIVER_ID: !DRIVER_ID! >> "%LOG_FILE%"
echo [DEBUG] CP_ID asignado: !CP_ID! >> "%LOG_FILE%"
echo [DEBUG] RANDOM_KW: !RANDOM_KW! >> "%LOG_FILE%"
echo [DEBUG] MAT: !MAT! >> "%LOG_FILE%"

REM Construir comando PowerShell completo
set "PS_DRIVER_CMD=Write-Host 'Iniciando Driver (!DRIVER_ID!) -> !CP_ID! (!RANDOM_KW! kWh)...' -ForegroundColor Cyan; Write-Host ''; docker run --rm --name driver_!DRIVER_ID! --label project=evcharging-pc-c --label component=driver --label driver_id=!DRIVER_ID! -e KAFKA_BROKER=!KAFKA_SERVER! -e DRIVER_ID=!DRIVER_ID! -e CP_ID=!CP_ID! -e MAT=!MAT! -e KW=!RANDOM_KW! -e LISTEN=true ev_driver:local"

echo [DEBUG] ---- COMANDO POWERSHELL DRIVER ---- >> "%LOG_FILE%"
echo !PS_DRIVER_CMD! >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

REM Lanzar Driver en terminal PowerShell separada
echo [DEBUG] Ejecutando START PowerShell para Driver... >> "%LOG_FILE%"
start "Driver_!DRIVER_ID!" powershell -NoExit -Command "!PS_DRIVER_CMD!"
echo [DEBUG] START ejecutado para Driver (errorlevel: !errorlevel!) >> "%LOG_FILE%"

echo [DEBUG] !DRIVER_ID! completado >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"

endlocal
goto :eof

