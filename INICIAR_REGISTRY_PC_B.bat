@echo off
REM ========================================================================
REM  SCRIPT PARA INICIAR EV_Registry EN PC_B
REM ========================================================================
REM  Este script inicia EV_Registry en PC_B para que los CPs puedan
REM  registrarse antes de conectarse a EV_Central en PC_A.
REM ========================================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ========================================================================
echo   INICIANDO EV_Registry EN PC_B
echo ========================================================================
echo.

REM ============================================================
REM  PASO 1: DETECTAR IP DE BASE DE DATOS (PC_A)
REM ============================================================
echo [1/3] DETECTANDO IP DE BASE DE DATOS EN PC_A
echo.

REM Leer IP de PC_A desde central_ip.txt
set CENTRAL_IP_BD=
if exist central_ip.txt (
    for /f "tokens=*" %%i in (central_ip.txt) do set CENTRAL_IP_BD=%%i
    echo [OK] IP de BD ^(PC_A^) detectada desde central_ip.txt: !CENTRAL_IP_BD!
    goto :ip_found
)

echo [ERROR] No se encuentra central_ip.txt
echo.
echo Debes copiar el archivo central_ip.txt desde PC_A a este directorio.
echo El archivo se genera automaticamente cuando ejecutas PC_A_RUN.bat
echo.
pause
exit /b 1

:ip_found
echo.

echo [INFO] Configuracion:
echo   - Base de datos en PC_A: !CENTRAL_IP_BD!:3306
echo   - Database: evcharging
echo   - Puerto Registry: 6000
echo.

REM ============================================================
REM  PASO 2: VERIFICAR CONEXIÓN A BASE DE DATOS EN PC_A
REM ============================================================
echo [2/3] VERIFICANDO CONEXIÓN A BASE DE DATOS EN PC_A
echo.

echo Verificando que MySQL en PC_A esta accesible ^(!CENTRAL_IP_BD!:3306^)...
echo ^(Esto puede tardar unos segundos^)
echo.

REM Verificar conexión usando Python
python -c "import sys; import mysql.connector; conn = mysql.connector.connect(host='!CENTRAL_IP_BD!', port=3306, user='root', password='root', database='evcharging', connection_timeout=5); conn.close(); sys.exit(0)" 2>nul
set MYSQL_CHECK_RESULT=%errorlevel%

if !MYSQL_CHECK_RESULT! neq 0 (
    echo [ERROR] No se pudo conectar a MySQL en PC_A ^(!CENTRAL_IP_BD!:3306^)
    echo.
    echo VERIFICA:
    echo   1. PC_A_RUN.bat esta ejecutandose en PC_A
    echo   2. MySQL esta activo en PC_A
    echo   3. Firewall en PC_A permite conexiones al puerto 3306
    echo   4. La IP !CENTRAL_IP_BD! es correcta ^(verifica en PC_A^)
    echo   5. Ambos PCs estan en la misma red
    echo.
    echo Comando para abrir firewall en PC_A ^(ejecutar en PowerShell como Admin^):
    echo   New-NetFirewallRule -DisplayName "MySQL" -Direction Inbound -LocalPort 3306 -Protocol TCP -Action Allow
    echo.
    echo Prueba de conectividad desde PC_B:
    echo   ping !CENTRAL_IP_BD!
    echo.
    pause
    exit /b 1
)

echo [OK] MySQL en PC_A esta accesible ^(!CENTRAL_IP_BD!:3306^)
echo [OK] Conexion a base de datos verificada correctamente
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
    echo [OK] Certificados SSL encontrados y validos:
    echo   - Certificado: certificados\registry_cert.pem ^(!CERT_SIZE! bytes^)
    echo   - Clave privada: certificados\registry_key.pem ^(!KEY_SIZE! bytes^)
    echo.
    echo [INFO] Iniciando EV_Registry en PC_B con HTTPS ^(SSL obligatorio^)...
    echo [INFO] Conectandose a BD en PC_A: !CENTRAL_IP_BD!:3306
    echo.
    start "EV_Registry_PC_B" cmd /k "python ev_registry\EV_Registry.py --db-host !CENTRAL_IP_BD! --db-port 3306 --db-user root --db-password root --db-name evcharging --port 6000 --ssl --ssl-cert certificados\registry_cert.pem --ssl-key certificados\registry_key.pem"
    echo [OK] EV_Registry iniciado en PC_B con HTTPS ^(puerto 6000^)
    echo   - API REST: https://localhost:6000/api
    echo   - Conectado a BD en PC_A: !CENTRAL_IP_BD!:3306
    goto :registry_started
)

REM Si no hay certificados, ERROR (SSL es obligatorio)
echo [ERROR] Certificados SSL NO encontrados o invalidos
echo.
echo SSL es OBLIGATORIO para el sistema. Debes generar los certificados.
echo.
echo OPCIONES:
echo   1. Ejecutar: generar_certificados_rapido.bat
echo   2. O ejecutar: generar_certificados_ssl.bat
echo.
echo Archivos requeridos en certificados\:
echo   - registry_cert.pem ^(certificado^)
echo   - registry_key.pem  ^(clave privada^)
echo.
echo IMPORTANTE: Los certificados deben copiarse desde PC_A o generarse
echo en PC_B siguiendo las instrucciones de la practica.
echo.
pause
exit /b 1

:registry_started

echo.
echo ========================================================================
echo   EV_Registry INICIADO CORRECTAMENTE EN PC_B
echo ========================================================================
echo.
echo [CONFIGURACION]
echo   - Ubicacion: PC_B ^(este ordenador^)
echo   - Puerto: 6000
echo   - Protocolo: HTTPS ^(SSL obligatorio^)
echo   - API REST: https://localhost:6000/api
echo   - Base de datos: !CENTRAL_IP_BD!:3306/evcharging ^(en PC_A^)
echo.
echo [IMPORTANTE] 
echo   - Espera unos segundos a que EV_Registry se inicie completamente
echo   - Los CPs de PC_B deben registrarse primero con Registry antes de conectar a Central
echo   - Registry esta conectado a la BD en PC_A ^(!CENTRAL_IP_BD!^)
echo.
echo [VERIFICAR CONEXION]
echo   Desde otro terminal, prueba:
echo   curl -k https://localhost:6000/api/status
echo.
echo [SIGUIENTE PASO]
echo   Ahora puedes ejecutar los CPs en PC_B usando los scripts:
echo   - INICIAR_CP01.bat
echo   - INICIAR_CP02.bat ^(si corresponde^)
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
echo ^(EV_Registry seguira corriendo en su ventana separada^)
pause >nul
