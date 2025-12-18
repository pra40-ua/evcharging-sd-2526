@echo off
REM ========================================================================
REM  SCRIPT PARA INICIAR EV_Registry EN PC_B
REM ========================================================================
REM  Este script inicia EV_Registry en PC_B siguiendo la guía simplificada
REM  de implementación para la Release 2.
REM  
REM  ARQUITECTURA:
REM  - EV_Registry (PC_B) se conecta a la BD en PC_A (remotamente)
REM  - EV_Central (PC_A) también usa la misma BD para validar credenciales
REM  - El Registry gestiona el registro inicial y entrega de credenciales
REM  - EV_Central gestiona la autenticación real y entrega de claves simétricas
REM  
REM  IMPORTANTE: Los CPs deben registrarse primero en el Registry antes
REM  de poder autenticarse en EV_Central. El Registry devuelve las
REM  credenciales (username/password) que el CP usará para autenticarse
REM  posteriormente en EV_Central.
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
echo [1/4] DETECTANDO IP DE BASE DE DATOS EN PC_A
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

REM ============================================================
REM  PASO 2: VERIFICAR QUE PYTHON ESTÁ DISPONIBLE
REM ============================================================
echo [2/4] VERIFICANDO PYTHON
echo.

python --version >nul 2>&1
if errorlevel 1 (
    py --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python no esta disponible
        echo.
        echo Debes instalar Python o asegurarte de que esta en el PATH.
        echo Prueba ejecutando: python --version o py --version
        echo.
        pause
        exit /b 1
    )
    set PYTHON_CMD=py
) else (
    set PYTHON_CMD=python
)

echo [OK] Python detectado
echo.

REM ============================================================
REM  PASO 3: VERIFICAR CONEXIÓN A BASE DE DATOS EN PC_A
REM ============================================================
echo [3/4] VERIFICANDO CONEXIÓN A BASE DE DATOS EN PC_A
echo.

echo [INFO] Configuracion:
echo   - Base de datos en PC_A: !CENTRAL_IP_BD!:3306
echo   - Database: evcharging
echo   - Puerto Registry: 6000
echo.
echo Verificando que MySQL en PC_A esta accesible ^(!CENTRAL_IP_BD!:3306^)...
echo ^(Esto puede tardar unos segundos^)
echo.

REM Verificar conexión usando Python
!PYTHON_CMD! -c "import sys; import mysql.connector; conn = mysql.connector.connect(host='!CENTRAL_IP_BD!', port=3306, user='root', password='root', database='evcharging', connection_timeout=5); conn.close(); sys.exit(0)" 2>nul
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
REM  PASO 4: VERIFICAR CERTIFICADOS SSL (OBLIGATORIO)
REM ============================================================
echo [4/4] VERIFICANDO CERTIFICADOS SSL
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
    
    REM Verificar que existe el archivo EV_Registry.py
    if not exist "ev_registry\EV_Registry.py" (
        echo [ERROR] No se encuentra ev_registry\EV_Registry.py
        echo.
        echo Verifica que el archivo existe en la ruta correcta.
        echo.
        pause
        exit /b 1
    )
    
    echo [INFO] Iniciando EV_Registry en PC_B con HTTPS ^(SSL obligatorio^)...
    echo [INFO] Conectandose a BD en PC_A: !CENTRAL_IP_BD!:3306
    echo [INFO] El Registry compartira la BD con EV_Central para sincronizar CPs
    echo.
    start "EV_Registry_PC_B" cmd /k "!PYTHON_CMD! ev_registry\EV_Registry.py --db-host !CENTRAL_IP_BD! --db-port 3306 --db-user root --db-password root --db-name evcharging --port 6000 --ssl --ssl-cert certificados\registry_cert.pem --ssl-key certificados\registry_key.pem"
    echo [OK] EV_Registry iniciado en PC_B con HTTPS ^(puerto 6000^)
    echo   - API REST: https://localhost:6001/register/cp
    echo   - Health Check: https://localhost:6001/api/health
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
echo   - Protocolo: HTTPS ^(SSL obligatorio - cifrado del canal^)
echo   - API REST Base: https://localhost:6001/register/cp
echo   - Base de datos: !CENTRAL_IP_BD!:3306/evcharging ^(en PC_A - conexion remota^)
echo   - Compartida con: EV_Central en PC_A para validacion de credenciales
echo.
echo [API REST DISPONIBLE]
echo   - REGISTRO: PUT/POST /register/cp - Registra un nuevo CP en el sistema
echo   - BAJA: DELETE /register/cp/^<id^> - Da de baja un CP
echo   - CONSULTA: GET /register/cp/^<id^> - ^(Opcional^) Consulta estado/datos del CP
echo   - HEALTH: GET /api/health - Verifica estado del servicio
echo.
echo [FLUJO DE INTEGRACION DE CPs - SEGUN GUIA]
echo   1. El CP ^(a traves de EV_CP_M - Monitor^) se conecta al Registry via HTTPS
echo      ^(Cifrado del canal OBLIGATORIO - SSL/TLS^)
echo   2. El CP se registra mediante PUT/POST /register/cp con su ID y ubicacion
echo   3. El Registry genera credenciales unicas ^(username y password^) para el CP
echo   4. El Registry almacena las credenciales en la BD ^(en PC_A^) para que
echo      EV_Central pueda validarlas posteriormente
echo   5. El Registry devuelve las credenciales al CP Monitor ^(EV_CP_M^) en la respuesta
echo   6. El CP usa estas credenciales para intentar autenticarse en EV_Central ^(PC_A^)
echo   7. EV_Central consulta la BD para validar si el CP esta registrado y las
echo      credenciales son correctas
echo   8. Si es exitoso: EV_Central genera una clave de cifrado simetrico UNICA para
echo      ese CP, la almacena y la devuelve al Monitor
echo   9. El CP usa esta clave simetrica para cifrar todos los mensajes futuros
echo      que envie a Central
echo.
echo [IMPORTANTE - ROL DEL REGISTRY]
echo   - El Registry SOLO gestiona el registro inicial y la entrega de credenciales
echo   - La autenticacion real ^(con devolucion de clave simetrica^) la gestiona EV_Central
echo   - Sin registro previo en el Registry, la autenticacion en EV_Central sera denegada
echo.
echo [CONFIGURACION DE SEGURIDAD]
echo   - Espera unos segundos a que EV_Registry se inicie completamente
echo   - Los CPs deben registrarse PRIMERO en el Registry antes de conectar a Central
echo   - La comunicacion con el Registry debe ser segura ^(HTTPS/SSL OBLIGATORIO^)
echo   - Se usa certificado autofirmado para simplificar en el entorno de practica
echo   - Registry esta conectado a la BD en PC_A ^(!CENTRAL_IP_BD!^) para compartir
echo     informacion de CPs con EV_Central
echo   - EV_Central y EV_Registry comparten la misma BD para sincronizar informacion
echo.
echo [VERIFICAR CONEXION]
echo   Desde otro terminal, prueba:
echo   curl -k https://localhost:6001/api/health
echo.
echo   Para probar registro de CP:
echo   curl -k -X POST https://localhost:6001/register/cp ^
echo     -H "Content-Type: application/json" ^
echo     -d "{\"cp_id\":\"CP001\",\"ubicacion\":\"C/Mayor, 45, Madrid\"}"
echo.
echo [SIGUIENTE PASO - IMPORTANTE]
echo   Ahora que Registry esta corriendo, puedes ejecutar los CPs:
echo.
echo   1. En otra ventana, ejecuta: PC_B_RUN.bat
echo   2. El Monitor ^(EV_CP_M^) detectara automaticamente el Registry local
echo   3. El CP se registrara automaticamente en el Registry via PUT/POST /register/cp
echo   4. El Registry generara y devolvera credenciales ^(username/password^) al CP
echo   5. El CP usara estas credenciales para autenticarse en EV_Central ^(PC_A^)
echo   6. EV_Central validara las credenciales en la BD y devolvera clave simetrica
echo.
echo NOTA: Deja esta ventana abierta ^(Registry debe seguir corriendo^)
echo.
echo [VERIFICAR QUE FUNCIONA]
echo   Antes de ejecutar PC_B_RUN.bat, puedes verificar Registry desde otra terminal:
echo   curl -k https://localhost:6001/api/health
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
echo ^(ADVERTENCIA: Si cierras esta ventana, Registry se detendra^)
echo ^(El Registry debe estar corriendo mientras ejecutas los CPs^)
pause >nul
