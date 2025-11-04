@echo off
REM ============================================================
REM  SCRIPT DE EJECUCION PARA PC_A (ORDENADOR SERVIDOR CENTRAL)
REM  
REM  Este script ejecuta los componentes del sistema:
REM  - Detecta IP local automaticamente
REM  - Inicia Kafka + MySQL (Docker)
REM  - Inicia EV_Central
REM  - Inicia Dashboard Web
REM  
REM  REQUISITO: Ejecutar PC_A_INSTALL.bat primero
REM ============================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo      PC_A - EJECUCION DE SERVIDOR CENTRAL
echo ============================================================
echo.

REM ============================================================
REM  VERIFICAR INSTALACION PREVIA
REM ============================================================
py --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python NO esta instalado o no esta en PATH.
    echo.
    echo Por favor, ejecuta primero: PC_A_INSTALL.bat
    echo.
    pause
    exit /b 1
)

docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker NO esta instalado.
    echo.
    echo Por favor, ejecuta primero: PC_A_INSTALL.bat
    echo.
    pause
    exit /b 1
)

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

REM ============================================================
REM  PASO 1: DETECTAR IP LOCAL AUTOMATICAMENTE
REM ============================================================
echo ============================================================
echo [1/4] DETECTANDO IP LOCAL
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
REM  PASO 2: INICIAR KAFKA + MYSQL (DOCKER COMPOSE)
REM ============================================================
echo ============================================================
echo [2/4] INICIANDO KAFKA + MYSQL
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
REM  PASO 3: INICIAR EV_CENTRAL
REM ============================================================
echo ============================================================
echo [3/4] INICIANDO EV_CENTRAL
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

REM ============================================================
REM  PASO 4: LANZAR DASHBOARD WEB
REM ============================================================
echo.
echo ============================================================
echo [4/4] LANZANDO DASHBOARD WEB
echo ============================================================
echo.
echo Iniciando dashboard web en puerto 8080...
echo.

REM Lanzar Dashboard Web en nueva ventana
start "Dashboard-Web-PC_A" cmd /k "py web_dashboard.py --kafka !CENTRAL_IP!:9092 --central-ip !CENTRAL_IP! --central-port 5000"

REM Esperar 5 segundos a que el dashboard inicie
echo Esperando a que el dashboard inicie...
timeout /t 5 /nobreak >nul

REM Abrir navegador automáticamente
echo Abriendo navegador en http://localhost:8080 ...
start http://localhost:8080

echo.
echo ============================================================
echo      SISTEMA PC_A INICIADO CORRECTAMENTE
echo ============================================================
echo.
echo Servicios activos:
echo   [X] Kafka           - Puerto 9092
echo   [X] MySQL           - Puerto 3306
echo   [X] EV_Central      - Puerto 5000
echo   [X] Dashboard Web   - http://localhost:8080
echo.
echo Ventanas abiertas:
echo   - EV_Central (logs en ventana separada)
echo   - Dashboard Web (interfaz grafica en navegador)
echo.
echo Archivo generado para PC_B:
echo   - central_ip.txt (IP: !CENTRAL_IP!)
echo.
echo SIGUIENTE PASO:
echo   - En PC_B: Copiar central_ip.txt y ejecutar PC_B_COMPLETO.bat
echo.
echo DASHBOARD WEB:
echo   - URL: http://localhost:8080
echo   - Desde otra red: http://!CENTRAL_IP!:8080
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
echo (Central y Dashboard seguiran corriendo en sus ventanas)
echo.
pause

exit /b 0

