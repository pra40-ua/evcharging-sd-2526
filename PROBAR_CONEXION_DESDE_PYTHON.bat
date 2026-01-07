@echo off
REM Script para probar la conexión desde Python (como lo hace EV_Central)

echo ========================================================================
echo           PROBANDO CONEXION DESDE PYTHON
echo ========================================================================
echo.
echo Este script prueba la conexion exactamente como lo hace EV_Central.
echo.

REM Verificar que el contenedor está corriendo
docker ps --filter "name=mariadb" --format "{{.Names}}" | findstr /C:"mariadb" >nul
if %errorlevel% neq 0 (
    echo [ERROR] El contenedor mariadb no esta corriendo.
    pause
    exit /b 1
)

echo [1/2] Probando con PyMySQL (si esta instalado)...
python -c "import pymysql; conn = pymysql.connect(host='127.0.0.1', port=3306, user='ev_user', password='ev_user_pass', database='evcharging', charset='utf8mb4'); cursor = conn.cursor(); cursor.execute('SELECT 1'); print('[OK] PyMySQL: Conexion exitosa'); conn.close()" 2>&1
if %errorlevel% neq 0 (
    echo [INFO] PyMySQL no disponible o fallo
) else (
    echo.
)

echo.
echo [2/2] Probando con mysql.connector (si esta instalado)...
python -c "import mysql.connector; conn = mysql.connector.connect(host='127.0.0.1', port=3306, user='ev_user', password='ev_user_pass', database='evcharging'); cursor = conn.cursor(); cursor.execute('SELECT 1'); print('[OK] mysql.connector: Conexion exitosa'); conn.close()" 2>&1
if %errorlevel% neq 0 (
    echo [INFO] mysql.connector no disponible o fallo
) else (
    echo.
)

echo.
echo ========================================================================
echo           PRUEBA COMPLETADA
echo ========================================================================
echo.
echo Si ambas pruebas fallaron, el problema esta en la configuracion del usuario.
echo Ejecuta: SOLUCIONAR_EV_USER_DEFINITIVO.bat
echo.
pause



