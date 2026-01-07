@echo off
REM Script para corregir acceso de root a MariaDB
REM Soluciona el error 1045 Access denied for user 'root'@'localhost'

echo ========================================================================
echo           CORRIGIENDO ACCESO ROOT A MARIADB
echo ========================================================================
echo.

REM Verificar contenedor
docker ps --filter "name=mariadb" --format "{{.Names}}" | findstr /C:"mariadb" >nul
if %errorlevel% neq 0 (
    echo [ERROR] El contenedor mariadb no esta corriendo.
    echo Ejecuta: docker-compose up -d mariadb
    pause
    exit /b 1
)

echo [1/5] Verificando estado actual de root...
docker exec mariadb mysql -u root -proot -e "SELECT User, Host, plugin FROM mysql.user WHERE User = 'root';" 2>&1
echo.

echo [2/5] Forzando mysql_native_password para root@localhost...
docker exec mariadb mysql -u root -proot -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'root';" 2>&1
if %errorlevel% neq 0 (
    echo [ADVERTENCIA] Error al configurar root@localhost
) else (
    echo [OK] root@localhost configurado
)
echo.

echo [3/5] Forzando mysql_native_password para root@%...
docker exec mariadb mysql -u root -proot -e "ALTER USER 'root'@'%%' IDENTIFIED WITH mysql_native_password BY 'root';" 2>&1
if %errorlevel% neq 0 (
    echo [ADVERTENCIA] Error al configurar root@%%
) else (
    echo [OK] root@%% configurado
)
echo.

echo [4/5] Creando/configurando root@127.0.0.1...
docker exec mariadb mysql -u root -proot -e "DROP USER IF EXISTS 'root'@'127.0.0.1';" 2>nul
docker exec mariadb mysql -u root -proot -e "CREATE USER 'root'@'127.0.0.1' IDENTIFIED WITH mysql_native_password BY 'root';" 2>&1
if %errorlevel% neq 0 (
    echo [ADVERTENCIA] Error al crear root@127.0.0.1
) else (
    echo [OK] root@127.0.0.1 creado
)
echo.

echo [5/5] Otorgando permisos y aplicando cambios...
docker exec mariadb mysql -u root -proot -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost' WITH GRANT OPTION;" 2>&1
docker exec mariadb mysql -u root -proot -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'%%' WITH GRANT OPTION;" 2>&1
docker exec mariadb mysql -u root -proot -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION;" 2>&1
docker exec mariadb mysql -u root -proot -e "FLUSH PRIVILEGES;" 2>&1
echo [OK] Permisos otorgados
echo.

echo ========================================================================
echo           VERIFICANDO CONFIGURACION
echo ========================================================================
echo.
echo Usuarios root configurados:
docker exec mariadb mysql -u root -proot -e "SELECT User, Host, plugin FROM mysql.user WHERE User = 'root' ORDER BY Host;" 2>&1
echo.

echo Probando conexion desde Python (como EV_Central)...
python -c "import pymysql; conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='root', database='evcharging'); print('[OK] PyMySQL: Conexion exitosa'); conn.close()" 2>&1
if %errorlevel% equ 0 (
    echo [OK] Conexion desde Python funciona!
) else (
    echo [ERROR] Aun hay problemas con la conexion desde Python
    echo.
    echo Probando con mysql.connector...
    python -c "import mysql.connector; conn = mysql.connector.connect(host='127.0.0.1', port=3306, user='root', password='root', database='evcharging'); print('[OK] mysql.connector: Conexion exitosa'); conn.close()" 2>&1
)

echo.
echo ========================================================================
echo           CORRECCION COMPLETADA
echo ========================================================================
echo.
echo Si la conexion funciona ahora, reinicia EV_Central.
echo.
pause



