@echo off
REM ========================================================================
REM  SCRIPT PARA REINICIAR EV_Registry CON HTTPS
REM ========================================================================

echo ========================================================================
echo   REINICIANDO EV_Registry CON HTTPS
echo ========================================================================
echo.

REM Detectar IP de la base de datos (Central)
set CENTRAL_IP_BD=127.0.0.1
if exist "central_ip.txt" (
    for /f "tokens=*" %%i in (central_ip.txt) do set CENTRAL_IP_BD=%%i
)

REM Detener procesos existentes de EV_Registry
echo [1/3] Deteniendo procesos existentes de EV_Registry...
taskkill /FI "WINDOWTITLE eq EV_Registry*" /F >nul 2>&1
timeout /t 2 /nobreak >nul

REM Verificar certificados
echo [2/3] Verificando certificados SSL...
if not exist "certificados\registry_cert.pem" (
    echo [ERROR] No se encuentra el certificado: certificados\registry_cert.pem
    echo Ejecuta: generar_certificados_ssl.bat
    pause
    exit /b 1
)

if not exist "certificados\registry_key.pem" (
    echo [ERROR] No se encuentra la clave privada: certificados\registry_key.pem
    echo Ejecuta: generar_certificados_ssl.bat
    pause
    exit /b 1
)

echo [OK] Certificados encontrados

REM Iniciar EV_Registry con HTTPS
echo [3/3] Iniciando EV_Registry con HTTPS...
echo.
start "EV_Registry" cmd /k "python ev_registry\EV_Registry.py --db-host %CENTRAL_IP_BD% --db-port 3306 --db-user root --db-password root --db-name evcharging --port 6000 --ssl --ssl-cert certificados\registry_cert.pem --ssl-key certificados\registry_key.pem"

echo [OK] EV_Registry iniciado con HTTPS (puerto 6000)
echo   - API REST: https://localhost:6000/api
echo.
echo ========================================================================
echo   EV_Registry reiniciado en ventana separada
echo ========================================================================
echo.
echo [IMPORTANTE] Espera unos segundos a que EV_Registry se inicie completamente
echo   antes de ejecutar los CPs.
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
pause >nul

