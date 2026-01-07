@echo off
REM ========================================================================
REM  SCRIPT PARA REPARAR LA BASE DE DATOS DESDE PC_B
REM ========================================================================
REM  Este script crea las tablas faltantes en MySQL de PC_A
REM ========================================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ========================================================================
echo   REPARANDO BASE DE DATOS EN PC_A - Creando tablas faltantes
echo ========================================================================
echo.

REM Leer IP de PC_A desde central_ip.txt
set CENTRAL_IP_BD=
if exist central_ip.txt (
    for /f "tokens=*" %%i in (central_ip.txt) do set CENTRAL_IP_BD=%%i
) else (
    echo [ERROR] No se encuentra central_ip.txt
    echo.
    echo Debes copiar el archivo central_ip.txt desde PC_A a este directorio.
    pause
    exit /b 1
)

echo [1/3] Detectando BD en PC_A: !CENTRAL_IP_BD!:3306
echo.

REM Verificar conexión a MySQL en PC_A
echo [2/3] Verificando conexion a MySQL en PC_A...
echo.

python -c "import sys; import mysql.connector; conn = mysql.connector.connect(host='!CENTRAL_IP_BD!', port=3306, user='evcharging_app', password='evcharging_app_pass', database='evcharging', connection_timeout=5); conn.close(); sys.exit(0)" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] No se pudo conectar a MySQL en PC_A ^(!CENTRAL_IP_BD!:3306^)
    echo.
    echo Verifica que PC_A_RUN.bat este ejecutandose en PC_A
    pause
    exit /b 1
)

echo [OK] MySQL en PC_A esta accesible
echo.

echo [3/3] Creando tablas faltantes en BD de PC_A...
echo.

REM Crear tablas usando Python + mysql.connector
python -c "import mysql.connector; conn = mysql.connector.connect(host='!CENTRAL_IP_BD!', port=3306, user='evcharging_app', password='evcharging_app_pass', database='evcharging'); cursor = conn.cursor(); cursor.execute('CREATE TABLE IF NOT EXISTS cp_encryption_keys (id INT AUTO_INCREMENT PRIMARY KEY, cp_id VARCHAR(50) UNIQUE NOT NULL, encryption_key VARCHAR(255) NOT NULL, fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP, fecha_ultima_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, activo BOOLEAN DEFAULT TRUE, INDEX idx_cp_id (cp_id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4'); cursor.execute('CREATE TABLE IF NOT EXISTS audit_log (id INT AUTO_INCREMENT PRIMARY KEY, fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP, origen_ip VARCHAR(45), cp_id VARCHAR(50), accion VARCHAR(100) NOT NULL, descripcion TEXT, resultado VARCHAR(50), INDEX idx_fecha_hora (fecha_hora), INDEX idx_cp_id (cp_id), INDEX idx_accion (accion)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4'); cursor.execute('CREATE TABLE IF NOT EXISTS weather_alerts (id INT AUTO_INCREMENT PRIMARY KEY, cp_id VARCHAR(50) NOT NULL, temperatura DECIMAL(5,2), alerta_activa BOOLEAN DEFAULT FALSE, fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP, INDEX idx_cp_id (cp_id), INDEX idx_alerta_activa (alerta_activa)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4'); conn.commit(); print('[OK] Tablas creadas/verificadas correctamente'); cursor.close(); conn.close()"

if %errorlevel% equ 0 (
    echo.
    echo [OK] Tablas cp_encryption_keys, audit_log y weather_alerts creadas
) else (
    echo.
    echo [ERROR] No se pudieron crear las tablas
    pause
    exit /b 1
)

echo.
echo ========================================================================
echo   VERIFICACION DE TABLAS EN PC_A
echo ========================================================================
echo.

REM Mostrar todas las tablas
python -c "import mysql.connector; conn = mysql.connector.connect(host='!CENTRAL_IP_BD!', port=3306, user='evcharging_app', password='evcharging_app_pass', database='evcharging'); cursor = conn.cursor(); cursor.execute('SHOW TABLES'); tables = cursor.fetchall(); print('Tablas en la base de datos evcharging:'); print(''); for table in tables: print(f'  - {table[0]}'); cursor.close(); conn.close()"

echo.
echo ========================================================================
echo   REPARACION COMPLETADA EXITOSAMENTE
echo ========================================================================
echo.
echo Las tablas han sido creadas en MySQL de PC_A (!CENTRAL_IP_BD!).
echo.
echo SIGUIENTE PASO:
echo   - En PC_A: Reinicia EV_Central si ya estaba corriendo
echo   - Las tablas ya estan disponibles para usar
echo.
pause

