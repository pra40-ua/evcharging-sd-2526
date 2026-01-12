@echo off
REM ============================================================
REM  SCRIPT DE INSTALACION PARA PC_A (ORDENADOR SERVIDOR CENTRAL)
REM  
REM  Este script instala las dependencias necesarias:
REM  - Verifica e instala Python
REM  - Instala dependencias (pip packages)
REM  - Verifica Docker
REM ============================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo      PC_A - INSTALACION DE DEPENDENCIAS
echo ============================================================
echo.
echo Este script realizara:
echo   [1] Verificacion de Python
echo   [2] Instalacion de dependencias Python
echo   [3] Verificacion de Docker
echo.
echo ============================================================
echo.
echo Presiona ENTER para continuar con la instalacion...
pause

REM ============================================================
REM  PASO 1: VERIFICAR PYTHON
REM ============================================================
echo.
echo ============================================================
echo [1/3] VERIFICANDO PYTHON
echo ============================================================
py --version >nul 2>&1
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
py --version
echo.

REM ============================================================
REM  PASO 2: INSTALAR DEPENDENCIAS PYTHON
REM ============================================================
echo ============================================================
echo [2/3] VERIFICANDO/INSTALANDO DEPENDENCIAS PYTHON
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
py -m pip install --upgrade pip --quiet --disable-pip-version-check 2>nul

echo.
echo Instalando/verificando dependencias desde requirements.txt...
echo (Esto puede tardar 1-2 minutos si necesita instalar paquetes)
echo.

REM Desinstalar kafka-python antiguo si existe (incompatible con Python 3.14+)
echo Verificando version de kafka-python...
py -m pip show kafka-python >nul 2>&1
if %errorlevel% equ 0 (
    echo Desinstalando kafka-python antiguo (incompatible)...
    py -m pip uninstall kafka-python -y --quiet >nul 2>&1
    echo [OK] kafka-python antiguo eliminado
)

REM Instalar directamente desde requirements.txt (pip salta los que ya estan instalados)
echo Instalando dependencias...
py -m pip install -r requirements.txt --quiet --disable-pip-version-check

if %errorlevel% equ 0 (
    echo.
    echo [OK] Instalacion de paquetes completada.
    echo.
) else (
    echo.
    echo [ADVERTENCIA] Hubo algun problema instalando dependencias.
    echo El script continuara de todas formas...
    echo.
)

REM Verificar que las dependencias criticas se instalaron correctamente
echo Verificando instalacion de dependencias criticas...
echo.

set DEPENDENCIAS_OK=1

REM Verificar kafka-python-ng
py -c "import kafka" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] kafka-python-ng NO se instalo correctamente.
    set DEPENDENCIAS_OK=0
) else (
    echo [OK] kafka-python-ng instalado correctamente.
)

REM Verificar pymysql o mysql.connector
py -c "import pymysql" >nul 2>&1
if %errorlevel% neq 0 (
    py -c "import mysql.connector" >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Ni pymysql ni mysql.connector estan instalados.
        set DEPENDENCIAS_OK=0
    ) else (
        echo [OK] mysql.connector instalado correctamente.
    )
) else (
    echo [OK] pymysql instalado correctamente.
)

REM Verificar flask
py -c "import flask" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] flask NO se instalo correctamente.
    set DEPENDENCIAS_OK=0
) else (
    echo [OK] flask instalado correctamente.
)

REM Verificar flask-socketio
py -c "import flask_socketio" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] flask-socketio NO se instalo correctamente.
    set DEPENDENCIAS_OK=0
) else (
    echo [OK] flask-socketio instalado correctamente.
)

REM Verificar rich
py -c "import rich" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] rich NO se instalo correctamente.
    set DEPENDENCIAS_OK=0
) else (
    echo [OK] rich instalado correctamente.
)

REM Verificar cryptography
py -c "import cryptography" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] cryptography NO se instalo correctamente.
    set DEPENDENCIAS_OK=0
) else (
    echo [OK] cryptography instalado correctamente.
)

REM Verificar requests
py -c "import requests" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] requests NO se instalo correctamente.
    set DEPENDENCIAS_OK=0
) else (
    echo [OK] requests instalado correctamente.
)

echo.
if !DEPENDENCIAS_OK! equ 0 (
    echo [ERROR] Algunas dependencias criticas NO se instalaron correctamente.
    echo.
    echo Por favor, ejecuta manualmente:
    echo   py -m pip install -r requirements.txt
    echo.
    echo Y luego ejecuta este script nuevamente.
    echo.
    pause
    exit /b 1
) else (
    echo [OK] Todas las dependencias criticas estan instaladas correctamente.
    echo.
)

echo Presiona una tecla para continuar al siguiente paso...
pause
echo.

REM ============================================================
REM  PASO 3: VERIFICAR DOCKER
REM ============================================================
echo ============================================================
echo [3/3] VERIFICANDO DOCKER
echo ============================================================
echo.
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker NO esta instalado.
    echo.
    echo ACCION REQUERIDA:
    echo   1. Descarga Docker Desktop: https://www.docker.com/products/docker-desktop/
    echo   2. Instala Docker Desktop
    echo   3. Reinicia el ordenador
    echo   4. Inicia Docker Desktop
    echo   5. Ejecuta este script nuevamente
    echo.
    pause
    exit /b 1
)

echo [OK] Docker encontrado:
docker --version
echo.

REM Verificar que Docker esta corriendo
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

echo [OK] Docker daemon esta corriendo.
echo.

REM Verificar que docker-compose esta disponible
docker compose version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ADVERTENCIA] docker-compose puede no estar disponible.
    echo Verificando con comando alternativo...
    docker-compose --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] docker-compose NO esta disponible.
        echo.
        echo ACCION REQUERIDA:
        echo   Docker Compose deberia venir con Docker Desktop.
        echo   Si no esta disponible, actualiza Docker Desktop.
        echo.
        pause
        exit /b 1
    ) else (
        echo [OK] docker-compose encontrado (comando alternativo).
    )
) else (
    echo [OK] docker compose encontrado.
)
echo.

REM ============================================================
REM  RESUMEN DE INSTALACION
REM ============================================================
echo.
echo ============================================================
echo      INSTALACION COMPLETADA
echo ============================================================
echo.
echo Todas las dependencias estan instaladas correctamente.
echo.
echo SIGUIENTE PASO:
echo   Para iniciar el servidor central y el dashboard, ejecuta:
echo     PC_A_RUN.bat
echo.
echo ============================================================
echo.
pause

exit /b 0



