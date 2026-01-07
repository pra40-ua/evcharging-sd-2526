@echo off
setlocal EnableDelayedExpansion
REM Script para solucionar problemas de conexión remota a BD

echo ========================================================================
echo           SOLUCIONAR CONEXION REMOTA A BASE DE DATOS
echo ========================================================================
echo.

REM Leer IP actual
set CENTRAL_IP_BD=
if exist central_ip.txt (
    for /f "tokens=*" %%i in (central_ip.txt) do set CENTRAL_IP_BD=%%i
    echo [INFO] IP actual en central_ip.txt: !CENTRAL_IP_BD!
) else (
    echo [ERROR] No se encuentra central_ip.txt
    echo.
    echo Debes copiar el archivo central_ip.txt desde PC_A
    pause
    exit /b 1
)

echo.
echo Verificando si la IP es correcta...
echo.

REM Verificar si es una IP de Docker (172.17.x.x o 172.18.x.x)
echo !CENTRAL_IP_BD! | findstr /R "^172\.17\." >nul
if %errorlevel% equ 0 (
    echo [ADVERTENCIA] La IP !CENTRAL_IP_BD! parece ser una IP de Docker, no la IP real del PC_A
    echo.
    echo SOLUCION:
    echo   1. En PC_A, ejecuta: ipconfig
    echo   2. Busca la IP de tu adaptador de red Ethernet o Wi-Fi
    echo      ^(ejemplo: 192.168.1.43, 192.168.0.100, etc.^)
    echo   3. NO uses la IP 172.17.x.x o 172.18.x.x ^(son IPs de Docker^)
    echo   4. Actualiza central_ip.txt en PC_A con la IP correcta
    echo   5. Copia el archivo actualizado a PC_B
    echo.
    echo O puedes ingresar la IP correcta ahora:
    set /p NUEVA_IP="Ingresa la IP real de PC_A: "
    if not "!NUEVA_IP!"=="" (
        echo !NUEVA_IP!> central_ip.txt
        set CENTRAL_IP_BD=!NUEVA_IP!
        echo [OK] IP actualizada a: !CENTRAL_IP_BD!
    )
    echo.
)

REM Verificar conectividad
echo [PASO 1] Verificando conectividad de red...
ping -n 2 !CENTRAL_IP_BD! >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] No se puede hacer ping a !CENTRAL_IP_BD!
    echo Verifica que ambos PCs estan en la misma red
    pause
    exit /b 1
) else (
    echo [OK] Ping exitoso
)
echo.

REM Verificar puerto
echo [PASO 2] Verificando puerto 3306...
python -c "import socket; s = socket.socket(); s.settimeout(3); result = s.connect_ex(('!CENTRAL_IP_BD!', 3306)); s.close(); exit(0 if result == 0 else 1)" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Puerto 3306 no accesible
    echo.
    echo INSTRUCCIONES PARA PC_A:
    echo.
    echo 1. Abre PowerShell como Administrador
    echo 2. Ejecuta este comando:
    echo    New-NetFirewallRule -DisplayName "MySQL" -Direction Inbound -LocalPort 3306 -Protocol TCP -Action Allow
    echo.
    echo 3. Verifica que MariaDB este corriendo:
    echo    docker ps --filter name=mariadb
    echo.
    echo 4. Verifica que MariaDB escucha en todas las interfaces:
    echo    docker exec mariadb netstat -tlnp ^| findstr 3306
    echo    ^(Debe mostrar 0.0.0.0:3306^)
    echo.
    pause
    exit /b 1
) else (
    echo [OK] Puerto 3306 accesible
)
echo.

REM Probar conexión
echo [PASO 3] Probando conexion con root sin contraseña...
python -c "import sys; import mysql.connector; conn = mysql.connector.connect(host='!CENTRAL_IP_BD!', port=3306, user='root', password='', database='evcharging', connection_timeout=5); print('[OK] Conexion exitosa'); conn.close(); sys.exit(0)" 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] No se pudo conectar
    echo.
    echo INSTRUCCIONES PARA PC_A:
    echo.
    echo 1. Ejecuta: ELIMINAR_AUTENTICACION.bat
    echo    O ejecuta: docker exec mariadb mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "CREATE USER IF NOT EXISTS 'root'@'%%' IDENTIFIED BY ''; GRANT ALL PRIVILEGES ON *.* TO 'root'@'%%' WITH GRANT OPTION; FLUSH PRIVILEGES;"
    echo.
    echo 2. Verifica usuarios:
    echo    docker exec mariadb mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "SELECT User, Host FROM mysql.user WHERE User='root';"
    echo.
    pause
    exit /b 1
) else (
    echo [OK] Conexion exitosa!
    echo.
    echo ========================================================================
    echo           CONEXION REMOTA FUNCIONA CORRECTAMENTE
    echo ========================================================================
    echo.
    echo Ahora puedes ejecutar INICIAR_REGISTRY_PC_B.bat
)

echo.
pause



