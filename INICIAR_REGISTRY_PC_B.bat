@echo off
REM ========================================================================
REM  SCRIPT PARA INICIAR EV_Registry EN PC_B
REM ========================================================================
REM  Este script inicia EV_Registry en PC_B conectándose a la BD en PC_A
REM  
REM  REQUISITOS:
REM  1. PC_A_RUN.bat debe estar ejecutándose (MySQL debe estar activo)
REM  2. central_ip.txt debe existir con la IP de PC_A
REM  3. Certificados SSL deben estar en certificados\
REM ========================================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ========================================================================
echo   INICIANDO EV_Registry EN PC_B
echo ========================================================================
echo.

REM ============================================================
REM  PASO 1: DETECTAR IP DE PC_A (BASE DE DATOS)
REM ============================================================
echo [1/3] DETECTANDO IP DE PC_A (BASE DE DATOS)
echo.

set CENTRAL_IP_BD=127.0.0.1
if exist "central_ip.txt" (
    for /f "tokens=*" %%i in (central_ip.txt) do set CENTRAL_IP_BD=%%i
    echo [OK] IP de PC_A detectada desde central_ip.txt: !CENTRAL_IP_BD!
) else (
    echo [ADVERTENCIA] No se encuentra central_ip.txt
    echo.
    echo Por favor, ingresa la IP de PC_A manualmente:
    set /p CENTRAL_IP_BD="IP de PC_A (Base de datos): "
    if "!CENTRAL_IP_BD!"=="" (
        echo [ERROR] IP no proporcionada. Usando 192.168.1.43 por defecto
        set CENTRAL_IP_BD=192.168.1.43
    )
)

echo.
echo [INFO] Configuración:
echo   - Base de datos: !CENTRAL_IP_BD!:3306 (PC_A)
echo   - Base de datos: evcharging
echo   - Puerto Registry: 6000 (PC_B)
echo.

REM ============================================================
REM  PASO 2: VERIFICAR CONEXIÓN A BASE DE DATOS
REM ============================================================
echo [2/3] VERIFICANDO CONEXIÓN A BASE DE DATOS
echo.

echo Verificando que MySQL está accesible en !CENTRAL_IP_BD!:3306...
echo (Esto puede tardar unos segundos)
echo.

REM Intentar conectar (usando Python para verificar)
python -c "import mysql.connector; conn = mysql.connector.connect(host='!CENTRAL_IP_BD!', port=3306, user='root', password='root', database='evcharging', connection_timeout=5); print('[OK] Conexión a MySQL exitosa'); conn.close()" 2>nul

if %errorlevel% neq 0 (
    echo [ERROR] No se pudo conectar a MySQL en !CENTRAL_IP_BD!:3306
    echo.
    echo VERIFICA:
    echo   1. PC_A_RUN.bat está ejecutándose
    echo   2. MySQL está activo en PC_A
    echo   3. Firewall en PC_A permite conexiones al puerto 3306
    echo   4. La IP !CENTRAL_IP_BD! es correcta
    echo.
    echo Comando para abrir firewall en PC_A (ejecutar en PowerShell como Admin):
    echo   New-NetFirewallRule -DisplayName "MySQL" -Direction Inbound -LocalPort 3306 -Protocol TCP -Action Allow
    echo.
    pause
    exit /b 1
)

echo [OK] MySQL está accesible en !CENTRAL_IP_BD!:3306
echo.

REM ============================================================
REM  PASO 3: INICIAR EV_Registry
REM ============================================================
echo [3/3] INICIANDO EV_Registry
echo.

REM Verificar si hay certificados SSL válidos
set USE_SSL=0
set CERT_SIZE=0
set KEY_SIZE=0
if exist "certificados\registry_cert.pem" (
    if exist "certificados\registry_key.pem" (
        REM Verificar que los archivos no estén vacíos
        for %%A in ("certificados\registry_cert.pem") do set CERT_SIZE=%%~zA
        for %%B in ("certificados\registry_key.pem") do set KEY_SIZE=%%~zB
        if !CERT_SIZE! gtr 0 (
            if !KEY_SIZE! gtr 0 (
                set USE_SSL=1
            )
        )
    )
)

REM Ejecutar solo una rama usando goto
if !USE_SSL! equ 1 (
    echo [INFO] Certificados SSL encontrados. Iniciando con HTTPS...
    echo.
    start "EV_Registry-PC_B" cmd /k "python ev_registry\EV_Registry.py --db-host !CENTRAL_IP_BD! --db-port 3306 --db-user root --db-password root --db-name evcharging --port 6000 --ssl --ssl-cert certificados\registry_cert.pem --ssl-key certificados\registry_key.pem"
    echo [OK] EV_Registry iniciado con HTTPS (puerto 6000)
    echo   - API REST: https://localhost:6000/api
    echo   - Conectado a BD en: !CENTRAL_IP_BD!:3306
    goto :registry_started
)

echo [INFO] No se encontraron certificados SSL válidos. Iniciando con HTTP...
echo [ADVERTENCIA] Para usar HTTPS, ejecuta: generar_certificados_rapido.bat
echo.
start "EV_Registry-PC_B" cmd /k "python ev_registry\EV_Registry.py --db-host !CENTRAL_IP_BD! --db-port 3306 --db-user root --db-password root --db-name evcharging --port 6000"
echo [OK] EV_Registry iniciado con HTTP (puerto 6000)
echo   - API REST: http://localhost:6000/api
echo   - Conectado a BD en: !CENTRAL_IP_BD!:3306

:registry_started

echo.
echo ========================================================================
echo   EV_Registry INICIADO EN PC_B
echo ========================================================================
echo.
echo [IMPORTANTE] 
echo   - Registry está corriendo en este PC (PC_B)
echo   - Conectado a BD en PC_A (!CENTRAL_IP_BD!)
echo   - Puerto: 6000
echo.
echo [CONFIGURACIÓN REQUERIDA EN PC_B]
echo   Antes de ejecutar el Monitor, configura:
echo   set REGISTRY_URL=https://127.0.0.1:6000/api
echo.
echo   O si usas HTTP:
echo   set REGISTRY_URL=http://127.0.0.1:6000/api
echo.
echo [FIREWALL]
echo   Si otros PCs necesitan acceder a Registry, abre el puerto 6000:
echo   New-NetFirewallRule -DisplayName "EV_Registry" -Direction Inbound -LocalPort 6000 -Protocol TCP -Action Allow
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
pause >nul

