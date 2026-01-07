@echo off
REM Script para eliminar completamente la autenticación de MariaDB
REM Configura root sin contraseña y permite acceso sin autenticación

echo ========================================================================
echo           ELIMINANDO AUTENTICACION DE MARIADB
echo ========================================================================
echo.
echo Este script configurara MariaDB para acceso sin contraseña.
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
echo [PASO 1/5] Conectando usando socket Unix (sin contraseña)...
REM Usar socket Unix dentro del contenedor para evitar problemas de autenticación
docker exec mariadb mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "SELECT 'Conexion OK' AS resultado;" 2>&1
if %errorlevel% neq 0 (
    echo [ADVERTENCIA] No se pudo conectar con socket Unix, intentando con contraseña vacia...
    docker exec mariadb mysql -u root --password= -e "SELECT 'Conexion OK' AS resultado;" 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] No se puede conectar a MariaDB. Verifica que el contenedor esta corriendo.
        pause
        exit /b 1
    )
)

echo [OK] Conexion establecida.
echo.

echo [PASO 2/5] Eliminando usuarios root existentes...
docker exec mariadb mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "DROP USER IF EXISTS 'root'@'localhost';" 2>&1
docker exec mariadb mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "DROP USER IF EXISTS 'root'@'%%';" 2>&1
docker exec mariadb mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "DROP USER IF EXISTS 'root'@'127.0.0.1';" 2>&1
echo [OK] Usuarios eliminados.
echo.

echo [PASO 3/5] Creando root SIN CONTRASEÑA...
docker exec mariadb mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "CREATE USER 'root'@'localhost' IDENTIFIED BY '';" 2>&1
docker exec mariadb mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "CREATE USER 'root'@'%%' IDENTIFIED BY '';" 2>&1
docker exec mariadb mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "CREATE USER 'root'@'127.0.0.1' IDENTIFIED BY '';" 2>&1
echo [OK] Usuarios creados sin contraseña.
echo.

echo [PASO 4/5] Otorgando permisos completos...
docker exec mariadb mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost' WITH GRANT OPTION;" 2>&1
docker exec mariadb mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'%%' WITH GRANT OPTION;" 2>&1
docker exec mariadb mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION;" 2>&1
docker exec mariadb mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "FLUSH PRIVILEGES;" 2>&1
echo [OK] Permisos otorgados.
echo.

echo [PASO 5/5] Verificando configuracion...
echo.
echo Usuarios root configurados:
docker exec mariadb mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "SELECT User, Host, plugin FROM mysql.user WHERE User = 'root' ORDER BY Host;" 2>&1
echo.

echo Probando conexion SIN contraseña desde Python...
python -c "import pymysql; conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='', database='evcharging'); print('[OK] PyMySQL: Conexion sin contraseña exitosa'); conn.close()" 2>&1
if %errorlevel% equ 0 (
    echo.
    echo ========================================================================
    echo           AUTENTICACION ELIMINADA EXITOSAMENTE
    echo ========================================================================
    echo.
    echo Ahora necesitas actualizar los scripts para usar contraseña vacia:
    echo   - RUN_CENTRAL.bat: cambiar root:root a root:
    echo   - PC_A_RUN.bat: cambiar root:root a root:
) else (
    echo [ADVERTENCIA] La conexion sin contraseña aun falla.
    echo Probando con mysql.connector...
    python -c "import mysql.connector; conn = mysql.connector.connect(host='127.0.0.1', port=3306, user='root', password='', database='evcharging'); print('[OK] mysql.connector: Conexion sin contraseña exitosa'); conn.close()" 2>&1
)

echo.
pause



