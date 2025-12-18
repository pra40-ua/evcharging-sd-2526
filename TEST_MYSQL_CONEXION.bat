@echo off
REM Script para probar diferentes formas de conectar a MySQL

echo ============================================================
echo   PROBANDO CONEXIONES A MYSQL
echo ============================================================
echo.

echo [1/4] Probando 127.0.0.1:3306...
python -c "import mysql.connector; conn = mysql.connector.connect(host='127.0.0.1', port=3306, user='root', password='root', database='evcharging', connection_timeout=3); print('[OK] Conexion exitosa con 127.0.0.1'); conn.close()" 2>nul
if %errorlevel% equ 0 (
    echo [SOLUCION] Usa: 127.0.0.1:3306:root:root:evcharging
    goto :end
)

echo [2/4] Probando host.docker.internal:3306...
python -c "import mysql.connector; conn = mysql.connector.connect(host='host.docker.internal', port=3306, user='root', password='root', database='evcharging', connection_timeout=3); print('[OK] Conexion exitosa con host.docker.internal'); conn.close()" 2>nul
if %errorlevel% equ 0 (
    echo [SOLUCION] Usa: host.docker.internal:3306:root:root:evcharging
    goto :end
)

echo [3/4] Probando mysql:3306 (desde contenedor Docker)...
python -c "import mysql.connector; conn = mysql.connector.connect(host='mysql', port=3306, user='root', password='root', database='evcharging', connection_timeout=3); print('[OK] Conexion exitosa con mysql'); conn.close()" 2>nul
if %errorlevel% equ 0 (
    echo [SOLUCION] Usa: mysql:3306:root:root:evcharging
    goto :end
)

echo [4/4] Obteniendo IP del contenedor MySQL...
for /f "tokens=*" %%i in ('docker inspect -f "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}" mysql 2^>nul') do set MYSQL_IP=%%i
if not "!MYSQL_IP!"=="" (
    echo Probando IP directa del contenedor: !MYSQL_IP!:3306...
    python -c "import mysql.connector; conn = mysql.connector.connect(host='!MYSQL_IP!', port=3306, user='root', password='root', database='evcharging', connection_timeout=3); print('[OK] Conexion exitosa con IP directa'); conn.close()" 2>nul
    if !errorlevel! equ 0 (
        echo [SOLUCION] Usa: !MYSQL_IP!:3306:root:root:evcharging
        goto :end
    )
)

echo [ERROR] No se pudo conectar a MySQL con ninguna opcion
echo.
echo Verifica que:
echo   1. MySQL este corriendo: docker ps | findstr mysql
echo   2. El puerto 3306 este mapeado: docker port mysql
echo   3. Los permisos esten correctos

:end
echo.
pause

