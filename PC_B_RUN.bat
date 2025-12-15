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
REM  CONFIGURAR REGISTRY_URL AUTOMATICAMENTE
REM ============================================================
echo ============================================================
echo [INFO] CONFIGURANDO REGISTRY_URL
echo ============================================================
echo.

REM Verificar si Registry está corriendo localmente (puerto 6000)
set REGISTRY_LOCAL=0
echo [INFO] Verificando si Registry está corriendo localmente (puerto 6000)...
echo [DEBUG] Verificando si Registry está corriendo localmente en puerto 6000... >> "%LOG_FILE%"

REM Intentar HTTPS primero
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $response = Invoke-WebRequest -Uri 'https://127.0.0.1:6000/api/health' -Method GET -SkipCertificateCheck -TimeoutSec 2 -ErrorAction Stop; exit 0 } catch { exit 1 }" >nul 2>&1
if !errorlevel! equ 0 (
    set REGISTRY_LOCAL=1
    REM IMPORTANTE: Usar host.docker.internal para que los contenedores Docker puedan acceder al host de Windows
    set REGISTRY_URL=https://host.docker.internal:6000/api
    echo [OK] Registry detectado localmente (HTTPS)
    echo [INFO] Usando host.docker.internal para acceso desde contenedores Docker
    echo [DEBUG] Registry local detectado (HTTPS) - usando host.docker.internal >> "%LOG_FILE%"
    goto :registry_configured
)

REM Intentar HTTP
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $response = Invoke-WebRequest -Uri 'http://127.0.0.1:6000/api/health' -Method GET -TimeoutSec 2 -ErrorAction Stop; exit 0 } catch { exit 1 }" >nul 2>&1
if !errorlevel! equ 0 (
    set REGISTRY_LOCAL=1
    REM IMPORTANTE: Usar host.docker.internal para que los contenedores Docker puedan acceder al host de Windows
    set REGISTRY_URL=http://host.docker.internal:6000/api
    echo [OK] Registry detectado localmente (HTTP)
    echo [INFO] Usando host.docker.internal para acceso desde contenedores Docker
    echo [DEBUG] Registry local detectado (HTTP) - usando host.docker.internal >> "%LOG_FILE%"
    goto :registry_configured
)

REM Registry no está local, intentar en PC_A (Central)
echo [INFO] Registry no detectado localmente. Verificando en PC_A...
echo [DEBUG] Intentando conectar a Registry en PC_A: https://!CENTRAL_IP!:6000/api/health >> "%LOG_FILE%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $response = Invoke-WebRequest -Uri 'https://!CENTRAL_IP!:6000/api/health' -Method GET -SkipCertificateCheck -TimeoutSec 2 -ErrorAction Stop; exit 0 } catch { exit 1 }" >nul 2>&1
if !errorlevel! equ 0 (
    set REGISTRY_URL=https://!CENTRAL_IP!:6000/api
    echo [OK] Registry detectado en PC_A (HTTPS)
    echo [DEBUG] Registry detectado en PC_A (HTTPS): !REGISTRY_URL! >> "%LOG_FILE%"
    goto :registry_configured
)

REM Intentar HTTP en PC_A
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $response = Invoke-WebRequest -Uri 'http://!CENTRAL_IP!:6000/api/health' -Method GET -TimeoutSec 2 -ErrorAction Stop; exit 0 } catch { exit 1 }" >nul 2>&1
if !errorlevel! equ 0 (
    set REGISTRY_URL=http://!CENTRAL_IP!:6000/api
    echo [OK] Registry detectado en PC_A (HTTP)
    echo [DEBUG] Registry detectado en PC_A (HTTP): !REGISTRY_URL! >> "%LOG_FILE%"
    goto :registry_configured
)

REM Si no se encuentra, mostrar error crítico
echo [ERROR] Registry NO detectado ni localmente ni en PC_A
echo.
echo ========================================================================
echo   ERROR CRÍTICO: EV_Registry NO ESTÁ EJECUTÁNDOSE
echo ========================================================================
echo.
echo El Registry es OBLIGATORIO antes de ejecutar los CPs.
echo.
echo PASOS REQUERIDOS:
echo   1. Ejecuta primero: INICIAR_REGISTRY_PC_B.bat
echo   2. Espera a ver el mensaje: "EV_Registry iniciado en PC_B con HTTPS"
echo   3. Luego ejecuta este script nuevamente: PC_B_RUN.bat
echo.
echo IMPORTANTE:
echo   - El Registry debe estar en el mismo PC_B donde ejecutas los CPs
echo   - El Registry debe estar en el puerto 6000
echo   - Debes haber ejecutado PC_A_RUN.bat primero para iniciar MySQL
echo.
echo [ERROR] No se puede continuar sin Registry activo >> "%LOG_FILE%"
echo [ERROR] REGISTRY_URL no configurado porque Registry no está disponible >> "%LOG_FILE%"
pause
exit /b 1

:registry_configured
REM Configurar variable de entorno para esta sesión
set REGISTRY_URL=!REGISTRY_URL!
echo.
echo [OK] REGISTRY_URL configurado: !REGISTRY_URL!
echo [DEBUG] REGISTRY_URL final: !REGISTRY_URL! >> "%LOG_FILE%"
echo.
echo ============================================================
echo.

REM ============================================================
REM  PASO 0: INICIAR EV_WEATHER
REM ============================================================
echo ============================================================
echo [0/4] INICIANDO EV_WEATHER
echo ============================================================
echo.

REM Debug: mostrar directorio actual
echo [DEBUG] Directorio actual: %CD% >> "%LOG_FILE%"
echo [DEBUG] Verificando existencia de OPENWEATHER_API_KEY.txt... >> "%LOG_FILE%"
echo [DEBUG] Ruta completa buscada: %CD%\OPENWEATHER_API_KEY.txt >> "%LOG_FILE%"

REM Verificar si existe el archivo de configuración de OpenWeather (con ruta completa)
set "WEATHER_KEY_FILE=%CD%\OPENWEATHER_API_KEY.txt"
if not exist "!WEATHER_KEY_FILE!" (
    REM Intentar también con ruta relativa
    if not exist "OPENWEATHER_API_KEY.txt" (
        echo [ADVERTENCIA] No se encontro OPENWEATHER_API_KEY.txt
        echo [DEBUG] Archivo no encontrado en: !WEATHER_KEY_FILE! >> "%LOG_FILE%"
        echo [DEBUG] Archivo no encontrado en: %CD%\OPENWEATHER_API_KEY.txt >> "%LOG_FILE%"
        echo.
        echo Para usar EV_Weather, crea un archivo OPENWEATHER_API_KEY.txt
        echo con tu API Key de OpenWeather (obtener en https://openweathermap.org/api)
        echo.
        echo Continuando sin EV_Weather...
        echo.
        timeout /t 3 /nobreak >nul
        goto MENU
    )
)

echo [DEBUG] Archivo OPENWEATHER_API_KEY.txt encontrado >> "%LOG_FILE%"
echo [OK] Archivo OPENWEATHER_API_KEY.txt encontrado
echo [INFO] Leyendo contenido del archivo...

REM Leer API Key (método más robusto - solo primera línea)
REM Usar ruta completa para asegurar que se lee desde el directorio correcto
set OPENWEATHER_API_KEY=
set "WEATHER_KEY_FILE=%CD%\OPENWEATHER_API_KEY.txt"
if exist "OPENWEATHER_API_KEY.txt" (
    for /f "usebackq delims=" %%a in ("OPENWEATHER_API_KEY.txt") do (
        set "OPENWEATHER_API_KEY=%%a"
        goto :read_done
    )
) else if exist "!WEATHER_KEY_FILE!" (
    for /f "usebackq delims=" %%a in ("!WEATHER_KEY_FILE!") do (
        set "OPENWEATHER_API_KEY=%%a"
        goto :read_done
    )
)
:read_done

REM El for /f ya elimina saltos de línea automáticamente
REM Solo necesitamos eliminar espacios y tabs si los hay
REM (pero normalmente la API key no debería tenerlos)

REM Debug: mostrar lo que se leyó
echo [DEBUG] Contenido leido del archivo: !OPENWEATHER_API_KEY! >> "%LOG_FILE%"
echo [DEBUG] Longitud de la API Key: >> "%LOG_FILE%"
echo !OPENWEATHER_API_KEY! >> "%LOG_FILE%"

REM Mostrar información en pantalla
if defined OPENWEATHER_API_KEY (
    echo [OK] API Key leida correctamente
    echo [INFO] Longitud: !OPENWEATHER_API_KEY:~0,50!...
    echo [DEBUG] Verificando que la API Key no este vacia... >> "%LOG_FILE%"
    echo [DEBUG] Valor de OPENWEATHER_API_KEY: "!OPENWEATHER_API_KEY!" >> "%LOG_FILE%"
) else (
    echo [ERROR] No se pudo leer la API Key del archivo
    echo [ERROR] OPENWEATHER_API_KEY no esta definida >> "%LOG_FILE%"
)

REM Verificar que se leyó algo - validación simple
echo [DEBUG] Verificando que la API Key fue leida correctamente... >> "%LOG_FILE%"
echo [DEBUG] Valor de OPENWEATHER_API_KEY: "!OPENWEATHER_API_KEY!" >> "%LOG_FILE%"

REM Si la variable no está definida o está vacía, saltar a MENU
if not defined OPENWEATHER_API_KEY goto :skip_weather
if "!OPENWEATHER_API_KEY!"=="" goto :skip_weather

REM Si llegamos aquí, la API key está definida y no está vacía
echo [DEBUG] API Key validada: tiene contenido >> "%LOG_FILE%"
echo [OK] API Key leida y validada correctamente
echo [INFO] Continuando con el inicio de EV_Weather...

REM Construir URL de Central API (puerto 5001 para API REST)
set CENTRAL_API_URL=http://!CENTRAL_IP!:5001/api

echo.
echo [OK] Todas las validaciones completadas correctamente
echo.
echo ============================================================
echo   INICIANDO EV_WEATHER
echo ============================================================
echo   - API Key: !OPENWEATHER_API_KEY:~0,10!...
echo   - Central API: !CENTRAL_API_URL!
echo   - Archivo: OPENWEATHER_API_KEY.txt encontrado
echo ============================================================
echo.

REM Verificar que Python está disponible
echo [DEBUG] Verificando Python... >> "%LOG_FILE%"
py --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Python no esta disponible. EV_Weather no se iniciara.
    echo [ERROR] Ejecuta: py --version para verificar
    echo Continuando sin EV_Weather...
    echo.
    timeout /t 3 /nobreak >nul
    goto MENU
)
echo [DEBUG] Python encontrado >> "%LOG_FILE%"

REM Verificar que existe el archivo EV_W.py
echo [DEBUG] Verificando ev_weather\EV_W.py... >> "%LOG_FILE%"
if not exist "ev_weather\EV_W.py" (
    echo [ERROR] No se encuentra ev_weather\EV_W.py
    echo [ERROR] Verifica que el archivo existe en la ruta correcta
    echo Continuando sin EV_Weather...
    echo.
    timeout /t 3 /nobreak >nul
    goto MENU
)
echo [DEBUG] Archivo ev_weather\EV_W.py encontrado >> "%LOG_FILE%"
goto :launch_weather

:skip_weather
echo.
echo [ERROR] No se pudo leer la API Key del archivo
echo [ERROR] El archivo existe pero esta vacio o no se pudo leer >> "%LOG_FILE%"
echo.
echo Verifica que el archivo contiene tu API Key de OpenWeather
echo (solo la clave, sin espacios ni saltos de linea)
echo.
echo Continuando sin EV_Weather...
echo.
timeout /t 3 /nobreak >nul
echo [DEBUG] Saltando al MENU desde skip_weather >> "%LOG_FILE%"
goto MENU

:launch_weather

echo [DEBUG] Llegando a :launch_weather >> "%LOG_FILE%"
echo [DEBUG] API Key leida correctamente: !OPENWEATHER_API_KEY:~0,10!... >> "%LOG_FILE%"
echo [DEBUG] Iniciando lanzamiento de EV_Weather... >> "%LOG_FILE%"
echo [INFO] Preparando lanzamiento de EV_Weather...

REM Crear script temporal con las variables ya expandidas
echo [DEBUG] Creando script temporal... >> "%LOG_FILE%"
set TEMP_WEATHER_SCRIPT=%TEMP%\ev_weather_launch_%RANDOM%.bat
echo [DEBUG] Ruta del script temporal: !TEMP_WEATHER_SCRIPT! >> "%LOG_FILE%"

REM Guardar valores en variables temporales para usar en el script
set WEATHER_API_KEY=!OPENWEATHER_API_KEY!
set WEATHER_CENTRAL_URL=!CENTRAL_API_URL!
echo [DEBUG] Variables temporales configuradas >> "%LOG_FILE%"

REM Crear el script temporal usando un método más robusto
echo [DEBUG] Escribiendo contenido del script temporal... >> "%LOG_FILE%"
echo [DEBUG] Ruta completa: !TEMP_WEATHER_SCRIPT! >> "%LOG_FILE%"

REM Guardar las variables en variables con nombres más simples para evitar problemas de expansión
set "WK=!WEATHER_API_KEY!"
set "WCU=!WEATHER_CENTRAL_URL!"

REM Guardar el directorio del proyecto para usar en el script temporal
set "PROJ_DIR=%CD%"
echo [DEBUG] Directorio del proyecto: !PROJ_DIR! >> "%LOG_FILE%"

REM Crear el script usando un bloque que expande correctamente las variables
REM Escapar correctamente los caracteres especiales dentro del bloque
(
echo @echo off
echo setlocal EnableDelayedExpansion
echo cd /d "!PROJ_DIR!"
echo echo ============================================================
echo echo   EV_WEATHER - Weather Control Office
echo echo ============================================================
echo echo.
echo echo Iniciando EV_Weather...
echo echo   - API Key: !WK:~0,10!...
echo echo   - Central API: !WCU!
echo echo.
echo echo ============================================================
echo echo.
echo py ev_weather\EV_W.py --api-key "!WK!" --central-url "!WCU!"
echo ^if errorlevel 1 ^(
echo     echo.
echo     echo [ERROR] EV_Weather fallo al iniciar
echo     echo Verifica que:
echo     echo   1. Python esta instalado y en PATH
echo     echo   2. El archivo ev_weather\EV_W.py existe
echo     echo   3. Las dependencias estan instaladas ^(pip install -r ev_weather\requirements.txt^)
echo     echo.
echo     pause
echo ^) else ^(
echo     echo.
echo     echo EV_Weather ha finalizado. Presiona cualquier tecla para cerrar...
echo     pause
echo ^)
) > "!TEMP_WEATHER_SCRIPT!"
set CREATE_RESULT=!errorlevel!
echo [DEBUG] Resultado de creacion del script: !CREATE_RESULT! >> "%LOG_FILE%"

REM Verificar que el archivo se creó correctamente
if not exist "!TEMP_WEATHER_SCRIPT!" (
    echo [ERROR] El script temporal no se creo correctamente >> "%LOG_FILE%"
    echo [ERROR] No se pudo crear el script temporal para EV_Weather
    echo [ERROR] Ruta intentada: !TEMP_WEATHER_SCRIPT!
    echo.
    pause
    goto MENU
)

if !CREATE_RESULT! neq 0 (
    echo [ERROR] Fallo al crear el script temporal >> "%LOG_FILE%"
    echo [ERROR] No se pudo crear el script temporal para EV_Weather
    echo [ERROR] Ruta intentada: !TEMP_WEATHER_SCRIPT!
    echo.
    pause
    goto MENU
)

echo [DEBUG] Script temporal creado exitosamente >> "%LOG_FILE%"
echo Lanzando EV_Weather en nueva ventana...
echo [DEBUG] Script temporal: !TEMP_WEATHER_SCRIPT! >> "%LOG_FILE%"
echo [DEBUG] API Key: !OPENWEATHER_API_KEY:~0,10!... >> "%LOG_FILE%"
echo [DEBUG] Central URL: !CENTRAL_API_URL! >> "%LOG_FILE%"

start "EV_Weather-PC_B" cmd /k "!TEMP_WEATHER_SCRIPT!"
if !errorlevel! neq 0 (
    echo [ERROR] Fallo al lanzar EV_Weather >> "%LOG_FILE%"
    echo [ERROR] No se pudo lanzar EV_Weather en nueva ventana
    echo.
    pause
    goto MENU
)
echo [DEBUG] Comando START ejecutado exitosamente >> "%LOG_FILE%"

REM Esperar un momento para verificar que la ventana se abrió
timeout /t 2 /nobreak >nul

echo [OK] EV_Weather deberia estar ejecutandose en ventana separada
echo      Busca la ventana titulada "EV_Weather-PC_B"
echo.
echo [DEBUG] EV_Weather lanzado, continuando al MENU... >> "%LOG_FILE%"
timeout /t 2 /nobreak >nul

REM ============================================================
REM  MENU DE SELECCION
REM ============================================================
:MENU
echo [DEBUG] Llegando al MENU >> "%LOG_FILE%"
echo ============================================================
echo   MENU DE OPCIONES
echo ============================================================
echo.
echo Que deseas lanzar?
echo.
echo   [1] Multiples CPs (hasta 20 CPs simultaneos)
echo   [2] Multiples Drivers (hasta 20 Drivers simultaneos)
echo   [3] CLASICO: 1 CP + 1 Driver
echo   [0] SALIR
echo.
set "MODO="
set /p MODO="Selecciona opcion (1, 2, 3 o 0): "

REM Si no se ingresó nada (usuario presionó Enter sin escribir), volver al MENU
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
echo [DEBUG] Saliendo del script >> "%LOG_FILE%"
pause
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

echo Cuantos Charging Points deseas lanzar? (1-20)
set /p NUM_CPS="Numero de CPs: "

echo [INPUT] Usuario ingreso: NUM_CPS=!NUM_CPS! >> "%LOG_FILE%"

REM Validar entrada
if "%NUM_CPS%"=="" set NUM_CPS=1
if !NUM_CPS! LSS 1 set NUM_CPS=1
if !NUM_CPS! GTR 20 set NUM_CPS=20

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
echo   - EV_Weather: Monitoreo climatológico
echo   - PowerShell: !NUM_CPS! CPs (Engine + Monitor)
echo   - Navegador: !NUM_CPS! interfaces web
echo   - Menú Control: !NUM_CPS! menús de control de suministro
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
set /p NUM_CPS_DISPONIBLES="Numero de CPs disponibles: "

echo [INPUT] Usuario ingreso: NUM_CPS_DISPONIBLES=!NUM_CPS_DISPONIBLES! >> "%LOG_FILE%"

REM Validar entrada
if "%NUM_CPS_DISPONIBLES%"=="" set NUM_CPS_DISPONIBLES=5
if !NUM_CPS_DISPONIBLES! LSS 1 set NUM_CPS_DISPONIBLES=1
if !NUM_CPS_DISPONIBLES! GTR 20 set NUM_CPS_DISPONIBLES=20

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
echo Ventanas abiertas:
echo   - EV_Weather: Monitoreo climatológico
echo   - PowerShell: !NUM_DRIVERS! Drivers
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

REM Lanzar Menu de Control de Suministro para CP_001
call :LANZAR_MENU_CONTROL CP_001 9001

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

start "Monitor-PC_B" powershell -NoExit -Command "Write-Host 'Iniciando Monitor (CP_001)...' -ForegroundColor Cyan; Write-Host ''; docker run --rm --network evnet --label project=evcharging-pc-b --label component=monitor --label cp_id=CP_001 --name monitor -e CP_ID=CP_001 -e CENTRAL_IP=!CENTRAL_IP! -e CENTRAL_PORT=5000 -e ENGINE_IP=host.docker.internal -e ENGINE_PORT=5001 -e REGISTRY_URL=!REGISTRY_URL! -e WEATHER_API_URL=http://host.docker.internal:5002 ev_monitor:local"

echo [OK] Monitor iniciado en ventana separada
echo.

REM RESUMEN FINAL
echo.
echo ============================================================
echo      SISTEMA PC_B DOCKER INICIADO CORRECTAMENTE
echo ============================================================
echo.
echo Contenedores ejecutandose:
echo   - EV_Weather: Monitoreo climatológico
echo   - Engine:  CP_001 en puerto 5001
echo   - Driver:  DRIVER_456 (MAT: ABC-1234)
echo   - Monitor: CP_001
echo.
echo Ventanas abiertas:
echo   - EV_Weather: Monitoreo climatológico
echo   - PowerShell: Engine, Driver, Monitor
echo   - Navegador: Interfaz web del Engine
echo   - Menú Control: Menú de control de suministro (CP_001)
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
set "MONITOR_CMD=docker run --rm --network evnet --name monitor_!CP_ID! --label project=evcharging-pc-b --label component=monitor --label cp_id=!CP_ID! -e CP_ID=!CP_ID! -e CENTRAL_IP=%CENTRAL_IP% -e CENTRAL_PORT=5000 -e ENGINE_IP=host.docker.internal -e ENGINE_PORT=!ENGINE_PORT! -e REGISTRY_URL=!REGISTRY_URL! -e WEATHER_API_URL=http://host.docker.internal:5002 ev_monitor:local"

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

REM Lanzar Menu de Control de Suministro
echo [DEBUG] Lanzando Menu de Control para !CP_ID!... >> "%LOG_FILE%"
call :LANZAR_MENU_CONTROL !CP_ID! !WEB_PORT_ENGINE!
echo [DEBUG] Menu de Control lanzado >> "%LOG_FILE%"

echo [DEBUG] !CP_ID! completado >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"

endlocal
goto :eof

REM ============================================================
REM  FUNCION PARA LANZAR MENU DE CONTROL DE SUMINISTRO
REM ============================================================
:LANZAR_MENU_CONTROL
setlocal EnableDelayedExpansion
set CP_ID_PARAM=%1
set WEB_PORT_PARAM=%2

echo. >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"
echo [FUNCION] LANZAR_MENU_CONTROL INICIADA >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"
echo [DEBUG] LANZAR_MENU_CONTROL llamado con CP_ID=%1, WEB_PORT=%2 >> "%LOG_FILE%"

REM Construir URL de la API
set API_BASE_URL=http://127.0.0.1:%WEB_PORT_PARAM%/api

echo [DEBUG] API_BASE_URL: !API_BASE_URL! >> "%LOG_FILE%"

REM Crear script .bat temporal con el menu
set TEMP_SCRIPT=%TEMP%\menu_control_!CP_ID_PARAM!.bat

(
echo @echo off
echo setlocal EnableDelayedExpansion
echo title Menú de Control de Suministro ^(!CP_ID_PARAM!^) - API: !API_BASE_URL!
echo.
echo REM ============================================================
echo REM  CONFIGURACION
echo REM ============================================================
echo set API_BASE_URL=!API_BASE_URL!
echo.
echo :MENU
echo cls
echo echo ============================================================
echo echo   MENÚ DE CONTROL DE SUMINISTRO ^(!CP_ID_PARAM!^)
echo echo   Engine: %%API_BASE_URL%%
echo echo ============================================================
echo echo.
echo echo Selecciona la operacion a ejecutar:
echo echo.
echo echo   [1] - Iniciar Suministro
echo echo   [2] - Solicitar Fin del Suministro
echo echo   [3] - Simular Avería
echo echo   [4] - Recuperar Avería
echo echo   [0] - SALIR
echo echo.
echo echo ============================================================
echo REM Limpiar variables de opciones especiales
echo set "OPCION_ESPECIAL="
echo set "OPCION="
echo set /p OPCION="Selecciona opcion: "
echo.
echo REM Validar que se ingreso algo
echo if not defined OPCION ^(
echo     goto ERROR_OPCION
echo ^)
echo.
echo echo.
echo.
echo REM ============================================================
echo REM  EJECUCION DE COMANDOS
echo REM ============================================================
echo.
echo REM Limpiar variables antes de establecer nuevas
echo set "DESCRIPCION="
echo set "COMANDO_PS="
echo set "OPCION_ESPECIAL="
echo.
echo if "%%OPCION%%"=="1" ^(
echo     set "DESCRIPCION=Iniciar Suministro"
echo     set "COMANDO_PS=Invoke-WebRequest -Method POST -Uri %%API_BASE_URL%%/iniciar_suministro"
echo     goto EJECUTAR
echo ^)
echo.
echo if "%%OPCION%%"=="2" ^(
echo     set "DESCRIPCION=Solicitar Fin del Suministro"
echo     set "COMANDO_PS=Invoke-WebRequest -Method POST -Uri %%API_BASE_URL%%/solicitar_fin"
echo     goto EJECUTAR
echo ^)
echo.
echo if "%%OPCION%%"=="3" ^(
echo     set "DESCRIPCION=Simular Avería"
echo     set "OPCION_ESPECIAL=3"
echo     goto EJECUTAR
echo ^)
echo.
echo if "%%OPCION%%"=="4" ^(
echo     set "DESCRIPCION=Recuperar Avería"
echo     set "OPCION_ESPECIAL="
echo     set "COMANDO_PS=Invoke-WebRequest -Method POST -Uri %%API_BASE_URL%%/recuperar_averia"
echo     goto EJECUTAR
echo ^)
echo.
echo if "%%OPCION%%"=="0" ^(
echo     echo Saliendo...
echo     timeout /t 1 /nobreak ^>nul
echo     exit /b 0
echo ^)
echo.
echo :ERROR_OPCION
echo echo [ERROR] Opción no válida: %%OPCION%%
echo echo Presiona cualquier tecla para continuar...
echo pause ^>nul
echo goto MENU
echo.
echo :EJECUTAR
echo echo [INFO] Ejecutando: %%DESCRIPCION%%
echo echo ------------------------------------------------------------
echo if "%%OPCION%%"=="3" ^(
echo     echo Comando: Simular Avería ^(comando especial^)
echo ^) else ^(
echo     echo Comando: %%COMANDO_PS%%
echo ^)
echo echo ------------------------------------------------------------
echo echo.
echo echo.
echo REM Ejecutar el comando de PowerShell
echo if defined OPCION_ESPECIAL ^(
echo     if "%%OPCION_ESPECIAL%%"=="3" ^(
echo         powershell -NoProfile -ExecutionPolicy Bypass -Command "$body = @{activar=$true;motivo='Avería simulada'} | ConvertTo-Json; try { $response = Invoke-WebRequest -Method POST -Uri '%%API_BASE_URL%%/simular_averia' -ContentType 'application/json' -Body $body; $result = $response.Content | ConvertFrom-Json; Write-Host '[ÉXITO]' $result.mensaje -ForegroundColor Green } catch { Write-Host '[ERROR] Error al ejecutar la operación:' -ForegroundColor Red; Write-Host $_.Exception.Message -ForegroundColor Red }"
echo     ^)
echo ^) else ^(
echo     powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $response = %%COMANDO_PS%%; if ($response.StatusCode -eq 200) { $result = $response.Content | ConvertFrom-Json; if ($result.status -eq 'ok') { Write-Host '[ÉXITO]' $result.mensaje -ForegroundColor Green } else { Write-Host '[ADVERTENCIA]' $result.mensaje -ForegroundColor Yellow } } else { Write-Host '[ERROR] Código de respuesta:' $response.StatusCode -ForegroundColor Red } } catch { Write-Host '[ERROR] Error al ejecutar la operación:' -ForegroundColor Red; Write-Host $_.Exception.Message -ForegroundColor Red; if ($_.Exception.Response) { try { $errorBody = $_.Exception.Response.GetResponseStream(); $reader = New-Object System.IO.StreamReader($errorBody); $errorContent = $reader.ReadToEnd() | ConvertFrom-Json; Write-Host 'Detalle:' $errorContent.mensaje -ForegroundColor Red } catch {} } }"
echo ^)
echo.
echo echo.
echo echo Presiona cualquier tecla para volver al menú principal...
echo pause ^>nul
echo goto MENU
echo.
echo endlocal
) > "%TEMP_SCRIPT%"

echo [DEBUG] Script temporal creado: %TEMP_SCRIPT% >> "%LOG_FILE%"

REM Lanzar el menu en una ventana cmd separada
start "Menu_Control_!CP_ID_PARAM!" cmd /k "%TEMP_SCRIPT%"

echo [DEBUG] Menu de Control lanzado para !CP_ID_PARAM! >> "%LOG_FILE%"
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

REM ============================================================
REM  PUNTO DE SEGURIDAD - NO DEBERIA LLEGAR AQUI
REM ============================================================
:ERROR_EXIT
echo.
echo [ERROR] El script ha terminado inesperadamente
echo [ERROR] Revisa el archivo de log para mas detalles
echo.
pause
exit /b 1
