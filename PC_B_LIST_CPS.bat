@echo off
REM ============================================================
REM  SCRIPT PARA LISTAR TODOS LOS CONTENEDORES DE PC_B
REM  
REM  Este script muestra todos los contenedores de Charging
REM  Points que estan corriendo desde PC_B.
REM  
REM ============================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo    CONTENEDORES DE EV CHARGING - PC_B
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

echo Contenedores en ejecucion:
echo.
docker ps --filter "label=project=evcharging-pc-b" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo.
echo ============================================================
echo.
echo RESUMEN:
for /f %%i in ('docker ps -q --filter "label=project=evcharging-pc-b"') do set /a COUNT+=1
if not defined COUNT set COUNT=0
echo   Total de contenedores: %COUNT%
echo.

echo Filtros disponibles:
echo   - Engines:  docker ps --filter "label=component=engine"
echo   - Monitors: docker ps --filter "label=component=monitor"
echo.

echo Para detener todos:
echo   - Ejecuta: PC_B_STOP_ALL.bat
echo.

pause
exit /b 0

