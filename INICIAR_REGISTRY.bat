@echo off
REM ========================================================================
REM  SCRIPT PARA INICIAR SOLO EV_Registry
REM ========================================================================
REM  Este script inicia EV_Registry que es necesario para que los CPs
REM  puedan registrarse antes de conectarse a EV_Central.
REM ========================================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ========================================================================
echo   INICIANDO EV_Registry
echo ========================================================================
echo.

REM ============================================================
REM  PASO 1: DETECTAR IP DE BASE DE DATOS
REM ============================================================
echo [1/3] DETECTANDO IP DE BASE DE DATOS
echo.

REM Detectar IP de la base de datos (Central)
REM Si se ejecuta en PC_A, usa localhost. Si se ejecuta en PC_B/PC_C, usa la IP de PC_A
set CENTRAL_IP_BD=127.0.0.1
if exist "central_ip.txt" (
    for /f "tokens=*" %%i in (central_ip.txt) do set CENTRAL_IP_BD=%%i
    echo [OK] IP de BD detectada desde central_ip.txt: !CENTRAL_IP_BD!
    echo [INFO] Si Registry está en PC_B/PC_C, se conectará a BD en PC_A
    echo [INFO] Si Registry está en PC_A, se conectará a BD local
) else (
    echo [INFO] No se encuentra central_ip.txt. Usando localhost (127.0.0.1)
    echo [INFO] Si estás en PC_B/PC_C, asegúrate de copiar central_ip.txt desde PC_A
)
echo.

echo [INFO] Configuración:
echo   - Base de datos: !CENTRAL_IP_BD!:3306
echo   - Base de datos: evcharging
echo   - Puerto Registry: 6000
echo.

REM ============================================================
REM  PASO 2: VERIFICAR CONEXIÓN A BASE DE DATOS
REM ============================================================
echo [2/3] VERIFICANDO CONEXIÓN A BASE DE DATOS
echo.

echo Verificando que MySQL está accesible en !CENTRAL_IP_BD!:3306...
echo (Esto puede tardar unos segundos)
echo.

REM Verificar conexión usando Python - método más robusto
python -c "import sys; import mysql.connector; conn = mysql.connector.connect(host='!CENTRAL_IP_BD!', port=3306, user='root', password='root', database='evcharging', connection_timeout=5); conn.close(); sys.exit(0)" 2>nul
set MYSQL_CHECK_RESULT=%errorlevel%

if !MYSQL_CHECK_RESULT! neq 0 (
    echo [ERROR] No se pudo conectar a MySQL en !CENTRAL_IP_BD!:3306
    echo.
    echo VERIFICA:
    echo   1. PC_A_RUN.bat está ejecutándose (MySQL debe estar activo)
    echo   2. MySQL está activo en PC_A
    echo   3. Firewall en PC_A permite conexiones al puerto 3306
    echo   4. La IP !CENTRAL_IP_BD! es correcta
    echo   5. central_ip.txt contiene la IP correcta de PC_A
    echo.
    echo Comando para abrir firewall en PC_A (ejecutar en PowerShell como Admin):
    echo   New-NetFirewallRule -DisplayName "MySQL" -Direction Inbound -LocalPort 3306 -Protocol TCP -Action Allow
    echo.
    pause
    exit /b 1
)

echo [OK] MySQL está accesible en !CENTRAL_IP_BD!:3306
echo [OK] Conexión a base de datos verificada correctamente
echo.

REM ============================================================
REM  PASO 3: VERIFICAR CERTIFICADOS SSL (OBLIGATORIO)
REM ============================================================
echo [3/3] VERIFICANDO CERTIFICADOS SSL
echo.

REM Verificar si hay certificados SSL válidos (OBLIGATORIO)
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

REM SSL es OBLIGATORIO - si no hay certificados, generar o error
if !USE_SSL! equ 1 (
    echo [OK] Certificados SSL encontrados y válidos:
    echo   - Certificado: certificados\registry_cert.pem (!CERT_SIZE! bytes)
    echo   - Clave privada: certificados\registry_key.pem (!KEY_SIZE! bytes)
    echo.
    echo [INFO] Iniciando EV_Registry con HTTPS (SSL obligatorio)...
    echo.
    start "EV_Registry" cmd /k "python ev_registry\EV_Registry.py --db-host !CENTRAL_IP_BD! --db-port 3306 --db-user root --db-password root --db-name evcharging --port 6000 --ssl --ssl-cert certificados\registry_cert.pem --ssl-key certificados\registry_key.pem"
    echo [OK] EV_Registry iniciado con HTTPS (puerto 6000)
    echo   - API REST: https://localhost:6000/api
    echo   - Conectado a BD en: !CENTRAL_IP_BD!:3306
    goto :registry_started
)

REM Si no hay certificados, ERROR (SSL es obligatorio)
echo [ERROR] Certificados SSL NO encontrados o inválidos
echo.
echo SSL es OBLIGATORIO para el sistema. Debes generar los certificados.
echo.
echo OPCIONES:
echo   1. Ejecutar: generar_certificados_rapido.bat
echo   2. O ejecutar: generar_certificados_ssl.bat
echo.
echo Archivos requeridos en certificados\:
echo   - registry_cert.pem (certificado)
echo   - registry_key.pem  (clave privada)
echo.
pause
exit /b 1

:registry_started

echo.
echo ========================================================================
echo   EV_Registry INICIADO CORRECTAMENTE
echo ========================================================================
echo.
echo [CONFIGURACIÓN]
echo   - Puerto: 6000
echo   - Protocolo: HTTPS (SSL obligatorio)
echo   - API REST: https://localhost:6000/api
echo   - Base de datos: !CENTRAL_IP_BD!:3306/evcharging
echo.
echo [IMPORTANTE] 
echo   - Espera unos segundos a que EV_Registry se inicie completamente
echo   - Antes de ejecutar los CPs, verifica que Registry esté respondiendo
echo   - Los CPs deben usar HTTPS para conectarse al Registry
echo.
echo [VERIFICAR CONEXIÓN]
echo   Desde otro terminal, prueba:
echo   curl -k https://localhost:6000/api/health
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
echo (EV_Registry seguirá corriendo en su ventana separada)
pause >nul

