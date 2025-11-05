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
    echo [OK] Todas las dependencias estan instaladas y actualizadas.
    echo.
) else (
    echo.
    echo [ADVERTENCIA] Hubo algun problema instalando dependencias.
    echo El script continuara de todas formas...
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


