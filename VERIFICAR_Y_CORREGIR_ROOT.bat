@echo off
REM Script para verificar y corregir el problema de root@localhost

echo ========================================================================
echo           VERIFICANDO Y CORRIGIENDO ROOT@LOCALHOST
echo ========================================================================
echo.

REM Verificar contenedor
docker ps --filter "name=mariadb" --format "{{.Names}}" | findstr /C:"mariadb" >nul
if %errorlevel% neq 0 (
    echo [ERROR] El contenedor mariadb no esta corriendo.
    pause
    exit /b 1
)

echo [PASO 1] Estado actual de root...
echo.
docker exec mariadb mysql -u root -proot -e "SELECT User, Host, plugin, authentication_string FROM mysql.user WHERE User = 'root';" 2>&1
echo.

echo [PASO 2] Verificando si podemos conectarnos desde dentro del contenedor...
docker exec mariadb mysql -u root -proot -e "SELECT 'Conexion OK' AS resultado;" 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] No se puede conectar ni desde dentro del contenedor!
    echo Esto indica un problema mas grave.
    pause
    exit /b 1
) else (
    echo [OK] Conexion desde dentro del contenedor funciona
)
echo.

echo [PASO 3] Eliminando y recreando root@localhost completamente...
docker exec mariadb mysql -u root -proot -e "DROP USER IF EXISTS 'root'@'localhost';" 2>&1
docker exec mariadb mysql -u root -proot -e "CREATE USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'root';" 2>&1
docker exec mariadb mysql -u root -proot -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost' WITH GRANT OPTION;" 2>&1
echo.

echo [PASO 4] Configurando root@%%
docker exec mariadb mysql -u root -proot -e "DROP USER IF EXISTS 'root'@'%%';" 2>&1
docker exec mariadb mysql -u root -proot -e "CREATE USER 'root'@'%%' IDENTIFIED WITH mysql_native_password BY 'root';" 2>&1
docker exec mariadb mysql -u root -proot -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'%%' WITH GRANT OPTION;" 2>&1
echo.

echo [PASO 5] Configurando root@127.0.0.1
docker exec mariadb mysql -u root -proot -e "DROP USER IF EXISTS 'root'@'127.0.0.1';" 2>&1
docker exec mariadb mysql -u root -proot -e "CREATE USER 'root'@'127.0.0.1' IDENTIFIED WITH mysql_native_password BY 'root';" 2>&1
docker exec mariadb mysql -u root -proot -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION;" 2>&1
echo.

echo [PASO 6] Aplicando cambios...
docker exec mariadb mysql -u root -proot -e "FLUSH PRIVILEGES;" 2>&1
echo.

echo [PASO 7] Verificando configuracion final...
docker exec mariadb mysql -u root -proot -e "SELECT User, Host, plugin FROM mysql.user WHERE User = 'root' ORDER BY Host;" 2>&1
echo.

echo [PASO 8] Probando conexion desde Python (como EV_Central lo hace)...
echo.
echo Probando con PyMySQL...
python -c "import pymysql; conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='root', database='evcharging'); print('[OK] PyMySQL: Conexion exitosa'); conn.close()" 2>&1
if %errorlevel% equ 0 (
    echo [OK] PyMySQL funciona!
) else (
    echo [ERROR] PyMySQL aun falla
    echo.
    echo Probando con mysql.connector...
    python -c "import mysql.connector; conn = mysql.connector.connect(host='127.0.0.1', port=3306, user='root', password='root', database='evcharging'); print('[OK] mysql.connector: Conexion exitosa'); conn.close()" 2>&1
)

echo.
echo ========================================================================
echo           VERIFICACION COMPLETADA
echo ========================================================================
echo.
pause



