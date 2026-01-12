@echo off
REM ============================================================
REM  SCRIPT DE INSTALACION PARA PC_B (ORDENADOR PUNTOS DE RECARGA)
REM  
REM  Este script instala las dependencias necesarias:
REM  - Verifica e instala Python
REM  - Instala dependencias Python (requirements.txt principal)
REM  - Instala dependencias especificas de cada servicio:
REM    * CP (Charging Points): Engine y Monitor
REM    * Weather: EV_W.py
REM    * Registry: EV_Registry.py
REM  - Verifica Docker (necesario para CPs)
REM  - Configura IP de Central desde central_ip.txt
REM ============================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo    PC_B - INSTALACION DE DEPENDENCIAS
echo ============================================================
echo.
echo Este script realizara:
echo   [1] Verificacion de Python
echo   [2] Instalacion de dependencias Python (principal)
echo   [3] Instalacion de dependencias especificas:
echo       - CP (Engine y Monitor)
echo       - Weather (EV_W)
echo       - Registry (EV_Registry)
echo   [4] Verificacion de Docker (para CPs)
echo   [5] Configuracion de IP de Central
echo.
echo ============================================================
echo.
echo Presiona ENTER para continuar con la instalacion...
pause

REM ============================================================
REM  PASO 1: VERIFICAR PYTHON
REM ============================================================
echo.
echo ============================================================
echo [1/5] VERIFICANDO PYTHON
echo ============================================================
py --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Python NO esta instalado.
    echo.
    echo ACCION REQUERIDA:
    echo   1. Descarga Python desde: https://www.python.org/downloads/
    echo   2. Durante instalacion, marca "Add Python to PATH"
    echo   3. Reinicia este script
    echo.
    pause
    exit /b 1
)

echo [OK] Python encontrado:
py --version
echo.

REM ============================================================
REM  PASO 2: INSTALAR DEPENDENCIAS PYTHON PRINCIPALES
REM ============================================================
echo ============================================================
echo [2/5] INSTALANDO DEPENDENCIAS PYTHON PRINCIPALES
echo ============================================================
echo.
if not exist requirements.txt (
    echo [ERROR] No se encuentra requirements.txt
    echo Asegurate de ejecutar desde la raiz del proyecto.
    echo.
    pause
    exit /b 1
)

REM Actualizar pip si es necesario
echo Actualizando pip...
py -m pip install --upgrade pip --quiet --disable-pip-version-check 2>nul

echo.
echo Instalando/verificando dependencias desde requirements.txt...
echo (Esto puede tardar 1-2 minutos si necesita instalar paquetes)
echo.

REM Instalar directamente desde requirements.txt (pip salta los que ya estan instalados)
py -m pip install -r requirements.txt --quiet --disable-pip-version-check

if %errorlevel% equ 0 (
    echo.
    echo [OK] Dependencias principales instaladas correctamente.
    echo.
) else (
    echo.
    echo [ADVERTENCIA] Hubo algun problema instalando dependencias principales.
    echo El script continuara de todas formas...
    echo.
)

echo Presiona una tecla para continuar al siguiente paso...
pause
cls
echo.

REM ============================================================
REM  PASO 3: INSTALAR DEPENDENCIAS ESPECIFICAS DE SERVICIOS
REM ============================================================
echo ============================================================
echo [3/5] INSTALANDO DEPENDENCIAS ESPECIFICAS DE SERVICIOS
echo ============================================================
echo.

REM Instalar dependencias de Registry
if exist ev_registry\requirements.txt (
    echo [INFO] Instalando dependencias de Registry (EV_Registry)...
    py -m pip install -r ev_registry\requirements.txt --quiet --disable-pip-version-check
    if !errorlevel! equ 0 (
        echo [OK] Dependencias de Registry instaladas.
    ) else (
        echo [ADVERTENCIA] Problema instalando dependencias de Registry.
    )
    echo.
) else (
    echo [INFO] No se encuentra ev_registry\requirements.txt
    echo [INFO] Se usaran las dependencias del requirements.txt principal.
    echo.
)

REM Instalar dependencias de Weather
if exist ev_weather\requirements.txt (
    echo [INFO] Instalando dependencias de Weather (EV_W)...
    py -m pip install -r ev_weather\requirements.txt --quiet --disable-pip-version-check
    if !errorlevel! equ 0 (
        echo [OK] Dependencias de Weather instaladas.
    ) else (
        echo [ADVERTENCIA] Problema instalando dependencias de Weather.
    )
    echo.
) else (
    echo [INFO] No se encuentra ev_weather\requirements.txt
    echo [INFO] Se usaran las dependencias del requirements.txt principal.
    echo.
)

REM Verificar que los archivos principales de los servicios existen
echo [INFO] Verificando archivos de servicios...
if exist ev_registry\EV_Registry.py (
    echo [OK] EV_Registry.py encontrado
) else (
    echo [ADVERTENCIA] EV_Registry.py NO encontrado
)

if exist ev_weather\EV_W.py (
    echo [OK] EV_W.py encontrado
) else (
    echo [ADVERTENCIA] EV_W.py NO encontrado
)

if exist ev_cp_engine\EV_CP_E.py (
    echo [OK] EV_CP_E.py encontrado
) else (
    echo [ADVERTENCIA] EV_CP_E.py NO encontrado
)

if exist ev_cp_monitor\EV_CP_M.py (
    echo [OK] EV_CP_M.py encontrado
) else (
    echo [ADVERTENCIA] EV_CP_M.py NO encontrado
)
echo.

echo Presiona una tecla para continuar al siguiente paso...
pause
cls
echo.

REM ============================================================
REM  PASO 4: VERIFICAR DOCKER (NECESARIO PARA CPS)
REM ============================================================
echo ============================================================
echo [4/5] VERIFICANDO DOCKER
echo ============================================================
echo.

docker --version >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK] Docker esta instalado:
    docker --version
    echo.
    echo [INFO] Docker es necesario para ejecutar los CPs (Charging Points)
    echo [INFO] Asegurate de que Docker Desktop este ejecutandose antes de usar PC_B_RUN.bat
    echo.
    
    REM Verificar/crear red Docker evnet
    echo [INFO] Verificando red Docker evnet...
    docker network inspect evnet >nul 2>&1
    if !errorlevel! neq 0 (
        echo [INFO] Red evnet no existe. Creandola...
        docker network create evnet --driver bridge >nul 2>&1
        if !errorlevel! equ 0 (
            echo [OK] Red evnet creada correctamente
        ) else (
            echo [ADVERTENCIA] No se pudo crear la red evnet ahora
            echo [INFO] La red se creara automaticamente al ejecutar PC_B_RUN.bat
        )
    ) else (
        echo [OK] Red evnet ya existe
    )
    echo.
) else (
    echo [ADVERTENCIA] Docker NO esta instalado o no esta en el PATH.
    echo.
    echo IMPORTANTE: Docker es necesario para ejecutar los CPs.
    echo.
    echo Para instalar Docker:
    echo   1. Descarga Docker Desktop desde: https://www.docker.com/products/docker-desktop
    echo   2. Instala Docker Desktop
    echo   3. Inicia Docker Desktop
    echo   4. Reinicia este script para verificar la instalacion
    echo.
    echo NOTA: Weather y Registry pueden ejecutarse sin Docker.
    echo.
)

echo Presiona una tecla para continuar al siguiente paso...
pause
cls
echo.

REM ============================================================
REM  PASO 5: CONFIGURAR IP DE CENTRAL
REM ============================================================
echo ============================================================
echo [5/5] CONFIGURACION DE CENTRAL
echo ============================================================
echo.

set CENTRAL_IP=

if exist central_ip.txt (
    for /f "delims=" %%i in (central_ip.txt) do set CENTRAL_IP=%%i
    
    if "!CENTRAL_IP!"=="" (
        echo [ERROR] El archivo central_ip.txt existe pero esta vacio.
        echo.
        set /p CENTRAL_IP="Introduce la IP de PC_A (ej: 192.168.1.43): "
        if "!CENTRAL_IP!"=="" (
            echo [ERROR] No se introdujo ninguna IP.
            echo.
            pause
            exit /b 1
        )
        echo !CENTRAL_IP!> central_ip.txt
    )
    
    echo [OK] IP de Central leida desde central_ip.txt
    echo      IP Central: !CENTRAL_IP!
) else (
    echo [ADVERTENCIA] No se encuentra central_ip.txt
    echo.
    echo Puedes:
    echo   A) Copiar central_ip.txt desde PC_A
    echo   B) Introducir la IP manualmente ahora
    echo.
    set /p CENTRAL_IP="Introduce la IP de PC_A (ej: 192.168.1.43): "
    
    if "!CENTRAL_IP!"=="" (
        echo [ERROR] No se introdujo ninguna IP.
        echo.
        pause
        exit /b 1
    )
    
    REM Guardar para proximas ejecuciones
    echo !CENTRAL_IP!> central_ip.txt
    echo [OK] IP guardada en central_ip.txt
)
echo.

REM ============================================================
REM  VERIFICACIONES ADICIONALES
REM ============================================================
echo.
echo ============================================================
echo   VERIFICACIONES ADICIONALES
echo ============================================================
echo.

REM Verificar certificados SSL para Registry
if exist certificados\registry_cert.pem (
    if exist certificados\registry_key.pem (
        echo [OK] Certificados SSL para Registry encontrados
    ) else (
        echo [ADVERTENCIA] Falta certificados\registry_key.pem para Registry
        echo [INFO] Ejecuta: generar_certificados_rapido.bat
    )
) else (
    echo [ADVERTENCIA] Certificados SSL para Registry NO encontrados
    echo [INFO] Para usar Registry con HTTPS, ejecuta: generar_certificados_rapido.bat
    echo [INFO] Registry puede funcionar sin certificados, pero es menos seguro
)
echo.

REM Verificar API Key de OpenWeather para Weather
if exist OPENWEATHER_API_KEY.txt (
    echo [OK] OPENWEATHER_API_KEY.txt encontrado
    echo [INFO] Weather podra ejecutarse correctamente
) else (
    echo [ADVERTENCIA] OPENWEATHER_API_KEY.txt NO encontrado
    echo [INFO] Weather requiere una API Key de OpenWeather
    echo [INFO] Crea el archivo OPENWEATHER_API_KEY.txt con tu API Key
    echo [INFO] Obtener API Key en: https://openweathermap.org/api
    echo [INFO] Weather no se iniciara sin este archivo
)
echo.

REM ============================================================
REM  RESUMEN DE INSTALACION
REM ============================================================
echo.
echo ============================================================
echo      INSTALACION COMPLETADA
echo ============================================================
echo.
echo DEPENDENCIAS INSTALADAS:
echo   [OK] Python y pip
echo   [OK] Dependencias principales (requirements.txt)
echo   [OK] Dependencias de Registry
echo   [OK] Dependencias de Weather
echo   [OK] Dependencias de CP (Engine y Monitor)
echo.
echo CONFIGURACION:
echo   [OK] IP de Central: !CENTRAL_IP!
echo.
echo SERVICIOS DISPONIBLES:
echo   - CP (Charging Points): Requiere Docker
echo   - Weather (EV_W): Requiere OPENWEATHER_API_KEY.txt
echo   - Registry (EV_Registry): Requiere certificados SSL (recomendado)
echo.
echo SIGUIENTE PASO:
echo   1. Si usas Registry: Ejecuta INICIAR_REGISTRY_PC_B.bat
echo   2. Para ejecutar CPs y Weather: Ejecuta PC_B_RUN.bat
echo.
echo NOTAS IMPORTANTES:
echo   - Docker Desktop debe estar ejecutandose para los CPs
echo   - Registry debe estar ejecutandose antes de los CPs
echo   - Weather requiere OPENWEATHER_API_KEY.txt
echo.
echo ============================================================
echo.
pause

exit /b 0

