@echo off
REM ============================================================
REM  SCRIPT COMPLETO PARA PC_B (ORDENADOR PUNTOS DE RECARGA)
REM  
REM  Este script hace TODO lo necesario:
REM  - Verifica e instala Python
REM  - Instala dependencias (pip packages)
REM  - Lee IP de Central desde central_ip.txt
REM  - Lanza multiples CPs (Engine + Monitor)
REM  - Lanza multiples Drivers
REM ============================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo    PC_B - PUNTOS DE RECARGA Y DRIVERS (SCRIPT COMPLETO)
echo ============================================================
echo.
echo Este script realizara:
echo   [1] Verificacion de Python
echo   [2] Instalacion de dependencias Python
echo   [3] Lectura de IP de Central (central_ip.txt)
echo   [4] Configuracion de parametros
echo   [5] Inicio de Puntos de Recarga (CPs)
echo   [6] Inicio de Drivers
echo.
pause

REM ============================================================
REM  PASO 1: VERIFICAR PYTHON
REM ============================================================
echo.
echo ============================================================
echo [1/6] VERIFICANDO PYTHON
echo ============================================================
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Python NO esta instalado.
    echo.
    echo ACCION REQUERIDA:
    echo   1. Descarga Python desde: https://www.python.org/downloads/
    echo   2. Durante instalacion, marca "Add Python to PATH"
    echo   3. Reinicia este script
    echo.
    pause
    exit /b 1
)

echo [OK] Python encontrado:
python --version
echo.

REM ============================================================
REM  PASO 2: INSTALAR DEPENDENCIAS PYTHON
REM ============================================================
echo ============================================================
echo [2/6] VERIFICANDO/INSTALANDO DEPENDENCIAS PYTHON
echo ============================================================
echo.
if not exist requirements.txt (
    echo [ERROR] No se encuentra requirements.txt
    echo Asegurate de ejecutar desde la raiz del proyecto.
    pause
    exit /b 1
)

REM Actualizar pip si es necesario
echo Actualizando pip...
python -m pip install --upgrade pip --quiet --disable-pip-version-check 2>nul

echo.
echo Verificando dependencias...
echo.

REM Leer requirements.txt y verificar cada paquete
set PACKAGES_TO_INSTALL=
set ALL_OK=1

for /F "tokens=1 delims==#" %%p in (requirements.txt) do (
    set PACKAGE=%%p
    set PACKAGE=!PACKAGE: =!
    
    REM Saltar líneas vacías y comentarios
    if not "!PACKAGE!"=="" if not "!PACKAGE:~0,1!"=="#" (
        REM Extraer nombre del paquete (sin versión)
        for /F "tokens=1 delims==<>!" %%n in ("!PACKAGE!") do (
            set PKG_NAME=%%n
            
            REM Verificar si el paquete ya está instalado
            python -m pip show !PKG_NAME! >nul 2>&1
            if !errorlevel! equ 0 (
                echo   [OK] !PKG_NAME! - Ya instalado
            ) else (
                echo   [--] !PKG_NAME! - Necesita instalarse
                set PACKAGES_TO_INSTALL=!PACKAGES_TO_INSTALL! !PACKAGE!
                set ALL_OK=0
            )
        )
    )
)

echo.

REM Si hay paquetes por instalar, instalarlos
if !ALL_OK! equ 0 (
    echo Instalando paquetes faltantes...
    echo (Esto puede tardar 1-2 minutos)
    echo.
    
    for %%p in (!PACKAGES_TO_INSTALL!) do (
        echo Instalando %%p...
        python -m pip install "%%p" --quiet --disable-pip-version-check
        if !errorlevel! equ 0 (
            echo   [OK] %%p instalado correctamente
        ) else (
            echo   [ERROR] No se pudo instalar %%p
        )
    )
    echo.
    echo [OK] Instalacion completada.
) else (
    echo [OK] Todas las dependencias ya estan instaladas.
)
echo.

REM ============================================================
REM  PASO 3: LEER IP DE CENTRAL
REM ============================================================
echo ============================================================
echo [3/6] CONFIGURACION DE CENTRAL
echo ============================================================
echo.

if exist central_ip.txt (
    set /p CENTRAL_IP=<central_ip.txt
    echo [OK] IP de Central leida desde central_ip.txt
    echo      IP Central: !CENTRAL_IP!
) else (
    echo [ADVERTENCIA] No se encuentra central_ip.txt
    echo.
    echo Puedes:
    echo   A) Copiar central_ip.txt desde PC_A
    echo   B) Introducir la IP manualmente ahora
    echo.
    set /p CENTRAL_IP="Introduce la IP de PC_A (ej: 192.168.1.43): "
    
    if "!CENTRAL_IP!"=="" (
        echo [ERROR] No se introdujo ninguna IP.
        pause
        exit /b 1
    )
    
    REM Guardar para proximas ejecuciones
    echo !CENTRAL_IP!> central_ip.txt
    echo [OK] IP guardada en central_ip.txt
)
echo.

REM ============================================================
REM  PASO 4: CONFIGURAR PARAMETROS
REM ============================================================
echo ============================================================
echo [4/6] CONFIGURACION DE PARAMETROS
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
pause >nul

REM ============================================================
REM  PASO 5: LANZAR PUNTOS DE RECARGA (CPs)
REM ============================================================
echo.
echo ============================================================
echo [5/6] LANZANDO PUNTOS DE RECARGA
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
    pause >nul
)

echo.
echo Lanzando CPs (esto abrira una ventana nueva)...
start "CPs-PC_B" cmd /k "python launch_multiple_cps.py --num !NUM_CPS! --central-ip !CENTRAL_IP! --central-port 5000 --kafka !CENTRAL_IP!:9092 --base-port 6000 --delay 1.0"

echo.
echo Esperando 10 segundos a que los CPs se registren...
for /L %%i in (1,1,10) do (
    echo|set /p="."
    timeout /t 1 /nobreak >nul
)
echo.
echo.

REM ============================================================
REM  PASO 6: LANZAR DRIVERS
REM ============================================================
echo ============================================================
echo [6/6] LANZANDO DRIVERS
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
start "Drivers-PC_B" cmd /k "python launch_multiple_drivers.py --num !NUM_DRIVERS! --kafka !CENTRAL_IP!:9092 --cps !NUM_CPS! --mode !MODE_STR! --delay 1.0"

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
echo     python web_dashboard.py --kafka !CENTRAL_IP!:9092
echo   Accede: http://localhost:8080
echo.
echo Para DETENER:
echo   - Cierra las ventanas de CPs y Drivers (Ctrl+C)
echo   - O cierra directamente las ventanas
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
echo (Los CPs y Drivers seguiran corriendo en sus ventanas)
echo.
pause >nul

exit /b 0

