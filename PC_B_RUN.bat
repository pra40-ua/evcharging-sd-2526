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
set LOG_FILE=%LOG_DIR%\PC_B_RUN_%TIMESTAMP%.log

REM Iniciar log
echo ============================================================ > "%LOG_FILE%"
echo  LOG DE EJECUCION - PC_B_RUN.bat >> "%LOG_FILE%"
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
echo    PC_B - EJECUCION CON DOCKER
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
)
echo.

REM ============================================================
REM  MENU DE SELECCION
REM ============================================================
:MENU
echo ============================================================
echo   MENU DE OPCIONES
echo ============================================================
echo.
echo Que deseas lanzar?
echo.
echo   [1] Multiples CPs (hasta 5 CPs simultaneos)
echo   [2] Multiples Drivers (hasta 5 Drivers simultaneos)
echo   [3] CLASICO: 1 CP + 1 Driver
echo   [0] SALIR
echo.
set "MODO="
set /p MODO="Selecciona opcion (1, 2, 3 o 0): "

REM Validar que se ingreso algo
if not defined MODO (
    echo.
    echo [ERROR] Debes seleccionar una opcion.
    echo.
    timeout /t 2 /nobreak >nul
    goto MENU
)

echo.

if "%MODO%"=="1" goto MULTIPLE_CPS
if "%MODO%"=="2" goto MULTIPLE_DRIVERS
if "%MODO%"=="3" goto CLASICO
if "%MODO%"=="0" goto SALIR

echo [ERROR] Opcion invalida: %MODO%
echo.
timeout /t 2 /nobreak >nul
goto MENU

:SALIR
echo.
echo Saliendo...
exit /b 0

REM ============================================================
REM  MODO 1: MULTIPLES CPS
REM ============================================================
:MULTIPLE_CPS
echo. >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"
echo [MODO] MULTIPLES CPS SELECCIONADO >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"

echo ============================================================
echo    MODO: MULTIPLES CHARGING POINTS
echo ============================================================
echo.

echo Cuantos Charging Points deseas lanzar? (1-5)
set /p NUM_CPS="Numero de CPs: "

echo [INPUT] Usuario ingreso: NUM_CPS=!NUM_CPS! >> "%LOG_FILE%"

REM Validar entrada
if "%NUM_CPS%"=="" set NUM_CPS=1
if !NUM_CPS! LSS 1 set NUM_CPS=1
if !NUM_CPS! GTR 5 set NUM_CPS=5

echo [VALIDADO] NUM_CPS final: !NUM_CPS! >> "%LOG_FILE%"

echo.
echo Se lanzaran !NUM_CPS! Charging Point(s)
echo.
timeout /t 2 /nobreak >nul

REM CONSTRUIR IMAGENES
echo ============================================================
echo [1/3] CONSTRUYENDO IMAGENES DOCKER
echo ============================================================
echo.

echo [BUILD] Iniciando construccion de imagenes >> "%LOG_FILE%"
echo [BUILD] Fecha/Hora: %date% %time% >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

echo Construyendo imagen ev_engine:local...
echo [BUILD] Ejecutando: docker build -t ev_engine:local -f ev_cp_engine/Dockerfile . >> "%LOG_FILE%"
echo [BUILD] ---- INICIO OUTPUT DOCKER BUILD ENGINE ---- >> "%LOG_FILE%"
docker build -t ev_engine:local -f ev_cp_engine/Dockerfile . >> "%LOG_FILE%" 2>&1
set BUILD_RESULT=!errorlevel!
echo [BUILD] ---- FIN OUTPUT DOCKER BUILD ENGINE ---- >> "%LOG_FILE%"
echo [BUILD] Resultado (errorlevel): !BUILD_RESULT! >> "%LOG_FILE%"
if !BUILD_RESULT! neq 0 (
    echo [ERROR] Fallo al construir imagen ev_engine
    echo [BUILD ERROR] Construccion de ev_engine fallo con errorlevel: !BUILD_RESULT! >> "%LOG_FILE%"
    echo Revisa el archivo de log: %LOG_FILE%
    pause
    exit /b 1
)
echo [OK] Imagen ev_engine construida
echo [BUILD OK] ev_engine construido exitosamente >> "%LOG_FILE%"
echo.

echo Construyendo imagen ev_monitor:local...
echo [BUILD] Ejecutando: docker build -t ev_monitor:local -f ev_cp_monitor/Dockerfile . >> "%LOG_FILE%"
echo [BUILD] ---- INICIO OUTPUT DOCKER BUILD MONITOR ---- >> "%LOG_FILE%"
docker build -t ev_monitor:local -f ev_cp_monitor/Dockerfile . >> "%LOG_FILE%" 2>&1
set BUILD_RESULT=!errorlevel!
echo [BUILD] ---- FIN OUTPUT DOCKER BUILD MONITOR ---- >> "%LOG_FILE%"
echo [BUILD] Resultado (errorlevel): !BUILD_RESULT! >> "%LOG_FILE%"
if !BUILD_RESULT! neq 0 (
    echo [ERROR] Fallo al construir imagen ev_monitor
    echo [BUILD ERROR] Construccion de ev_monitor fallo con errorlevel: !BUILD_RESULT! >> "%LOG_FILE%"
    echo Revisa el archivo de log: %LOG_FILE%
    pause
    exit /b 1
)
echo [OK] Imagen ev_monitor construida
echo [BUILD OK] ev_monitor construido exitosamente >> "%LOG_FILE%"
echo.

timeout /t 2 /nobreak >nul

REM DETECTAR CPS EXISTENTES
echo ============================================================
echo [2/3] DETECTANDO CPS EXISTENTES
echo ============================================================
echo.

echo [DEBUG] Ejecutando: docker ps -q --filter "label=component=engine" >> "%LOG_FILE%"

set CP_OFFSET=0
for /f %%i in ('docker ps -q --filter "label=component=engine" 2^>nul ^| find /c /v ""') do set CP_OFFSET=%%i

echo [DEBUG] CP_OFFSET detectado: !CP_OFFSET! >> "%LOG_FILE%"
echo [LOG] CPs existentes: !CP_OFFSET! >> "%LOG_FILE%"
echo [DEBUG] Antes de mostrar mensaje... >> "%LOG_FILE%"

echo CPs existentes: !CP_OFFSET!
echo Comenzando lanzamiento...

echo [DEBUG] Mensaje mostrado >> "%LOG_FILE%"
echo.
echo [DEBUG] Iniciando timeout de 2 segundos... >> "%LOG_FILE%"
timeout /t 2 /nobreak >nul
echo [DEBUG] Timeout completado, continuando... >> "%LOG_FILE%"

REM LANZAR CPS
echo ============================================================
echo [3/3] LANZANDO CHARGING POINTS
echo ============================================================
echo.

set BASE_PORT=5000
set KAFKA_SERVER=!CENTRAL_IP!:9092

echo. >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"
echo [MAIN] INICIANDO LANZAMIENTO DE !NUM_CPS! CPs >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"
echo [DEBUG] BASE_PORT=!BASE_PORT! >> "%LOG_FILE%"
echo [DEBUG] KAFKA_SERVER=!KAFKA_SERVER! >> "%LOG_FILE%"
echo [DEBUG] CENTRAL_IP=!CENTRAL_IP! >> "%LOG_FILE%"
echo [DEBUG] CP_OFFSET=!CP_OFFSET! >> "%LOG_FILE%"
echo [DEBUG] NUM_CPS=!NUM_CPS! >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

echo [LOG] Configuracion:
echo [LOG] - BASE_PORT: !BASE_PORT!
echo [LOG] - KAFKA_SERVER: !KAFKA_SERVER!
echo [LOG] - CENTRAL_IP: !CENTRAL_IP!
echo [LOG] - CP_OFFSET: !CP_OFFSET!
echo.

echo [DEBUG] Antes de iniciar bucle FOR >> "%LOG_FILE%"
echo [DEBUG] Rango del bucle: 1 a !NUM_CPS! >> "%LOG_FILE%"

for /L %%i in (1,1,!NUM_CPS!) do (
    set /a CP_NUM=!CP_OFFSET!+%%i
    echo. >> "%LOG_FILE%"
    echo [MAIN] ================================================ >> "%LOG_FILE%"
    echo [MAIN] Iteracion %%i de !NUM_CPS! >> "%LOG_FILE%"
    echo [MAIN] CP_NUM calculado: !CP_NUM! >> "%LOG_FILE%"
    echo [MAIN] ================================================ >> "%LOG_FILE%"
    echo [DEBUG] A punto de llamar a LANZAR_CP con CP_NUM=!CP_NUM! >> "%LOG_FILE%"
    
    call :LANZAR_CP !CP_NUM!
    
    echo [DEBUG] Retorno de LANZAR_CP completado >> "%LOG_FILE%"
    echo [MAIN] Esperando 2 segundos antes del siguiente CP... >> "%LOG_FILE%"
    timeout /t 2 /nobreak >nul
)

echo [DEBUG] Bucle FOR completado >> "%LOG_FILE%"

echo.
echo ============================================================
echo      !NUM_CPS! CHARGING POINT(S) INICIADO(S) CORRECTAMENTE
echo ============================================================
echo.
echo Ventanas abiertas:
echo   - PowerShell: !NUM_CPS! CPs
echo   - Navegador: !NUM_CPS! interfaces web
echo.
echo Interfaces web disponibles:
for /L %%i in (1,1,!NUM_CPS!) do (
    set /a CP_NUM_DISPLAY=!CP_OFFSET!+%%i
    set /a WEB_PORT_DISPLAY=9000+!CP_NUM_DISPLAY!
    if !CP_NUM_DISPLAY! LSS 10 (
        set CP_ID_DISPLAY=CP_00!CP_NUM_DISPLAY!
    ) else if !CP_NUM_DISPLAY! LSS 100 (
        set CP_ID_DISPLAY=CP_0!CP_NUM_DISPLAY!
    ) else (
        set CP_ID_DISPLAY=CP_!CP_NUM_DISPLAY!
    )
    echo   - !CP_ID_DISPLAY!: http://localhost:!WEB_PORT_DISPLAY!
)
echo.
echo Para DETENER:
echo   - Presiona Ctrl+C en cada ventana de PowerShell
echo   - O ejecuta: PC_B_STOP_ALL.bat
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
echo (Los CPs seguiran ejecutandose en sus ventanas)
echo.
pause
exit /b 0

REM ============================================================
REM  MODO 2: MULTIPLES DRIVERS
REM ============================================================
:MULTIPLE_DRIVERS
echo. >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"
echo [MODO] MULTIPLES DRIVERS SELECCIONADO >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"

echo ============================================================
echo    MODO: MULTIPLES DRIVERS
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
REM  MODO 3: CLASICO (1 CP + 1 DRIVER)
REM ============================================================
:CLASICO
echo ============================================================
echo    MODO CLASICO: 1 CP + 1 DRIVER
echo ============================================================
echo.

REM CONSTRUIR IMAGENES
echo ============================================================
echo [1/4] CONSTRUYENDO IMAGENES DOCKER
echo ============================================================
echo.

echo Construyendo imagen ev_engine:local...
docker build -t ev_engine:local -f ev_cp_engine/Dockerfile . >> "%LOG_FILE%" 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Fallo al construir imagen ev_engine
    echo Revisa el archivo de log: %LOG_FILE%
    pause
    exit /b 1
)
echo [OK] Imagen ev_engine construida
echo.

echo Construyendo imagen ev_monitor:local...
docker build -t ev_monitor:local -f ev_cp_monitor/Dockerfile . >> "%LOG_FILE%" 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Fallo al construir imagen ev_monitor
    echo Revisa el archivo de log: %LOG_FILE%
    pause
    exit /b 1
)
echo [OK] Imagen ev_monitor construida
echo.

echo Construyendo imagen ev_driver:local...
docker build -t ev_driver:local -f ev_driver/Dockerfile . >> "%LOG_FILE%" 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Fallo al construir imagen ev_driver
    echo Revisa el archivo de log: %LOG_FILE%
    pause
    exit /b 1
)
echo [OK] Imagen ev_driver construida
echo.

timeout /t 2 /nobreak >nul

REM LANZAR ENGINE
echo ============================================================
echo [2/4] LANZANDO ENGINE
echo ============================================================
echo.

start "Engine-PC_B" powershell -NoExit -Command "Write-Host 'Iniciando Engine (CP_001) en puerto 5001...' -ForegroundColor Cyan; Write-Host ''; docker run --rm -p 5001:5001 -p 9001:9001 --label project=evcharging-pc-b --label component=engine --label cp_id=CP_001 --name engine -e ENGINE_PORT=5001 -e CP_ID=CP_001 -e KAFKA_SERVER=!CENTRAL_IP!:9092 -e WEB_PORT=9001 ev_engine:local"

echo [OK] Engine iniciado en ventana separada
echo.
timeout /t 3 /nobreak >nul

REM Abrir interfaz web del engine (puerto 9001 para CP_001)
echo Abriendo interfaz web en http://localhost:9001...
start "" "http://localhost:9001"
timeout /t 1 /nobreak >nul

REM LANZAR DRIVER
echo ============================================================
echo [3/4] LANZANDO DRIVER
echo ============================================================
echo.

start "Driver-PC_B" powershell -NoExit -Command "Write-Host 'Iniciando Driver (DRIVER_456)...' -ForegroundColor Cyan; Write-Host ''; docker run --rm --label project=evcharging-pc-b --label component=driver --label cp_id=CP_001 --name driver -e KAFKA_BROKER=!CENTRAL_IP!:9092 -e DRIVER_ID=DRIVER_456 -e CP_ID=CP_001 -e MAT=ABC-1234 -e KW=1.0 -e LISTEN=true ev_driver:local"

echo [OK] Driver iniciado en ventana separada
echo.
timeout /t 3 /nobreak >nul

REM LANZAR MONITOR
echo ============================================================
echo [4/4] LANZANDO MONITOR
echo ============================================================
echo.

start "Monitor-PC_B" powershell -NoExit -Command "Write-Host 'Iniciando Monitor (CP_001)...' -ForegroundColor Cyan; Write-Host ''; docker run --rm --network host --label project=evcharging-pc-b --label component=monitor --label cp_id=CP_001 --name monitor -e CP_ID=CP_001 -e CENTRAL_IP=!CENTRAL_IP! -e CENTRAL_PORT=5000 -e ENGINE_IP=localhost -e ENGINE_PORT=5001 ev_monitor:local"

echo [OK] Monitor iniciado en ventana separada
echo.

REM RESUMEN FINAL
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
echo Ventanas abiertas:
echo   - PowerShell: Engine, Driver, Monitor
echo   - Navegador: Interfaz web del Engine
echo.
echo Interfaz web disponible:
echo   - CP_001: http://localhost:9001
echo.
echo Para DETENER:
echo   - Presiona Ctrl+C en cada ventana de PowerShell
echo   - O ejecuta: PC_B_STOP_ALL.bat
echo   - O ejecuta: docker stop engine driver monitor
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
echo (Los contenedores seguiran ejecutandose en sus ventanas)
echo.
pause
exit /b 0

REM ============================================================
REM  FUNCION PARA LANZAR UN CP
REM ============================================================
:LANZAR_CP
setlocal EnableDelayedExpansion
set CP_NUM=%1

echo. >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"
echo [FUNCION] LANZAR_CP INICIADA >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"
echo [DEBUG] LANZAR_CP llamado con CP_NUM=%1 >> "%LOG_FILE%"
echo [DEBUG] BASE_PORT=%BASE_PORT% >> "%LOG_FILE%"
echo [DEBUG] KAFKA_SERVER=%KAFKA_SERVER% >> "%LOG_FILE%"
echo [DEBUG] CENTRAL_IP=%CENTRAL_IP% >> "%LOG_FILE%"

REM Formatear ID con padding (CP_001, CP_002, etc.)
if %CP_NUM% LSS 10 (
    set CP_ID=CP_00%CP_NUM%
) else if %CP_NUM% LSS 100 (
    set CP_ID=CP_0%CP_NUM%
) else (
    set CP_ID=CP_%CP_NUM%
)

set /a ENGINE_PORT=%BASE_PORT%+%CP_NUM%

echo [DEBUG] CP_ID calculado: !CP_ID! >> "%LOG_FILE%"
echo [DEBUG] ENGINE_PORT calculado: !ENGINE_PORT! >> "%LOG_FILE%"

REM Calcular puerto web (9000 + CP_NUM)
set /a WEB_PORT_ENGINE=9000+%CP_NUM%

REM Construir comando ENGINE: Sin --network host, con mapeo de puertos TCP y Web
set "ENGINE_CMD=docker run --rm -p !ENGINE_PORT!:!ENGINE_PORT! -p !WEB_PORT_ENGINE!:!WEB_PORT_ENGINE! --name engine_!CP_ID! --label project=evcharging-pc-b --label component=engine --label cp_id=!CP_ID! -e ENGINE_PORT=!ENGINE_PORT! -e CP_ID=!CP_ID! -e KAFKA_SERVER=%KAFKA_SERVER% -e WEB_PORT=!WEB_PORT_ENGINE! ev_engine:local"
set "MONITOR_CMD=docker run --rm --network host --name monitor_!CP_ID! --label project=evcharging-pc-b --label component=monitor --label cp_id=!CP_ID! -e CP_ID=!CP_ID! -e CENTRAL_IP=%CENTRAL_IP% -e CENTRAL_PORT=5000 -e ENGINE_IP=localhost -e ENGINE_PORT=!ENGINE_PORT! ev_monitor:local"

echo. >> "%LOG_FILE%"
echo [DEBUG] ---- COMANDO ENGINE ---- >> "%LOG_FILE%"
echo !ENGINE_CMD! >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"
echo [DEBUG] ---- COMANDO MONITOR ---- >> "%LOG_FILE%"
echo !MONITOR_CMD! >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

REM Construir el comando PowerShell completo para Engine
set "PS_ENGINE_CMD=Write-Host 'Iniciando Engine (!CP_ID!) en puerto !ENGINE_PORT!...' -ForegroundColor Cyan; Write-Host ''; !ENGINE_CMD!"

REM Construir el comando PowerShell completo para Monitor
set "PS_MONITOR_CMD=Write-Host 'Iniciando Monitor (!CP_ID!)...' -ForegroundColor Cyan; Write-Host ''; !MONITOR_CMD!"

echo [DEBUG] ---- COMANDO POWERSHELL ENGINE ---- >> "%LOG_FILE%"
echo !PS_ENGINE_CMD! >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"
echo [DEBUG] ---- COMANDO POWERSHELL MONITOR ---- >> "%LOG_FILE%"
echo !PS_MONITOR_CMD! >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

REM Lanzar Engine en terminal PowerShell separada
echo [DEBUG] Ejecutando START PowerShell para Engine... >> "%LOG_FILE%"
start "Engine_!CP_ID!" powershell -NoExit -Command "!PS_ENGINE_CMD!"
echo [DEBUG] START ejecutado para Engine (errorlevel: !errorlevel!) >> "%LOG_FILE%"

REM Esperar para que el Engine este listo
echo [DEBUG] Esperando 3 segundos... >> "%LOG_FILE%"
timeout /t 3 /nobreak >nul

REM Calcular puerto web del engine (9000 + CP_NUM)
set /a WEB_PORT=9000+%CP_NUM%
set WEB_URL=http://localhost:!WEB_PORT!

echo [DEBUG] Abriendo navegador en !WEB_URL! >> "%LOG_FILE%"
echo Abriendo interfaz web para !CP_ID! en !WEB_URL!...
start "" "!WEB_URL!"
echo [DEBUG] Navegador abierto (errorlevel: !errorlevel!) >> "%LOG_FILE%"

REM Pequeña pausa para que el navegador se abra
timeout /t 1 /nobreak >nul

REM Lanzar Monitor en terminal PowerShell separada
echo [DEBUG] Ejecutando START PowerShell para Monitor... >> "%LOG_FILE%"
start "Monitor_!CP_ID!" powershell -NoExit -Command "!PS_MONITOR_CMD!"
echo [DEBUG] START ejecutado para Monitor (errorlevel: !errorlevel!) >> "%LOG_FILE%"

echo [DEBUG] !CP_ID! completado >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"

endlocal
goto :eof

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
set "PS_DRIVER_CMD=Write-Host 'Iniciando Driver (!DRIVER_ID!) -> !CP_ID! (!RANDOM_KW! kWh)...' -ForegroundColor Cyan; Write-Host ''; docker run --rm --name driver_!DRIVER_ID! --label project=evcharging-pc-b --label component=driver --label driver_id=!DRIVER_ID! -e KAFKA_BROKER=!KAFKA_SERVER! -e DRIVER_ID=!DRIVER_ID! -e CP_ID=!CP_ID! -e MAT=!MAT! -e KW=!RANDOM_KW! -e LISTEN=true ev_driver:local"

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
