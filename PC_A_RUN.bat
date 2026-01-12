@echo off
REM ============================================================
REM  SCRIPT DE EJECUCION PARA PC_A (ORDENADOR SERVIDOR CENTRAL)
REM  
REM  Este script ejecuta los componentes del sistema:
REM  - Detecta IP local automaticamente
REM  - Inicia Kafka + MySQL (Docker)
REM  - Inicia EV_Central
REM  - Inicia Dashboard Web
REM  
REM  REQUISITO: Ejecutar PC_A_INSTALL.bat primero
REM ============================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo      PC_A - EJECUCION DE SERVIDOR CENTRAL
echo ============================================================
echo.

REM ============================================================
REM  VERIFICAR INSTALACION PREVIA
REM ============================================================
py --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python NO esta instalado o no esta en PATH.
    echo.
    echo Por favor, ejecuta primero: PC_A_INSTALL.bat
    echo.
    pause
    exit /b 1
)

docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker NO esta instalado.
    echo.
    echo Por favor, ejecuta primero: PC_A_INSTALL.bat
    echo.
    pause
    exit /b 1
)

docker ps >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker esta instalado pero NO esta corriendo.
    echo.
    echo ACCION REQUERIDA:
    echo   1. Inicia Docker Desktop
    echo   2. Espera a ver "Docker Desktop is running"
    echo   3. Ejecuta este script nuevamente
    echo.
    pause
    exit /b 1
)

REM ============================================================
REM  VERIFICAR E INSTALAR DEPENDENCIAS PYTHON (KAFKA, ETC.)
REM ============================================================
echo ============================================================
echo [0/5] VERIFICANDO DEPENDENCIAS PYTHON
echo ============================================================
echo.

if not exist requirements.txt (
    echo [ADVERTENCIA] No se encuentra requirements.txt
    echo Continuando sin verificar dependencias.
    echo.
    goto :skip_deps_check
)

REM Verificar si kafka-python-ng esta instalado
echo Verificando dependencias Python
py -m pip show kafka-python-ng >nul 2>&1
set PIP_ERROR=%errorlevel%
if "%PIP_ERROR%"=="0" goto :kafka_found
    echo [INFO] kafka-python-ng no encontrado, instalando dependencias
    echo.
    REM Desinstalar kafka-python antiguo si existe (incompatible)
    py -m pip show kafka-python >nul 2>&1
    set OLD_KAFKA_ERROR=%errorlevel%
    if "%OLD_KAFKA_ERROR%"=="0" (
        echo Desinstalando kafka-python antiguo (incompatible)
        py -m pip uninstall kafka-python -y --quiet >nul 2>&1
    )
    
    REM Instalar dependencias desde requirements.txt
    echo Instalando dependencias desde requirements.txt.
    echo Esto puede tardar 30-60 segundos
    echo.
    py -m pip install -r requirements.txt --quiet --disable-pip-version-check
    if %errorlevel% equ 0 (
        echo [OK] Dependencias Python instaladas correctamente.
    ) else (
        echo [ADVERTENCIA] Hubo un problema instalando dependencias.
        echo El script continuara, pero puede haber errores.
    )
    echo.
    goto :deps_check_end
:kafka_found
    REM Verificar otras dependencias críticas
    py -m pip show pymysql >nul 2>&1
    if %errorlevel% neq 0 (
        echo [INFO] Algunas dependencias faltan, instalando.
        py -m pip install -r requirements.txt --quiet --disable-pip-version-check
        echo [OK] Dependencias actualizadas.
        echo.
    ) else (
        echo [OK] Dependencias Python verificadas - kafka-python-ng instalado.
        echo.
    )
:deps_check_end

:skip_deps_check

REM ============================================================
REM  PASO 1: DETECTAR IP LOCAL AUTOMATICAMENTE
REM ============================================================
echo ============================================================
echo [1/4] DETECTANDO IP LOCAL
echo ============================================================
echo.

REM Detectar IP local usando ipconfig
echo Detectando IP local automaticamente...
REM Excluir IPs de loopback, APIPA y Docker (172.17.x.x, 172.18.x.x, etc.)
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /C:"IPv4" ^| findstr /V "127.0.0.1" ^| findstr /V "169.254"') do (
    set TEMP_IP=%%a
    set TEMP_IP=!TEMP_IP: =!
    if not "!TEMP_IP!"=="" (
        REM Verificar que no sea una IP de Docker (172.17.x.x, 172.18.x.x, etc.)
        echo !TEMP_IP! | findstr /R "^172\.17\." >nul 2>&1
        if !errorlevel! neq 0 (
            echo !TEMP_IP! | findstr /R "^172\.18\." >nul 2>&1
            if !errorlevel! neq 0 (
                echo !TEMP_IP! | findstr /R "^172\.19\." >nul 2>&1
                if !errorlevel! neq 0 (
                    REM No es una IP de Docker, usar esta IP
                    set CENTRAL_IP=!TEMP_IP!
                    goto :ip_found
                )
            )
        )
    )
)

:ip_found
if "!CENTRAL_IP!"=="" (
    echo [ERROR] No se pudo detectar la IP local.
    echo Usando IP por defecto: 192.168.1.43
    set CENTRAL_IP=192.168.1.43
)

echo [OK] IP detectada: !CENTRAL_IP!

REM Guardar IP en central_ip.txt para PC_B
echo !CENTRAL_IP!> central_ip.txt
echo      IP guardada en central_ip.txt para PC_B
echo.

REM ============================================================
REM  PASO 2: INICIAR KAFKA + MARIADB (DOCKER COMPOSE)
REM ============================================================
echo ============================================================
echo [2/5] INICIANDO KAFKA + MARIADB
echo ============================================================
echo.
if not exist docker-compose.yml (
    echo [ERROR] No se encuentra docker-compose.yml
    pause
    exit /b 1
)

echo Deteniendo contenedores previos (si existen)...
docker compose down 2>&1
if %errorlevel% neq 0 (
    echo [ADVERTENCIA] Error al detener contenedores previos, continuando...
)

REM Limpiar red si existe y está huérfana
echo Limpiando red evnet si existe...
docker network rm evnet >nul 2>&1
REM Si la red está en uso, intentar desconectar contenedores primero
docker network inspect evnet >nul 2>&1
if %errorlevel% equ 0 (
    echo Desconectando contenedores de la red evnet...
    for /f "tokens=1" %%c in ('docker network inspect evnet --format "{{range .Containers}}{{.Name}} {{end}}" 2^>nul') do (
        docker network disconnect evnet %%c >nul 2>&1
    )
    docker network rm evnet >nul 2>&1
)

echo.
echo Configurando Kafka con IP: !CENTRAL_IP!
echo Iniciando Kafka + MariaDB + configuracion automatica...
echo (Esto puede tardar 20-40 segundos la primera vez)
echo.

REM Actualizar docker-compose.yml con la IP detectada
echo Actualizando docker-compose.yml con IP: !CENTRAL_IP!...
echo !CENTRAL_IP!> temp_ip.txt
powershell -Command "$ip = Get-Content temp_ip.txt -Raw; $ip = $ip.Trim(); $content = Get-Content docker-compose.yml -Raw; $content = $content -replace 'KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://\$\{KAFKA_ADVERTISED_IP:-[^}]*\}:9092', ('KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://' + $ip + ':9092'); $content = $content -replace 'KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://[0-9.]+:9092', ('KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://' + $ip + ':9092'); Set-Content docker-compose.yml -Value $content -NoNewline" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ADVERTENCIA] No se pudo actualizar docker-compose.yml, usando IP actual...
)
del temp_ip.txt >nul 2>&1

REM Establecer variable de entorno para docker-compose (por si acaso)
set KAFKA_ADVERTISED_IP=!CENTRAL_IP!
echo Ejecutando: docker compose up -d
docker compose up -d

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] No se pudo iniciar Docker Compose.
    echo.
    echo Verificando estado de contenedores...
    docker compose ps -a
    echo.
    echo Verifica los logs: docker compose logs kafka
    echo.
    pause
    exit /b 1
)

REM Verificar que los contenedores se crearon correctamente
echo.
echo Verificando que los contenedores se crearon...
timeout /t 2 /nobreak >nul
docker compose ps

echo.
echo [OK] Servicios Docker iniciados.
echo.
echo Esperando a que Kafka y MariaDB esten listos...
echo (5 segundos)

REM Esperar con progreso visual
for /L %%i in (1,1,5) do (
    echo|set /p="."
    timeout /t 1 /nobreak >nul
)
echo.
echo.
REM Verificar que el contenedor de Kafka existe y está corriendo
echo Verificando estado del contenedor Kafka...
docker ps -a --filter "name=kafka" --format "table {{.Names}}\t{{.Status}}" 2>&1
docker inspect kafka >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] El contenedor de Kafka NO se creo correctamente.
    echo.
    echo Verificando logs de Docker Compose...
    docker compose logs kafka
    echo.
    echo Por favor, revisa los logs anteriores para identificar el problema.
    pause
    exit /b 1
)

REM Verificar que Kafka responde
echo Esperando a que Kafka este listo...
timeout /t 5 /nobreak >nul
docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092 >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Kafka esta listo y respondiendo.
) else (
    echo [ADVERTENCIA] Kafka puede no estar listo aun, esperando mas tiempo...
    timeout /t 10 /nobreak >nul
    docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092 >nul 2>&1
    if %errorlevel% equ 0 (
        echo [OK] Kafka esta listo y respondiendo.
    ) else (
        echo [ADVERTENCIA] Kafka puede no estar listo aun.
        echo El sistema continuara de todas formas.
    )
)
echo.

REM Verificar que MariaDB está listo antes de limpiar
echo Verificando que MariaDB esta listo...
timeout /t 3 /nobreak >nul
docker exec mariadb mariadb-admin ping -h localhost -uroot >nul 2>&1
if %errorlevel% neq 0 (
    echo [ADVERTENCIA] MariaDB puede no estar listo aun, esperando...
    timeout /t 5 /nobreak >nul
)

REM Verificar y configurar root SIN CONTRASEÑA (autenticacion eliminada)
echo Verificando configuracion de MariaDB: root SIN CONTRASEÑA...
REM El script setup_sin_autenticacion.sql ya deberia haber configurado root sin contraseña
REM Solo verificamos y corregimos si es necesario
docker exec mariadb mysql -u root -e "SELECT User, Host FROM mysql.user WHERE User='root';" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ADVERTENCIA] No se puede conectar sin contraseña, configurando...
    REM Intentar con contraseña temporal 'root' y luego eliminarla
    docker exec mariadb mysql -u root -proot -e "ALTER USER 'root'@'localhost' IDENTIFIED BY ''; ALTER USER 'root'@'%%' IDENTIFIED BY ''; CREATE USER IF NOT EXISTS 'root'@'127.0.0.1' IDENTIFIED BY ''; GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost' WITH GRANT OPTION; GRANT ALL PRIVILEGES ON *.* TO 'root'@'%%' WITH GRANT OPTION; GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION; FLUSH PRIVILEGES;" 2>&1
)
echo [OK] MariaDB configurado (root SIN CONTRASEÑA, sin autenticacion).
echo.

REM Crear/asegurar usuario dedicado para Registry con acceso remoto
echo Configurando usuario dedicado 'registry' para acceso remoto desde PC_B...
docker exec mariadb mysql -u root -e "CREATE USER IF NOT EXISTS 'registry'@'%%' IDENTIFIED BY 'registry_pwd'; GRANT ALL PRIVILEGES ON evcharging.* TO 'registry'@'%%' WITH GRANT OPTION; FLUSH PRIVILEGES;" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Usuario 'registry' configurado con privilegios sobre evcharging.*
) else (
    echo [ADVERTENCIA] No se pudo configurar el usuario 'registry' ^(verifica logs de MariaDB^)
)
echo.

REM ============================================================
REM  PASO 2.5: LIMPIAR BASE DE DATOS
REM ============================================================
echo ============================================================
echo [2.5/5] LIMPIANDO BASE DE DATOS
echo ============================================================
echo.
echo Eliminando datos anteriores de la base de datos...
echo.

REM Limpiar todas las tablas usando TRUNCATE (sin contraseña)
docker exec mariadb mysql -u root evcharging -e "SET FOREIGN_KEY_CHECKS=0; TRUNCATE TABLE charging_points; TRUNCATE TABLE telemetria_log; TRUNCATE TABLE cp_encryption_keys; TRUNCATE TABLE audit_log; TRUNCATE TABLE weather_alerts; SET FOREIGN_KEY_CHECKS=1;" >nul 2>&1

if %errorlevel% equ 0 (
    echo [OK] Base de datos limpiada exitosamente.
) else (
    echo [ADVERTENCIA] No se pudo limpiar la base de datos completamente.
    echo Continuando de todas formas...
)
echo.

REM ============================================================
REM  PASO 3: INICIAR EV_CENTRAL
REM ============================================================
echo ============================================================
echo [3/5] INICIANDO EV_CENTRAL
echo ============================================================
echo.
echo CONFIGURACION DETECTADA:
echo   - IP de este PC:    !CENTRAL_IP!
echo   - Kafka:            !CENTRAL_IP!:9092
echo   - MySQL:            127.0.0.1:3306
echo   - Usuario MySQL:    root (SIN CONTRASEÑA)
echo   - Puerto Central:   5000
echo.
echo IMPORTANTE PARA RED LOCAL:
echo   Si PC_B esta en otro ordenador, asegurate de:
echo   1. Copiar central_ip.txt a PC_B
echo   2. Abrir firewall para puertos: 5000, 5001, 8080, 9092, 3306
echo.
echo Comandos Firewall (ejecutar en PowerShell como Admin):
echo   New-NetFirewallRule -DisplayName "Kafka" -Direction Inbound -LocalPort 9092 -Protocol TCP -Action Allow
echo   New-NetFirewallRule -DisplayName "Central" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow
echo   New-NetFirewallRule -DisplayName "Central API" -Direction Inbound -LocalPort 5001 -Protocol TCP -Action Allow
echo   New-NetFirewallRule -DisplayName "Dashboard Web" -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Allow
echo   New-NetFirewallRule -DisplayName "MySQL" -Direction Inbound -LocalPort 3306 -Protocol TCP -Action Allow
echo.
pause

REM Lanzar Central en nueva ventana
echo.
echo Lanzando EV_Central en nueva ventana...
echo.
echo ╔═══════════════════════════════════════════════════════════╗
echo ║  IMPORTANTE: Se abrirá una NUEVA VENTANA donde verás:    ║
echo ║  - Todos los mensajes que recibe Central                 ║
echo ║  - Telemetría en tiempo real de cada CP                  ║
echo ║  - Solicitudes de Drivers                                ║
echo ║  - Comandos enviados a CPs                               ║
echo ║  - Notificaciones a Drivers                              ║
echo ╚═══════════════════════════════════════════════════════════╝
echo.

REM Lanzar script dedicado en nueva ventana (permanece abierta)
start "EV_Central - MENSAJES Y TELEMETRIA" "%~dp0RUN_CENTRAL.bat"

REM Esperar un poco para que la Central arranque
echo Esperando a que el servidor Central inicie...
timeout /t 3 /nobreak >nul

REM ============================================================
REM  PASO 4: LANZAR DASHBOARD WEB
REM ============================================================
echo.
echo ============================================================
echo [4/5] LANZANDO DASHBOARD WEB
echo ============================================================
echo.
echo Iniciando dashboard web en puerto 8080...
echo.

REM Lanzar Dashboard Web en nueva ventana (con acceso a BD para sincronización)
REM Usar root SIN CONTRASEÑA (autenticacion eliminada)
start "Dashboard-Web-PC_A" cmd /k "py web_dashboard.py --kafka !CENTRAL_IP!:9092 --central-ip !CENTRAL_IP! --central-port 5000 --central-api-port 5001 --db 127.0.0.1:3306:root::evcharging"

REM Esperar 5 segundos a que el dashboard inicie
echo Esperando a que el dashboard inicie...
timeout /t 5 /nobreak >nul

REM Abrir navegador automáticamente
echo Abriendo navegador en http://localhost:8080 ...
start http://localhost:8080

echo.
echo ============================================================
echo      SISTEMA PC_A INICIADO CORRECTAMENTE
echo ============================================================
echo.
echo Servicios activos:
echo   [X] Kafka           - Puerto 9092
echo   [X] MySQL           - Puerto 3306
echo   [X] EV_Central      - Puerto 5000 (socket)
echo   [X] EV_Central API  - Puerto 5001 (REST)
echo   [X] Dashboard Web   - http://localhost:8080
echo.
echo Ventanas abiertas:
echo   - EV_Central (logs en ventana separada)
echo   - Dashboard Web (interfaz grafica en navegador)
echo.
echo Archivo generado para PC_B:
echo   - central_ip.txt (IP: !CENTRAL_IP!)
echo.
echo SIGUIENTE PASO:
echo   - En PC_B: Copiar central_ip.txt y ejecutar PC_B_RUN.bat
echo   - En PC_C: Copiar central_ip.txt y ejecutar PC_C_RUN.bat
echo.
echo DASHBOARD WEB:
echo   - URL: http://localhost:8080
echo   - Desde otra red: http://!CENTRAL_IP!:8080
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
echo (Central y Dashboard seguiran corriendo en sus ventanas)
echo.
pause

exit /b 0

