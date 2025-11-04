@echo off
REM ============================================================
REM  SCRIPT DE EJECUCION PARA PC_B CON DOCKER
REM  
REM  Este script ejecuta los componentes del sistema usando Docker:
REM  - Construye las imagenes Docker (Engine, Monitor, Driver)
REM  - Lanza Engine (CP_001)
REM  - Lanza Driver
REM  - Lanza Monitor
REM  
REM ============================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo    PC_B - EJECUCION CON DOCKER
echo ============================================================
echo.

REM ============================================================
REM  PASO 1: CONSTRUIR IMAGENES Y LANZAR ENGINE
REM ============================================================
echo ============================================================
echo [1/3] CONSTRUYENDO IMAGENES Y LANZANDO ENGINE
echo ============================================================
echo.

powershell -ExecutionPolicy Bypass -File commands_PC_B_build_engine.ps1
if %errorlevel% neq 0 (
    echo [ERROR] Fallo al construir imagenes o lanzar Engine
    pause
    exit /b 1
)

echo.
echo [OK] Engine iniciado
echo.
timeout /t 5 /nobreak >nul

REM ============================================================
REM  PASO 2: LANZAR DRIVER
REM ============================================================
echo ============================================================
echo [2/3] LANZANDO DRIVER
echo ============================================================
echo.

start "Driver-PC_B" powershell -ExecutionPolicy Bypass -NoExit -File commands_PC_B_driver.ps1

echo [OK] Driver iniciado en ventana separada
echo.
timeout /t 3 /nobreak >nul

REM ============================================================
REM  PASO 3: LANZAR MONITOR
REM ============================================================
echo ============================================================
echo [3/3] LANZANDO MONITOR
echo ============================================================
echo.

start "Monitor-PC_B" powershell -ExecutionPolicy Bypass -NoExit -File commands_PC_B_monitor.ps1

echo [OK] Monitor iniciado en ventana separada
echo.

REM ============================================================
REM  RESUMEN FINAL
REM ============================================================
echo.
echo ============================================================
echo      SISTEMA PC_B DOCKER INICIADO CORRECTAMENTE
echo ============================================================
echo.
echo Contenedores ejecutandose:
echo   - Engine:  CP_001 en puerto 5001
echo   - Driver:  DRIVER_456 (MAT: ABC-1234)
echo   - Monitor: CP_001
echo.
echo Ventanas abiertas:
echo   - Driver (PowerShell)
echo   - Monitor (PowerShell)
echo.
echo Para DETENER:
echo   - Presiona Ctrl+C en cada ventana de PowerShell
echo   - O ejecuta: docker stop engine driver monitor
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
echo (Los contenedores seguiran ejecutandose)
echo.
pause

exit /b 0

