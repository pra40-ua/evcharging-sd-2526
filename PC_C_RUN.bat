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

echo Cuantos Drivers deseas lanzar? (1-20)
set /p NUM_DRIVERS="Numero de Drivers: "

echo [INPUT] Usuario ingreso: NUM_DRIVERS=!NUM_DRIVERS! >> "%LOG_FILE%"

REM Validar entrada
if "%NUM_DRIVERS%"=="" set NUM_DRIVERS=1
if !NUM_DRIVERS! LSS 1 set NUM_DRIVERS=1
if !NUM_DRIVERS! GTR 20 set NUM_DRIVERS=20

echo [VALIDADO] NUM_DRIVERS final: !NUM_DRIVERS! >> "%LOG_FILE%"

echo.
echo Cuantos Charging Points estan disponibles? (1-20)
echo (Debe coincidir con el numero de CPs ejecutandose en PC_B)
set /p NUM_CPS_DISPONIBLES="Numero de CPs disponibles: "

echo [INPUT] Usuario ingreso: NUM_CPS_DISPONIBLES=!NUM_CPS_DISPONIBLES! >> "%LOG_FILE%"

REM Validar entrada
if "%NUM_CPS_DISPONIBLES%"=="" set NUM_CPS_DISPONIBLES=5
if !NUM_CPS_DISPONIBLES! LSS 1 set NUM_CPS_DISPONIBLES=1
if !NUM_CPS_DISPONIBLES! GTR 20 set NUM_CPS_DISPONIBLES=20

echo [VALIDADO] NUM_CPS_DISPONIBLES final: !NUM_CPS_DISPONIBLES! >> "%LOG_FILE%"

echo.
echo Se lanzaran !NUM_DRIVERS! Driver(s) para !NUM_CPS_DISPONIBLES! CP(s) disponibles
echo Los drivers se asignaran secuencialmente solo a CPs sin driver asignado
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

REM DETECTAR DRIVERS EXISTENTES Y CPs OCUPADOS
echo ============================================================
echo [2/3] DETECTANDO DRIVERS EXISTENTES Y CPs OCUPADOS
echo ============================================================
echo.

echo [DEBUG] Ejecutando: docker ps -q --filter "label=component=driver" >> "%LOG_FILE%"

set DRIVER_OFFSET=0
for /f %%i in ('docker ps -q --filter "label=component=driver" 2^>nul ^| find /c /v ""') do set DRIVER_OFFSET=%%i

echo [DEBUG] DRIVER_OFFSET detectado: !DRIVER_OFFSET! >> "%LOG_FILE%"
echo [LOG] Drivers existentes: !DRIVER_OFFSET! >> "%LOG_FILE%"

REM Detectar CPs ya asignados (buscar TODOS los drivers, no solo los de PC_C)
echo [DEBUG] Detectando CPs ya asignados... >> "%LOG_FILE%"
set CPs_OCUPADOS=
set TEMP_FILE_INIT=%TEMP%\cps_ocupados_init_%RANDOM%.txt
echo. > "!TEMP_FILE_INIT!"

for /f "tokens=*" %%i in ('docker ps -q --filter "label=component=driver" 2^>nul') do (
    for /f "tokens=*" %%c in ('docker inspect --format={{.Config.Labels.cp_id}} %%i 2^>nul') do (
        if not "%%c"=="" (
            echo %%c >> "!TEMP_FILE_INIT!"
        )
    )
)

REM Leer todos los CPs ocupados desde el archivo temporal
if exist "!TEMP_FILE_INIT!" (
    for /f "tokens=*" %%c in (!TEMP_FILE_INIT!) do (
        if not "%%c"=="" (
            echo [DEBUG] CP ocupado detectado: %%c >> "%LOG_FILE%"
            if "!CPs_OCUPADOS!"=="" (
                set CPs_OCUPADOS=%%c
            ) else (
                set CPs_OCUPADOS=!CPs_OCUPADOS! %%c
            )
        )
    )
    del "!TEMP_FILE_INIT!" >nul 2>&1
)

echo [DEBUG] CPs_OCUPADOS: !CPs_OCUPADOS! >> "%LOG_FILE%"
echo [LOG] Drivers existentes: !DRIVER_OFFSET! >> "%LOG_FILE%"
if not "!CPs_OCUPADOS!"=="" (
    echo [LOG] CPs ya ocupados: !CPs_OCUPADOS! >> "%LOG_FILE%"
) else (
    echo [LOG] No hay CPs ocupados >> "%LOG_FILE%"
)

echo Drivers existentes: !DRIVER_OFFSET!
if not "!CPs_OCUPADOS!"=="" (
    echo CPs ya ocupados: !CPs_OCUPADOS!
)
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

set DRIVERS_ASIGNADOS=0
for /L %%i in (1,1,!NUM_DRIVERS!) do (
    set /a DRIVER_NUM=!DRIVER_OFFSET!+%%i
    echo. >> "%LOG_FILE%"
    echo [MAIN] ================================================ >> "%LOG_FILE%"
    echo [MAIN] Iteracion %%i de !NUM_DRIVERS! >> "%LOG_FILE%"
    echo [MAIN] DRIVER_NUM calculado: !DRIVER_NUM! >> "%LOG_FILE%"
    echo [MAIN] ================================================ >> "%LOG_FILE%"
    echo [DEBUG] A punto de llamar a LANZAR_DRIVER con DRIVER_NUM=!DRIVER_NUM! >> "%LOG_FILE%"
    
    call :LANZAR_DRIVER !DRIVER_NUM! !NUM_CPS_DISPONIBLES!
    set RESULTADO=!errorlevel!
    
    if !RESULTADO! equ 0 (
        set /a DRIVERS_ASIGNADOS+=1
        echo [DEBUG] Driver asignado exitosamente. Total: !DRIVERS_ASIGNADOS! >> "%LOG_FILE%"
    ) else (
        echo [DEBUG] Driver no asignado (sin CPs disponibles) >> "%LOG_FILE%"
    )
    
    echo [DEBUG] Retorno de LANZAR_DRIVER completado >> "%LOG_FILE%"
    echo [MAIN] Esperando 2 segundos antes del siguiente driver para que Docker registre el contenedor... >> "%LOG_FILE%"
    timeout /t 2 /nobreak >nul
)

echo [DEBUG] Bucle FOR completado >> "%LOG_FILE%"
echo [LOG] Total de drivers asignados: !DRIVERS_ASIGNADOS! de !NUM_DRIVERS! >> "%LOG_FILE%"

echo.
echo ============================================================
echo      !DRIVERS_ASIGNADOS! DRIVER(S) INICIADO(S) CORRECTAMENTE
if !DRIVERS_ASIGNADOS! LSS !NUM_DRIVERS! (
    set /a NO_ASIGNADOS=!NUM_DRIVERS!-!DRIVERS_ASIGNADOS!
    echo      !NO_ASIGNADOS! DRIVER(S) NO ASIGNADO(S) (sin CPs disponibles)
)
echo ============================================================
echo.
if !DRIVERS_ASIGNADOS! GTR 0 (
    echo Ventanas abiertas (PowerShell): !DRIVERS_ASIGNADOS! Driver(s)
)
echo.
echo Los drivers se detendran automaticamente al recibir su ticket.
echo Para detener manualmente: PC_B_STOP_ALL.bat
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
if !DRIVERS_ASIGNADOS! GTR 0 (
    echo (Los Drivers seguiran ejecutandose en sus ventanas)
)
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

REM Esperar un momento para que los drivers anteriores se registren
timeout /t 1 /nobreak >nul

REM Detectar CPs ocupados nuevamente para esta iteración
REM Buscar TODOS los drivers (no solo los de PC_C) para detectar CPs ocupados
set CPs_OCUPADOS=
set TEMP_FILE=%TEMP%\cps_ocupados_%RANDOM%.txt
echo. > "!TEMP_FILE!"

for /f "tokens=*" %%i in ('docker ps -q --filter "label=component=driver" 2^>nul') do (
    for /f "tokens=*" %%c in ('docker inspect --format={{.Config.Labels.cp_id}} %%i 2^>nul') do (
        if not "%%c"=="" (
            echo %%c >> "!TEMP_FILE!"
        )
    )
)

REM Leer todos los CPs ocupados desde el archivo temporal
if exist "!TEMP_FILE!" (
    for /f "tokens=*" %%c in (!TEMP_FILE!) do (
        if not "%%c"=="" (
            if "!CPs_OCUPADOS!"=="" (
                set CPs_OCUPADOS=%%c
            ) else (
                set CPs_OCUPADOS=!CPs_OCUPADOS! %%c
            )
        )
    )
    del "!TEMP_FILE!" >nul 2>&1
)

echo [DEBUG] CPs ocupados en esta iteracion: !CPs_OCUPADOS! >> "%LOG_FILE%"

REM Buscar el primer CP disponible secuencialmente
set CP_ID=
set CP_ENCONTRADO=0
for /L %%j in (1,1,%NUM_CPS_TOTAL%) do (
    REM Formatear CP candidato
    if %%j LSS 10 (
        set CP_CANDIDATO=CP_00%%j
    ) else if %%j LSS 100 (
        set CP_CANDIDATO=CP_0%%j
    ) else (
        set CP_CANDIDATO=CP_%%j
    )
    
    REM Verificar si este CP está ocupado usando una verificación más robusta
    set CP_OCUPADO=0
    if not "!CPs_OCUPADOS!"=="" (
        REM Buscar el CP en la lista de ocupados (usando findstr con /C para buscar la cadena exacta)
        echo !CPs_OCUPADOS! | findstr /C:"!CP_CANDIDATO!" >nul 2>&1
        if !errorlevel! equ 0 (
            set CP_OCUPADO=1
            echo [DEBUG] CP !CP_CANDIDATO! esta ocupado >> "%LOG_FILE%"
        )
    )
    
    REM Si el CP no está ocupado y aún no hemos encontrado uno, asignarlo
    if !CP_OCUPADO! equ 0 (
        if !CP_ENCONTRADO! equ 0 (
            set CP_ID=!CP_CANDIDATO!
            set CP_ENCONTRADO=1
            echo [DEBUG] CP disponible encontrado: !CP_ID! >> "%LOG_FILE%"
            goto :CP_ENCONTRADO
        )
    )
)
:CP_ENCONTRADO

REM Si no se encontró CP disponible, no asignar driver
if "!CP_ID!"=="" (
    echo [WARNING] No hay CPs disponibles para asignar al driver !DRIVER_ID! >> "%LOG_FILE%"
    echo [WARNING] Todos los CPs estan ocupados. Saltando asignacion de !DRIVER_ID! >> "%LOG_FILE%"
    echo.
    echo [ADVERTENCIA] No hay CPs disponibles. El driver !DRIVER_ID! no sera asignado.
    endlocal
    exit /b 1
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

REM Construir comando PowerShell completo (agregando label cp_id y network)
set "PS_DRIVER_CMD=Write-Host 'Iniciando Driver (!DRIVER_ID!) -> !CP_ID! (!RANDOM_KW! kWh)...' -ForegroundColor Cyan; Write-Host ''; docker run --rm --name driver_!DRIVER_ID! --network evnet --label project=evcharging-pc-c --label component=driver --label driver_id=!DRIVER_ID! --label cp_id=!CP_ID! -e KAFKA_BROKER=!KAFKA_SERVER! -e DRIVER_ID=!DRIVER_ID! -e CP_ID=!CP_ID! -e MAT=!MAT! -e KW=!RANDOM_KW! -e LISTEN=true ev_driver:local"

echo [DEBUG] ---- COMANDO POWERSHELL DRIVER ---- >> "%LOG_FILE%"
echo !PS_DRIVER_CMD! >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

REM Lanzar Driver en terminal PowerShell separada
echo [DEBUG] Ejecutando START PowerShell para Driver... >> "%LOG_FILE%"
start "Driver_!DRIVER_ID!" powershell -NoExit -Command "!PS_DRIVER_CMD!"
echo [DEBUG] START ejecutado para Driver (errorlevel: !errorlevel!) >> "%LOG_FILE%"

echo [DEBUG] !DRIVER_ID! completado exitosamente >> "%LOG_FILE%"
echo [DEBUG] Driver !DRIVER_ID! asignado a !CP_ID! >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"
echo.
echo [OK] Driver !DRIVER_ID! asignado a !CP_ID!

endlocal
exit /b 0

