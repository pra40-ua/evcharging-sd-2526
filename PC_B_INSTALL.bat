@echo off
REM ============================================================
REM  SCRIPT DE INSTALACION PARA PC_B (ORDENADOR PUNTOS DE RECARGA)
REM  
REM  Este script instala las dependencias necesarias:
REM  - Verifica e instala Python
REM  - Instala dependencias (pip packages)
REM  - Configura IP de Central desde central_ip.txt
REM ============================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo    PC_B - INSTALACION DE DEPENDENCIAS
echo ============================================================
echo.
echo Este script realizara:
echo   [1] Verificacion de Python
echo   [2] Instalacion de dependencias Python
echo   [3] Configuracion de IP de Central
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
echo [2/3] VERIFICANDO/INSTALANDO DEPENDENCIAS PYTHON
echo ============================================================
echo.
if not exist requirements.txt (
    echo [ERROR] No se encuentra requirements.txt
    echo Asegurate de ejecutar desde la raiz del proyecto.
    echo.
    pause
    exit /b 1
)

REM Actualizar pip si es necesario
echo Actualizando pip...
python -m pip install --upgrade pip --quiet --disable-pip-version-check 2>nul

echo.
echo Instalando/verificando dependencias desde requirements.txt...
echo (Esto puede tardar 1-2 minutos si necesita instalar paquetes)
echo.

REM Instalar directamente desde requirements.txt (pip salta los que ya estan instalados)
python -m pip install -r requirements.txt --quiet --disable-pip-version-check

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
cls
echo.

REM ============================================================
REM  PASO 3: CONFIGURAR IP DE CENTRAL
REM ============================================================
echo ============================================================
echo [3/3] CONFIGURACION DE CENTRAL
echo ============================================================
echo.

set CENTRAL_IP=

if exist central_ip.txt (
    for /f "delims=" %%i in (central_ip.txt) do set CENTRAL_IP=%%i
    
    if "!CENTRAL_IP!"=="" (
        echo [ERROR] El archivo central_ip.txt existe pero esta vacio.
        echo.
        set /p CENTRAL_IP="Introduce la IP de PC_A (ej: 192.168.1.43): "
        if "!CENTRAL_IP!"=="" (
            echo [ERROR] No se introdujo ninguna IP.
            echo.
            pause
            exit /b 1
        )
        echo !CENTRAL_IP!> central_ip.txt
    )
    
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
        echo.
        pause
        exit /b 1
    )
    
    REM Guardar para proximas ejecuciones
    echo !CENTRAL_IP!> central_ip.txt
    echo [OK] IP guardada en central_ip.txt
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
echo Dependencias instaladas correctamente.
echo IP de Central configurada: !CENTRAL_IP!
echo.
echo SIGUIENTE PASO:
echo   Para ejecutar los Puntos de Recarga y Drivers, ejecuta:
echo     PC_B_RUN.bat
echo.
echo ============================================================
echo.
pause

exit /b 0

