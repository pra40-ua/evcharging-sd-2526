@echo off
REM ============================================================
REM  SCRIPT PARA DETENER TODOS LOS CONTENEDORES DE PC_B
REM  
REM  Este script detiene y elimina todos los contenedores
REM  de Charging Points lanzados desde PC_B.
REM  
REM ============================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo    DETENIENDO TODOS LOS CONTENEDORES DE PC_B
echo ============================================================
echo.

REM Verificar que Docker está corriendo
docker ps >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker no esta corriendo o no esta disponible.
    echo.
    pause
    exit /b 1
)

REM Contar cuántos contenedores hay
echo Buscando contenedores de EV Charging PC_B...
echo.

for /f %%i in ('docker ps -q --filter "label=project=evcharging-pc-b"') do set FOUND=1

if not defined FOUND (
    echo No se encontraron contenedores de PC_B en ejecucion.
    echo.
    echo Verifica que los CPs esten corriendo con: docker ps
    echo.
    pause
    exit /b 0
)

REM Mostrar contenedores que se van a detener
echo Contenedores que seran detenidos:
echo ----------------------------------------
docker ps --filter "label=project=evcharging-pc-b" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ----------------------------------------
echo.

REM Confirmar acción
set /p CONFIRM="¿Estas seguro de que quieres detener TODOS estos contenedores? (S/N): "
if /i not "%CONFIRM%"=="S" (
    echo.
    echo Operacion cancelada.
    echo.
    pause
    exit /b 0
)

echo.
echo Deteniendo contenedores...
echo.

REM Detener todos los contenedores con la etiqueta
docker stop $(docker ps -q --filter "label=project=evcharging-pc-b")

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo      TODOS LOS CONTENEDORES DETENIDOS EXITOSAMENTE
    echo ============================================================
    echo.
    echo Los contenedores han sido detenidos y eliminados.
    echo Las ventanas de PowerShell se cerraran automaticamente.
    echo.
) else (
    echo.
    echo [ERROR] Hubo un problema al detener los contenedores.
    echo Intenta manualmente: docker stop [nombre_contenedor]
    echo.
)

echo Presiona cualquier tecla para cerrar...
pause >nul

exit /b 0

