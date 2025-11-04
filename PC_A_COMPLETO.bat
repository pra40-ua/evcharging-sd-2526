@echo off
REM ============================================================
REM  SCRIPT COMPLETO PARA PC_A (ORDENADOR SERVIDOR CENTRAL)
REM  
REM  Este script hace TODO lo necesario:
REM  - Verifica e instala Python
REM  - Instala dependencias (pip packages)
REM  - Verifica Docker
REM  - Arranca Kafka + MySQL + Central
REM  - Genera archivo central_ip.txt para PC_B
REM ============================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo      PC_A - SERVIDOR CENTRAL (SCRIPT COMPLETO)
echo ============================================================
echo.
echo Este script realizara:
echo   [1] Verificacion de Python
echo   [2] Instalacion de dependencias Python
echo   [3] Verificacion de Docker
echo   [4] Inicio de Kafka + MySQL (Docker)
echo   [5] Deteccion de IP local
echo   [6] Inicio de EV_Central
echo.
pause

REM ============================================================
REM  PASO 1: VERIFICAR PYTHON
REM ============================================================
echo.
echo ============================================================
echo [1/6] VERIFICANDO PYTHON
echo ============================================================
python --version >nul 2>&1
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
python --version
echo.

REM ============================================================
REM  PASO 2: INSTALAR DEPENDENCIAS PYTHON
REM ============================================================
echo ============================================================
echo [2/6] VERIFICANDO/INSTALANDO DEPENDENCIAS PYTHON
echo ============================================================
echo.
if not exist requirements.txt (
    echo [ERROR] No se encuentra requirements.txt
    echo Asegurate de ejecutar desde la raiz del proyecto.
    pause
    exit /b 1
)

REM Actualizar pip si es necesario
echo Actualizando pip...
python -m pip install --upgrade pip --quiet --disable-pip-version-check 2>nul

echo.
echo Verificando dependencias...
echo.

REM Leer requirements.txt y verificar cada paquete
set PACKAGES_TO_INSTALL=
set ALL_OK=1

for /F "tokens=1 delims==#" %%p in (requirements.txt) do (
    set PACKAGE=%%p
    set PACKAGE=!PACKAGE: =!
    
    REM Saltar líneas vacías y comentarios
    if not "!PACKAGE!"=="" if not "!PACKAGE:~0,1!"=="#" (
        REM Extraer nombre del paquete (sin versión)
        for /F "tokens=1 delims==<>!" %%n in ("!PACKAGE!") do (
            set PKG_NAME=%%n
            
            REM Verificar si el paquete ya está instalado
            python -m pip show !PKG_NAME! >nul 2>&1
            if !errorlevel! equ 0 (
                echo   [OK] !PKG_NAME! - Ya instalado
            ) else (
                echo   [--] !PKG_NAME! - Necesita instalarse
                set PACKAGES_TO_INSTALL=!PACKAGES_TO_INSTALL! !PACKAGE!
                set ALL_OK=0
            )
        )
    )
)

echo.

REM Si hay paquetes por instalar, instalarlos
if !ALL_OK! equ 0 (
    echo Instalando paquetes faltantes...
    echo (Esto puede tardar 1-2 minutos)
    echo.
    
    for %%p in (!PACKAGES_TO_INSTALL!) do (
        echo Instalando %%p...
        python -m pip install "%%p" --quiet --disable-pip-version-check
        if !errorlevel! equ 0 (
            echo   [OK] %%p instalado correctamente
        ) else (
            echo   [ERROR] No se pudo instalar %%p
        )
    )
    echo.
    echo [OK] Instalacion completada.
) else (
    echo [OK] Todas las dependencias ya estan instaladas.
)
echo.

REM ============================================================
REM  PASO 3: VERIFICAR DOCKER
REM ============================================================
echo ============================================================
echo [3/6] VERIFICANDO DOCKER
echo ============================================================
echo.
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker NO esta instalado.
    echo.
    echo ACCION REQUERIDA:
    echo   1. Descarga Docker Desktop: https://www.docker.com/products/docker-desktop/
    echo   2. Instala Docker Desktop
    echo   3. Reinicia el ordenador
    echo   4. Inicia Docker Desktop
    echo   5. Ejecuta este script nuevamente
    echo.
    pause
    exit /b 1
)

echo [OK] Docker encontrado:
docker --version
echo.

REM Verificar que Docker esta corriendo
docker ps >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker esta instalado pero NO esta corriendo.
    echo.
    echo ACCION REQUERIDA:
    echo   1. Inicia Docker Desktop
    echo   2. Espera a ver "Docker Desktop is running"
    echo   3. Ejecuta este script nuevamente
    echo.
    pause
    exit /b 1
)

echo [OK] Docker daemon esta corriendo.
echo.

REM ============================================================
REM  PASO 4: DETECTAR IP LOCAL AUTOMATICAMENTE
REM ============================================================
echo ============================================================
echo [4/6] DETECTANDO IP LOCAL
echo ============================================================
echo.

REM Detectar IP local usando ipconfig
echo Detectando IP local automaticamente...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /C:"IPv4" ^| findstr /V "127.0.0.1" ^| findstr /V "169.254"') do (
    set TEMP_IP=%%a
    set TEMP_IP=!TEMP_IP: =!
    if not "!TEMP_IP!"=="" (
        set CENTRAL_IP=!TEMP_IP!
        goto :ip_found
    )
)

:ip_found
if "!CENTRAL_IP!"=="" (
    echo [ERROR] No se pudo detectar la IP local.
    echo Usando IP por defecto: 192.168.1.43
    set CENTRAL_IP=192.168.1.43
)

echo [OK] IP detectada: !CENTRAL_IP!

REM Guardar IP en central_ip.txt para PC_B
echo !CENTRAL_IP!> central_ip.txt
echo      IP guardada en central_ip.txt para PC_B
echo.
echo NOTA: Asegurate de actualizar manualmente docker-compose.yml
echo       con esta IP en KAFKA_ADVERTISED_LISTENERS si es necesario.
echo.

REM ============================================================
REM  PASO 5: INICIAR KAFKA + MYSQL (DOCKER COMPOSE)
REM ============================================================
echo ============================================================
echo [5/6] INICIANDO KAFKA + MYSQL
echo ============================================================
echo.
if not exist docker-compose.yml (
    echo [ERROR] No se encuentra docker-compose.yml
    pause
    exit /b 1
)

echo Deteniendo contenedores previos (si existen)...
docker compose down >nul 2>&1

echo.
echo Iniciando Kafka + MySQL + configuracion automatica...
echo (Esto puede tardar 30-60 segundos la primera vez)
echo.
docker compose up -d

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] No se pudo iniciar Docker Compose.
    echo Verifica los logs: docker compose logs
    pause
    exit /b 1
)

echo.
echo [OK] Servicios Docker iniciados.
echo.
echo Esperando a que Kafka y MySQL esten listos...
echo (30 segundos)

REM Esperar con progreso visual
for /L %%i in (1,1,30) do (
    echo|set /p="."
    timeout /t 1 /nobreak >nul
)
echo.
echo.

REM Verificar que Kafka responde
docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092 >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Kafka esta listo y respondiendo.
) else (
    echo [ADVERTENCIA] Kafka puede no estar listo aun.
    echo El sistema continuara de todas formas.
)
echo.

REM ============================================================
REM  PASO 6: INICIAR EV_CENTRAL
REM ============================================================
echo ============================================================
echo [6/6] INICIANDO EV_CENTRAL
echo ============================================================
echo.
echo CONFIGURACION DETECTADA:
echo   - IP de este PC:    !CENTRAL_IP!
echo   - Kafka:            !CENTRAL_IP!:9092
echo   - MySQL:            127.0.0.1:3306
echo   - Puerto Central:   5000
echo.
echo IMPORTANTE PARA RED LOCAL:
echo   Si PC_B esta en otro ordenador, asegurate de:
echo   1. Copiar central_ip.txt a PC_B
echo   2. Abrir firewall para puertos: 5000, 9092, 3306
echo.
echo Comandos Firewall (ejecutar en PowerShell como Admin):
echo   New-NetFirewallRule -DisplayName "Kafka" -Direction Inbound -LocalPort 9092 -Protocol TCP -Action Allow
echo   New-NetFirewallRule -DisplayName "Central" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow
echo   New-NetFirewallRule -DisplayName "MySQL" -Direction Inbound -LocalPort 3306 -Protocol TCP -Action Allow
echo.
pause

REM Lanzar Central en nueva ventana de PowerShell
echo.
echo Lanzando EV_Central en nueva ventana...
echo.
start "EV_Central-PC_A" powershell -NoLogo -NoExit -ExecutionPolicy Bypass -File "%~dp0commands_PC_A.ps1"

REM Esperar un poco para que la Central arranque
timeout /t 3 /nobreak >nul

echo.
echo ============================================================
echo      SISTEMA PC_A INICIADO CORRECTAMENTE
echo ============================================================
echo.
echo Servicios activos:
echo   [X] Kafka           - Puerto 9092
echo   [X] MySQL           - Puerto 3306
echo   [X] EV_Central      - Puerto 5000
echo.
echo Ventana abierta:
echo   - EV_Central (logs en ventana separada)
echo.
echo Archivo generado para PC_B:
echo   - central_ip.txt (IP: !CENTRAL_IP!)
echo.
echo SIGUIENTE PASO:
echo   - En PC_B: Copiar central_ip.txt y ejecutar PC_B_COMPLETO.bat
echo   - Para dashboard: python web_dashboard.py --kafka !CENTRAL_IP!:9092
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
echo (La Central seguira corriendo en la otra ventana)
echo.
pause >nul

exit /b 0

