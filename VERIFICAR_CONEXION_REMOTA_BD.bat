@echo off
REM Script para verificar conexión remota a la base de datos en PC_A

echo ========================================================================
echo           VERIFICAR CONEXION REMOTA A BASE DE DATOS
echo ========================================================================
echo.

REM Leer IP de PC_A
set CENTRAL_IP_BD=
if exist central_ip.txt (
    for /f "tokens=*" %%i in (central_ip.txt) do set CENTRAL_IP_BD=%%i
    echo [INFO] IP detectada desde central_ip.txt: !CENTRAL_IP_BD!
) else (
    echo [ERROR] No se encuentra central_ip.txt
    echo Por favor, copia el archivo desde PC_A
    pause
    exit /b 1
)

echo.
echo [PASO 1/4] Verificando conectividad de red...
echo.
ping -n 2 !CENTRAL_IP_BD! >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] No se puede hacer ping a !CENTRAL_IP_BD!
    echo Verifica que:
    echo   1. Ambos PCs estan en la misma red
    echo   2. La IP !CENTRAL_IP_BD! es correcta
    echo   3. El firewall no esta bloqueando ICMP
    pause
    exit /b 1
) else (
    echo [OK] Ping exitoso a !CENTRAL_IP_BD!
)
echo.

echo [PASO 2/4] Verificando que el puerto 3306 esta abierto...
echo.
python -c "import socket; s = socket.socket(); s.settimeout(3); result = s.connect_ex(('!CENTRAL_IP_BD!', 3306)); s.close(); exit(0 if result == 0 else 1)" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] El puerto 3306 no esta accesible en !CENTRAL_IP_BD!
    echo.
    echo Esto puede deberse a:
    echo   1. MariaDB no esta corriendo en PC_A
    echo   2. El firewall en PC_A esta bloqueando el puerto 3306
    echo   3. MariaDB no esta escuchando en todas las interfaces
    echo.
    echo SOLUCIONES:
    echo   1. En PC_A, ejecuta en PowerShell como Admin:
    echo      New-NetFirewallRule -DisplayName "MySQL" -Direction Inbound -LocalPort 3306 -Protocol TCP -Action Allow
    echo   2. Verifica que MariaDB este corriendo: docker ps --filter name=mariadb
    echo   3. Verifica que MariaDB este escuchando: docker exec mariadb netstat -tlnp ^| findstr 3306
    pause
    exit /b 1
) else (
    echo [OK] Puerto 3306 esta abierto y accesible
)
echo.

echo [PASO 3/4] Probando conexion con root sin contraseña...
echo.
python -c "import sys; import mysql.connector; conn = mysql.connector.connect(host='!CENTRAL_IP_BD!', port=3306, user='root', password='', database='evcharging', connection_timeout=5); print('[OK] Conexion exitosa'); conn.close(); sys.exit(0)" 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] No se pudo conectar con root sin contraseña
    echo.
    echo Probando con PyMySQL...
    python -c "import sys; import pymysql; conn = pymysql.connect(host='!CENTRAL_IP_BD!', port=3306, user='root', password='', database='evcharging', connect_timeout=5); print('[OK] Conexion exitosa con PyMySQL'); conn.close(); sys.exit(0)" 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Ambos drivers fallan
        echo.
        echo Verifica en PC_A que:
        echo   1. MariaDB esta configurado con root sin contraseña
        echo   2. El usuario root@%% existe y tiene permisos
        echo   3. Ejecuta en PC_A: ELIMINAR_AUTENTICACION.bat
        pause
        exit /b 1
    )
) else (
    echo [OK] Conexion exitosa con mysql.connector
)
echo.

echo [PASO 4/4] Verificando acceso a la base de datos...
echo.
python -c "import mysql.connector; conn = mysql.connector.connect(host='!CENTRAL_IP_BD!', port=3306, user='root', password='', database='evcharging'); cursor = conn.cursor(); cursor.execute('SHOW TABLES'); tables = cursor.fetchall(); print('[OK] Tablas encontradas:', len(tables)); conn.close()" 2>&1
if %errorlevel% equ 0 (
    echo.
    echo ========================================================================
    echo           CONEXION REMOTA VERIFICADA EXITOSAMENTE
    echo ========================================================================
    echo.
    echo La conexion a la base de datos en PC_A funciona correctamente.
    echo Ahora puedes ejecutar INICIAR_REGISTRY_PC_B.bat
) else (
    echo [ERROR] No se pudo acceder a las tablas
    echo Verifica que la base de datos evcharging existe en PC_A
)

echo.
pause



