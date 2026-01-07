@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ========================================================================
echo   INICIANDO EV_Registry (MODO LOCAL - PC A)
echo ========================================================================

REM --- 1. INSTALACION DE DEPENDENCIAS ---
echo [1/4] Verificando librerias Python...
pip install flask mysql-connector-python requests cryptography pyopenssl >nul 2>&1
if !errorlevel! neq 0 (
    echo [INFO] Instalando librerias faltantes...
    pip install flask mysql-connector-python requests cryptography pyopenssl
)

REM --- 2. CONFIGURACION DE RED ---
REM Al estar en el PC A, la base de datos es LOCALHOST
REM Modo desarrollo: usar root sin restricciones
set DB_HOST=127.0.0.1
set DB_PORT=3306
set DB_USER=root
set DB_PASS=
set DB_NAME=evcharging

REM Usamos comillas en el echo para evitar error por parentesis
echo [OK] Configurado para conectar a BD Local "127.0.0.1:3306"

REM --- 3. VERIFICAR CONEXION A BASE DE DATOS ---
echo [2/4] Probando conexion con MariaDB...

REM Simplificamos el comando docker para evitar errores de sintaxis con llaves {{.}}
docker ps | findstr "mariadb" >nul

if !errorlevel! neq 0 (
    echo [ERROR] Contenedor MariaDB no esta corriendo.
    echo Causas posibles:
    echo   1. Docker no esta corriendo.
    echo   2. Contenedor mariadb no existe o no esta activo.
    echo   3. Ejecuta PC_A_RUN.bat primero.
    pause
    exit /b 1
) else (
    echo [OK] Contenedor MariaDB detectado y corriendo.
)

REM --- 4. VERIFICAR CERTIFICADOS SSL (OBLIGATORIO RELEASE 2) ---
echo [3/4] Verificando certificados SSL...
set SSL_CMD=

if exist "certificados\registry_cert.pem" (
    if exist "certificados\registry_key.pem" (
        echo [OK] Certificados encontrados. Activando HTTPS.
        set SSL_CMD=--ssl --ssl-cert certificados\registry_cert.pem --ssl-key certificados\registry_key.pem
    ) else (
        echo [ADVERTENCIA] Falta la clave privada (registry_key.pem). Se usara HTTP inseguro.
    )
) else (
    echo [ADVERTENCIA] No se encuentran certificados en la carpeta certificados.
    echo [INFO] Se iniciara en modo HTTP (INSEGURO).
    echo Para cumplir la Release 2, genera los certificados.
)

REM --- 5. EJECUTAR REGISTRY ---
echo [4/4] Lanzando EV_Registry...
echo.
echo ------------------------------------------------------------------------
echo   La aplicacion se abrira en una NUEVA ventana.
echo   Si esa ventana muestra errores, no se cerrara automaticamente.
echo ------------------------------------------------------------------------

REM Comando para lanzar Python.
start "EV_Registry (PC A)" cmd /k "python ev_registry\EV_Registry.py --db-host !DB_HOST! --db-port !DB_PORT! --db-user !DB_USER! --db-password !DB_PASS! --db-name !DB_NAME! --port 6000 !SSL_CMD!"

echo [EXITO] Script finalizado. Revisa la nueva ventana.
pause