@echo off
REM ============================================================
REM  SCRIPT DE RECONSTRUCCION PARA PC_B
REM  
REM  Este script reconstruye las imágenes Docker con los
REM  cambios más recientes en el código Python
REM ============================================================

setlocal
cd /d "%~dp0"

echo.
echo ============================================================
echo      PC_B - RECONSTRUCCION DE IMAGENES DOCKER
echo ============================================================
echo.
echo Este script reconstruirá las imágenes Docker para incluir
echo los cambios más recientes en el código.
echo.
echo Imágenes a reconstruir:
echo   - ev_monitor:local
echo   - ev_engine:local
echo.
pause

REM ============================================================
REM  DETENER CONTENEDORES ACTUALES
REM ============================================================
echo.
echo [1/3] Deteniendo contenedores actuales...
echo.

docker stop monitor 2>nul
docker stop engine 2>nul

echo Contenedores detenidos.
echo.

REM ============================================================
REM  RECONSTRUIR IMAGENES
REM ============================================================
echo.
echo [2/3] Reconstruyendo imágenes...
echo.

echo Reconstruyendo ev_monitor:local...
docker build -t ev_monitor:local -f ev_cp_monitor/Dockerfile .
if %errorlevel% neq 0 (
    echo [ERROR] No se pudo construir ev_monitor:local
    pause
    exit /b 1
)
echo.

echo Reconstruyendo ev_engine:local...
docker build -t ev_engine:local -f ev_cp_engine/Dockerfile .
if %errorlevel% neq 0 (
    echo [ERROR] No se pudo construir ev_engine:local
    pause
    exit /b 1
)
echo.

REM ============================================================
REM  VERIFICAR IMAGENES
REM ============================================================
echo.
echo [3/3] Verificando imágenes construidas...
echo.

docker images | findstr "ev_monitor\|ev_engine"
echo.

echo.
echo ============================================================
echo      RECONSTRUCCION COMPLETADA
echo ============================================================
echo.
echo Las imágenes han sido reconstruidas exitosamente.
echo.
echo SIGUIENTE PASO:
echo   1. Ejecuta commands_PC_B_build_engine.ps1 (en PowerShell)
echo   2. Ejecuta commands_PC_B_monitor.ps1 (en PowerShell)
echo.
echo O usa PC_B_RUN.bat para ejecutar todo automáticamente.
echo.
pause

exit /b 0

