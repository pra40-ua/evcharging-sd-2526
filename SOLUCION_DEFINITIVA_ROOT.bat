@echo off
REM Solución definitiva para el problema de root@localhost
REM Este script elimina completamente el problema recreando todo desde cero

echo ========================================================================
echo           SOLUCION DEFINITIVA: ROOT@LOCALHOST
echo ========================================================================
echo.
echo Este script eliminara y recreara completamente los usuarios root
echo para solucionar el error 1045 Access denied.
echo.
pause

REM Verificar contenedor
docker ps --filter "name=mariadb" --format "{{.Names}}" | findstr /C:"mariadb" >nul
if %errorlevel% neq 0 (
    echo [ERROR] El contenedor mariadb no esta corriendo.
    echo Ejecuta: docker-compose up -d mariadb
    pause
    exit /b 1
)

echo.
echo [PASO 1/6] Eliminando usuarios root existentes...
docker exec mariadb mysql -u root -proot -e "DROP USER IF EXISTS 'root'@'localhost';" 2>&1
docker exec mariadb mysql -u root -proot -e "DROP USER IF EXISTS 'root'@'%%';" 2>&1
docker exec mariadb mysql -u root -proot -e "DROP USER IF EXISTS 'root'@'127.0.0.1';" 2>&1
docker exec mariadb mysql -u root -proot -e "FLUSH PRIVILEGES;" 2>&1
echo [OK] Usuarios eliminados.
echo.

echo [PASO 2/6] Creando root@localhost con mysql_native_password...
docker exec mariadb mysql -u root -proot -e "CREATE USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'root';" 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] No se pudo crear root@localhost
    pause
    exit /b 1
)
echo [OK] root@localhost creado.
echo.

echo [PASO 3/6] Creando root@%% con mysql_native_password...
docker exec mariadb mysql -u root -proot -e "CREATE USER 'root'@'%%' IDENTIFIED WITH mysql_native_password BY 'root';" 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] No se pudo crear root@%%
    pause
    exit /b 1
)
echo [OK] root@%% creado.
echo.

echo [PASO 4/6] Creando root@127.0.0.1 con mysql_native_password...
docker exec mariadb mysql -u root -proot -e "CREATE USER 'root'@'127.0.0.1' IDENTIFIED WITH mysql_native_password BY 'root';" 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] No se pudo crear root@127.0.0.1
    pause
    exit /b 1
)
echo [OK] root@127.0.0.1 creado.
echo.

echo [PASO 5/6] Otorgando permisos completos...
docker exec mariadb mysql -u root -proot -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost' WITH GRANT OPTION;" 2>&1
docker exec mariadb mysql -u root -proot -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'%%' WITH GRANT OPTION;" 2>&1
docker exec mariadb mysql -u root -proot -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION;" 2>&1
docker exec mariadb mysql -u root -proot -e "FLUSH PRIVILEGES;" 2>&1
echo [OK] Permisos otorgados.
echo.

echo [PASO 6/6] Verificando configuracion...
echo.
echo Usuarios root configurados:
docker exec mariadb mysql -u root -proot -e "SELECT User, Host, plugin FROM mysql.user WHERE User = 'root' ORDER BY Host;" 2>&1
echo.

echo Probando conexion desde Python (simulando EV_Central)...
python -c "import pymysql; conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='root', database='evcharging'); print('[OK] PyMySQL: Conexion exitosa'); conn.close()" 2>&1
if %errorlevel% equ 0 (
    echo.
    echo ========================================================================
    echo           SOLUCION APLICADA EXITOSAMENTE
    echo ========================================================================
    echo.
    echo El problema ha sido resuelto. Ahora puedes ejecutar PC_A_RUN.bat
    echo y EV_Central deberia conectarse correctamente.
) else (
    echo.
    echo [ADVERTENCIA] La conexion desde Python aun falla.
    echo.
    echo Probando con mysql.connector...
    python -c "import mysql.connector; conn = mysql.connector.connect(host='127.0.0.1', port=3306, user='root', password='root', database='evcharging'); print('[OK] mysql.connector: Conexion exitosa'); conn.close()" 2>&1
    if %errorlevel% equ 0 (
        echo.
        echo [OK] mysql.connector funciona. PyMySQL puede no estar instalado.
    ) else (
        echo.
        echo [ERROR] Ambos drivers fallan. Puede haber un problema mas profundo.
        echo.
        echo Verifica:
        echo   1. Que el contenedor mariadb esta corriendo
        echo   2. Que el puerto 3306 esta mapeado correctamente
        echo   3. Que la base de datos evcharging existe
    )
)

echo.
pause



