@echo off
REM ============================================================
REM  SCRIPT DE EJECUCION PARA PC_B (ORDENADOR PUNTOS DE RECARGA)
REM  
REM  Este script ejecuta los componentes del sistema:
REM  - Lee IP de Central desde central_ip.txt
REM  - Lanza multiples CPs (Engine + Monitor)
REM  - Lanza multiples Drivers
REM  
REM  REQUISITO: Ejecutar PC_B_INSTALL.bat primero
REM ============================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo    PC_B - EJECUCION DE PUNTOS DE RECARGA Y DRIVERS
echo ============================================================
echo.

REM ============================================================
REM  VERIFICAR INSTALACION PREVIA
REM ============================================================
py --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python NO esta instalado o no esta en PATH.
    echo.
    echo Por favor, ejecuta primero: PC_B_INSTALL.bat
    echo.
    pause
    exit /b 1
)

if not exist central_ip.txt (
    echo [ERROR] No se encuentra central_ip.txt
    echo.
    echo Por favor, ejecuta primero: PC_B_INSTALL.bat
    echo.
    pause
    exit /b 1
)

REM ============================================================
REM  PASO 1: LEER IP DE CENTRAL
REM ============================================================
echo ============================================================
echo [1/4] CONFIGURACION DE CENTRAL
echo ============================================================
echo.

set CENTRAL_IP=
for /f "delims=" %%i in (central_ip.txt) do set CENTRAL_IP=%%i

if "!CENTRAL_IP!"=="" (
    echo [ERROR] El archivo central_ip.txt esta vacio.
    echo.
    echo Por favor, ejecuta primero: PC_B_INSTALL.bat
    echo.
    pause
    exit /b 1
)

echo [OK] IP de Central leida desde central_ip.txt
echo      IP Central: !CENTRAL_IP!
echo.

REM ============================================================
REM  PASO 2: CONFIGURAR PARAMETROS
REM ============================================================
echo ============================================================
echo [2/4] CONFIGURACION DE PARAMETROS
echo ============================================================
echo.
echo Cuantos PUNTOS DE RECARGA (CPs) quieres lanzar?
echo (Cada CP incluye Engine + Monitor)
echo.
set /p NUM_CPS="Numero de CPs [default: 3]: "
if "!NUM_CPS!"=="" set NUM_CPS=3

echo.
echo Cuantos DRIVERS (clientes) quieres lanzar?
echo.
set /p NUM_DRIVERS="Numero de Drivers [default: 2]: "
if "!NUM_DRIVERS!"=="" set NUM_DRIVERS=2

echo.
echo CONFIGURACION:
echo   - IP Central:    !CENTRAL_IP!
echo   - Kafka:         !CENTRAL_IP!:9092
echo   - Puerto Central: 5000
echo   - CPs a lanzar:  !NUM_CPS!
echo   - Drivers:       !NUM_DRIVERS!
echo.
echo Presiona una tecla para continuar o Ctrl+C para cancelar...
pause

REM ============================================================
REM  PASO 3: LANZAR PUNTOS DE RECARGA (CPs)
REM ============================================================
echo.
echo ============================================================
echo [3/4] LANZANDO PUNTOS DE RECARGA
echo ============================================================
echo.
echo Iniciando !NUM_CPS! Punto(s) de Recarga...
echo (Cada CP abrira una ventana: Engine + Monitor)
echo.

REM Verificar conectividad con Central antes de continuar
echo Verificando conectividad con Central (!CENTRAL_IP!:5000)...
powershell -Command "Test-NetConnection -ComputerName !CENTRAL_IP! -Port 5000 -InformationLevel Quiet" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Central es accesible.
) else (
    echo [ADVERTENCIA] No se puede conectar a Central en !CENTRAL_IP!:5000
    echo.
    echo Verifica:
    echo   - PC_A esta ejecutando EV_Central
    echo   - Firewall permite puerto 5000
    echo   - La IP !CENTRAL_IP! es correcta
    echo.
    echo Presiona una tecla para continuar de todas formas...
    pause
)

echo.
echo Lanzando CPs (esto abrira una ventana nueva)...
start "CPs-PC_B" cmd /k "py launch_multiple_cps.py --num !NUM_CPS! --central-ip !CENTRAL_IP! --central-port 5000 --kafka !CENTRAL_IP!:9092 --base-port 6000 --delay 1.0"

echo.
echo Esperando 10 segundos a que los CPs se registren...
for /L %%i in (1,1,10) do (
    echo|set /p="."
    timeout /t 1 /nobreak >nul
)
echo.
echo.

REM ============================================================
REM  PASO 4: LANZAR DRIVERS
REM ============================================================
echo ============================================================
echo [4/4] LANZANDO DRIVERS
echo ============================================================
echo.
echo Iniciando !NUM_DRIVERS! Driver(s)...
echo.
echo Modo de asignacion:
echo   [1] Random   - Asignacion aleatoria a CPs
echo   [2] Uniform  - Distribucion uniforme (round-robin)
echo   [3] First    - Todos al primer CP (prueba saturacion)
echo.
set /p DRIVER_MODE="Selecciona modo [1-3, default: 1]: "
if "!DRIVER_MODE!"=="" set DRIVER_MODE=1

if "!DRIVER_MODE!"=="1" set MODE_STR=random
if "!DRIVER_MODE!"=="2" set MODE_STR=uniform
if "!DRIVER_MODE!"=="3" set MODE_STR=first
if "!DRIVER_MODE!" gtr 3 set MODE_STR=random

echo.
echo Modo seleccionado: !MODE_STR!
echo.
echo Lanzando Drivers (esto abrira una ventana nueva)...
start "Drivers-PC_B" cmd /k "py launch_multiple_drivers.py --num !NUM_DRIVERS! --kafka !CENTRAL_IP!:9092 --cps !NUM_CPS! --mode !MODE_STR! --delay 1.0"

echo.
echo Esperando 5 segundos...
timeout /t 5 /nobreak >nul

REM ============================================================
REM  RESUMEN FINAL
REM ============================================================
echo.
echo ============================================================
echo      SISTEMA PC_B INICIADO CORRECTAMENTE
echo ============================================================
echo.
echo Configuracion:
echo   - Central:        !CENTRAL_IP!:5000
echo   - Kafka:          !CENTRAL_IP!:9092
echo   - CPs lanzados:   !NUM_CPS!
echo   - Drivers:        !NUM_DRIVERS!
echo   - Modo drivers:   !MODE_STR!
echo.
echo Ventanas abiertas:
echo   - CPs (Engine + Monitor por cada CP)
echo   - Drivers
echo.
echo Puertos usados localmente:
echo   - Engines: 6001-60!NUM_CPS! (cada Engine en un puerto)
echo.
echo VERIFICACION:
echo   - Ve a la ventana de EV_Central en PC_A
echo   - Deberias ver los !NUM_CPS! CPs registrados
echo   - Deberias ver las solicitudes de los !NUM_DRIVERS! Drivers
echo.
echo DASHBOARD (opcional):
echo   Si quieres ver el dashboard web, ejecuta en cualquier PC:
echo     py web_dashboard.py --kafka !CENTRAL_IP!:9092
echo   Accede: http://localhost:8080
echo.
echo Para DETENER:
echo   - Cierra las ventanas de CPs y Drivers (Ctrl+C)
echo   - O cierra directamente las ventanas
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
echo (Los CPs y Drivers seguiran corriendo en sus ventanas)
echo.
pause

exit /b 0

