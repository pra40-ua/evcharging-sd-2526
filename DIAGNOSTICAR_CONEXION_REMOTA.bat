@echo off
setlocal EnableDelayedExpansion
REM Script de diagnóstico completo para conexión remota a BD

echo ========================================================================
echo           DIAGNOSTICO: CONEXION REMOTA A BASE DE DATOS
echo ========================================================================
echo.

REM Leer IP
set CENTRAL_IP_BD=
if exist central_ip.txt (
    for /f "tokens=*" %%i in (central_ip.txt) do set CENTRAL_IP_BD=%%i
    echo [INFO] IP desde central_ip.txt: !CENTRAL_IP_BD!
) else (
    echo [ERROR] No se encuentra central_ip.txt
    pause
    exit /b 1
)

echo.
echo ========================================================================
echo [1/5] VERIFICANDO CONECTIVIDAD DE RED
echo ========================================================================
echo.
ping -n 2 !CENTRAL_IP_BD! >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] No se puede hacer ping a !CENTRAL_IP_BD!
    echo.
    echo La IP !CENTRAL_IP_BD! parece ser una IP de Docker, no la IP real del PC_A.
    echo.
    echo SOLUCION:
    echo   1. En PC_A, ejecuta: ipconfig
    echo   2. Busca la IP real de tu adaptador de red (ej: 192.168.1.43)
    echo   3. Actualiza central_ip.txt en PC_A con esa IP
    echo   4. Copia el archivo actualizado a PC_B
    pause
    exit /b 1
) else (
    echo [OK] Ping exitoso a !CENTRAL_IP_BD!
)
echo.

echo ========================================================================
echo [2/5] VERIFICANDO PUERTO 3306
echo ========================================================================
echo.
echo Probando conexion al puerto 3306...
python -c "import socket; s = socket.socket(); s.settimeout(3); result = s.connect_ex(('!CENTRAL_IP_BD!', 3306)); s.close(); exit(0 if result == 0 else 1)" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Puerto 3306 no accesible
    echo.
    echo CAUSAS POSIBLES:
    echo   1. MariaDB no esta corriendo en PC_A
    echo   2. Firewall bloqueando el puerto 3306
    echo   3. MariaDB no esta escuchando en todas las interfaces
    echo.
    echo SOLUCIONES EN PC_A:
    echo   1. Verificar MariaDB: docker ps --filter name=mariadb
    echo   2. Abrir firewall (PowerShell como Admin):
    echo      New-NetFirewallRule -DisplayName "MySQL" -Direction Inbound -LocalPort 3306 -Protocol TCP -Action Allow
    echo   3. Verificar que escucha en 0.0.0.0:
    echo      docker exec mariadb netstat -tlnp ^| findstr 3306
    pause
    exit /b 1
) else (
    echo [OK] Puerto 3306 esta abierto y accesible
)
echo.

echo ========================================================================
echo [3/5] PROBANDO CONEXION CON ROOT SIN CONTRASEÑA
echo ========================================================================
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
        echo VERIFICA EN PC_A:
        echo   1. Ejecuta: ELIMINAR_AUTENTICACION.bat
        echo   2. O verifica usuarios: docker exec mariadb mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "SELECT User, Host FROM mysql.user WHERE User='root';"
        pause
        exit /b 1
    )
) else (
    echo [OK] Conexion exitosa
)
echo.

echo ========================================================================
echo [4/5] VERIFICANDO ACCESO A TABLAS
echo ========================================================================
echo.
python -c "import mysql.connector; conn = mysql.connector.connect(host='!CENTRAL_IP_BD!', port=3306, user='root', password='', database='evcharging'); cursor = conn.cursor(); cursor.execute('SHOW TABLES'); tables = cursor.fetchall(); print('[OK] Tablas encontradas:', len(tables)); conn.close()" 2>&1
if %errorlevel% equ 0 (
    echo [OK] Acceso a tablas verificado
) else (
    echo [ADVERTENCIA] No se pudo acceder a las tablas
)
echo.

echo ========================================================================
echo [5/5] RESUMEN
echo ========================================================================
echo.
echo Si todos los pasos anteriores fueron OK, la conexion funciona.
echo Si alguno fallo, sigue las instrucciones mostradas arriba.
echo.
pause



