@echo off
REM ========================================================================
REM  SCRIPT PARA INICIAR SOLO EV_Registry
REM ========================================================================
REM  Este script inicia EV_Registry que es necesario para que los CPs
REM  puedan registrarse antes de conectarse a EV_Central.
REM ========================================================================

echo ========================================================================
echo   INICIANDO EV_Registry
echo ========================================================================
echo.

REM Detectar IP de la base de datos (Central)
set CENTRAL_IP_BD=127.0.0.1
if exist "central_ip.txt" (
    for /f "tokens=*" %%i in (central_ip.txt) do set CENTRAL_IP_BD=%%i
)

echo [INFO] Configuración:
echo   - Base de datos: %CENTRAL_IP_BD%:3306
echo   - Base de datos: evcharging
echo   - Puerto Registry: 6000
echo.

REM Verificar si hay certificados SSL válidos
set USE_SSL=0
if exist "certificados\registry_cert.pem" (
    if exist "certificados\registry_key.pem" (
        REM Verificar que los archivos no estén vacíos
        for %%A in ("certificados\registry_cert.pem") do if %%~zA gtr 0 (
            for %%B in ("certificados\registry_key.pem") do if %%~zB gtr 0 (
                set USE_SSL=1
            )
        )
    )
)

if %USE_SSL% equ 1 (
    echo [INFO] Certificados SSL encontrados. Intentando iniciar con HTTPS...
    echo [ADVERTENCIA] Si falla SSL, se iniciará automáticamente con HTTP
    echo.
    REM Intentar con SSL primero, pero si falla, el usuario puede ejecutar sin SSL
    start "EV_Registry" cmd /k "python ev_registry\EV_Registry.py --db-host %CENTRAL_IP_BD% --db-port 3306 --db-user root --db-password root --db-name evcharging --port 6000 --ssl --ssl-cert certificados\registry_cert.pem --ssl-key certificados\registry_key.pem || python ev_registry\EV_Registry.py --db-host %CENTRAL_IP_BD% --db-port 3306 --db-user root --db-password root --db-name evcharging --port 6000"
    echo [OK] EV_Registry iniciado (intentando HTTPS, fallback a HTTP si falla)
    echo   - API REST: https://localhost:6000/api (o http://localhost:6000/api si SSL falla)
) else (
    echo [INFO] No se encontraron certificados SSL válidos. Iniciando con HTTP...
    echo [ADVERTENCIA] Para usar HTTPS, ejecuta: generar_certificados_ssl.bat
    echo.
    start "EV_Registry" cmd /k "python ev_registry\EV_Registry.py --db-host %CENTRAL_IP_BD% --db-port 3306 --db-user root --db-password root --db-name evcharging --port 6000"
    echo [OK] EV_Registry iniciado con HTTP (puerto 6000)
    echo   - API REST: http://localhost:6000/api
)

echo.
echo ========================================================================
echo   EV_Registry iniciado en ventana separada
echo ========================================================================
echo.
echo [IMPORTANTE] Espera unos segundos a que EV_Registry se inicie completamente
echo   antes de ejecutar los CPs.
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
pause >nul

