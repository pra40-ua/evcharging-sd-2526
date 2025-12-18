@echo off
REM Script para probar la conexión a MySQL antes de ejecutar EV_Central

echo ============================================================
echo   PROBANDO CONEXION A MYSQL
echo ============================================================
echo.

python -c "import mysql.connector; conn = mysql.connector.connect(host='127.0.0.1', port=3306, user='root', password='root', database='evcharging', ssl_disabled=True, allow_public_key_retrieval=True, auth_plugin='caching_sha2_password', connect_timeout=5); print('[OK] Conexion exitosa a MySQL'); print(f'    Base de datos: {conn.database}'); print(f'    Servidor: {conn.server_host}:{conn.server_port}'); conn.close()"

if %errorlevel% equ 0 (
    echo.
    echo [OK] La conexion funciona correctamente
    echo Puedes ejecutar EV_Central ahora
) else (
    echo.
    echo [ERROR] No se pudo conectar a MySQL
    echo.
    echo Verificando estado de MySQL...
    docker ps | findstr /i "mysql"
    echo.
    echo Si MySQL esta corriendo, prueba ejecutar:
    echo   docker exec -i mysql mysql -uroot -proot -e "SELECT 'OK' AS status;"
)

echo.
pause

