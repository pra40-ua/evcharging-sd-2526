@echo off
REM Script para solucionar problemas de conexión a MySQL
REM Opción 1: Conectar a MySQL en Docker y dar permisos
REM Opción 2: Usar host.docker.internal si se ejecuta desde contenedor

echo ============================================================
echo   SOLUCIONAR PROBLEMA DE CONEXION A MYSQL
echo ============================================================
echo.

REM Verificar si MySQL está corriendo en Docker
echo [1/3] Verificando si MySQL está en Docker...
docker ps | findstr /i "mysql" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] MySQL está corriendo en Docker
    echo.
    echo [2/3] Configurando permisos de MySQL...
    echo.
    echo Ejecutando comandos SQL para permitir conexiones desde cualquier IP...
    docker exec -i mysql mysql -uroot -proot -e "CREATE USER IF NOT EXISTS 'root'@'%%' IDENTIFIED BY 'root'; GRANT ALL PRIVILEGES ON *.* TO 'root'@'%%' WITH GRANT OPTION; FLUSH PRIVILEGES;"
    
    if %errorlevel% equ 0 (
        echo [OK] Permisos configurados correctamente
    ) else (
        echo [ERROR] No se pudieron configurar los permisos
        echo Intentando método alternativo...
        docker exec -i mysql mysql -uroot -proot -e "UPDATE mysql.user SET host='%%' WHERE user='root' AND host='localhost'; FLUSH PRIVILEGES;"
    )
    echo.
    echo [3/3] Verificando conexión...
    docker exec -i mysql mysql -uroot -proot -e "SELECT 'Conexion OK' AS status;" 2>nul
    if %errorlevel% equ 0 (
        echo [OK] MySQL está funcionando correctamente
    ) else (
        echo [ADVERTENCIA] Verifica manualmente la conexión
    )
) else (
    echo [INFO] MySQL no está en Docker, verificando si está en el sistema...
    echo.
    echo Si MySQL está instalado localmente, ejecuta estos comandos SQL:
    echo.
    echo   CREATE USER IF NOT EXISTS 'root'@'%%' IDENTIFIED BY 'root';
    echo   GRANT ALL PRIVILEGES ON *.* TO 'root'@'%%' WITH GRANT OPTION;
    echo   FLUSH PRIVILEGES;
    echo.
    echo O si ya existe el usuario root:
    echo.
    echo   UPDATE mysql.user SET host='%%' WHERE user='root' AND host='localhost';
    echo   FLUSH PRIVILEGES;
    echo.
)

echo.
echo ============================================================
echo   OPCIONES DE CONEXION
echo ============================================================
echo.
echo Si EV_Central se ejecuta DESDE DOCKER, usa:
echo   mysql:3306:root:root:evcharging
echo.
echo Si EV_Central se ejecuta EN EL HOST, usa:
echo   127.0.0.1:3306:root:root:evcharging
echo   O
echo   host.docker.internal:3306:root:root:evcharging
echo.
pause

