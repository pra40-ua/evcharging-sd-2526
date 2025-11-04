@echo off
REM ============================================================
REM  SCRIPT DE DEMOSTRACION RAPIDA PARA EL PROFESOR
REM  
REM  Este script facilita la demostracion de las capacidades
REM  del sistema segun los requisitos de la entrega.
REM  
REM ============================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo    MENU DE DEMOSTRACION PARA EL PROFESOR
echo ============================================================
echo.

:MENU
echo.
echo Que deseas demostrar?
echo.
echo   INSTANCIAS MULTIPLES:
echo     [1] Añadir CPs dinamicamente (detecta existentes)
echo     [2] Añadir Drivers dinamicamente (detecta existentes)
echo.
echo   SIMULACION DE FALLOS:
echo     [3] Simular CRASH de un CP especifico
echo     [4] Simular CRASH de un Driver especifico
echo     [5] Simular CRASH de TODOS los Drivers
echo.
echo   INFORMACION:
echo     [6] Ver estado actual del sistema
echo     [7] Ver logs de un contenedor especifico
echo.
echo   GESTION:
echo     [8] Detener TODOS los contenedores de PC_B
echo     [9] Abrir dashboard web
echo.
echo     [0] Salir
echo.
set /p OPCION="Selecciona opcion: "

if "%OPCION%"=="1" goto ADD_CPS
if "%OPCION%"=="2" goto ADD_DRIVERS
if "%OPCION%"=="3" goto CRASH_CP
if "%OPCION%"=="4" goto CRASH_DRIVER
if "%OPCION%"=="5" goto CRASH_ALL_DRIVERS
if "%OPCION%"=="6" goto VER_ESTADO
if "%OPCION%"=="7" goto VER_LOGS
if "%OPCION%"=="8" goto DETENER_TODO
if "%OPCION%"=="9" goto ABRIR_WEB
if "%OPCION%"=="0" goto SALIR

echo.
echo [ERROR] Opcion no valida
goto MENU

REM ============================================================
:ADD_CPS
echo.
echo ============================================================
echo    AÑADIR CHARGING POINTS DINAMICAMENTE
echo ============================================================
call PC_B_RUN_MULTIPLE_CPS.bat
goto MENU

REM ============================================================
:ADD_DRIVERS
echo.
echo ============================================================
echo    AÑADIR DRIVERS DINAMICAMENTE
echo ============================================================
call PC_B_RUN_MULTIPLE_DRIVERS.bat
goto MENU

REM ============================================================
:CRASH_CP
echo.
echo ============================================================
echo    SIMULAR CRASH DE UN CP
echo ============================================================
echo.
echo CPs actualmente en ejecucion:
docker ps --filter "label=component=engine" --format "  - {{.Names}} ({{.Status}})"
echo.
set /p CP_NAME="Nombre del Engine a detener (ej: engine_CP_001): "
if "%CP_NAME%"=="" goto MENU

echo.
echo Simulando CRASH subito de %CP_NAME%...
docker kill %CP_NAME% 2>nul

REM Obtener el CP_ID del nombre
for /f "tokens=2 delims=_" %%a in ("%CP_NAME%") do set CP_ID=%%a

REM Detener tambien el monitor correspondiente
echo Deteniendo monitor correspondiente...
docker kill monitor_%CP_ID% 2>nul

echo.
echo [OK] CRASH simulado exitosamente
echo   - Engine: %CP_NAME% DETENIDO
echo   - Monitor: monitor_%CP_ID% DETENIDO
echo.
echo Verifica en el dashboard web que el CP aparece como DESCONECTADO
echo.
pause
goto MENU

REM ============================================================
:CRASH_DRIVER
echo.
echo ============================================================
echo    SIMULAR CRASH DE UN DRIVER
echo ============================================================
echo.
echo Drivers actualmente en ejecucion:
docker ps --filter "label=component=driver" --format "  - {{.Names}} ({{.Status}})"
echo.
set /p DRIVER_NAME="Nombre del Driver a detener (ej: driver_DRIVER_001): "
if "%DRIVER_NAME%"=="" goto MENU

echo.
echo Simulando CRASH subito de %DRIVER_NAME%...
docker kill %DRIVER_NAME% 2>nul

echo.
echo [OK] CRASH simulado exitosamente
echo   - Driver: %DRIVER_NAME% DETENIDO
echo.
pause
goto MENU

REM ============================================================
:CRASH_ALL_DRIVERS
echo.
echo ============================================================
echo    SIMULAR CRASH DE TODOS LOS DRIVERS
echo ============================================================
echo.
echo Drivers actualmente en ejecucion:
docker ps --filter "label=component=driver" --format "  - {{.Names}}"
echo.
set /p CONFIRM="Estas seguro? (S/N): "
if /i not "%CONFIRM%"=="S" goto MENU

echo.
echo Simulando CRASH masivo...
for /f %%i in ('docker ps -q --filter "label=component=driver"') do docker kill %%i

echo.
echo [OK] Todos los drivers detenidos
echo.
pause
goto MENU

REM ============================================================
:VER_ESTADO
echo.
echo ============================================================
echo    ESTADO ACTUAL DEL SISTEMA
echo ============================================================
echo.
echo CHARGING POINTS (Engines):
docker ps --filter "label=component=engine" --format "  {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo.
echo MONITORS:
docker ps --filter "label=component=monitor" --format "  {{.Names}}\t{{.Status}}"
echo.
echo DRIVERS:
docker ps --filter "label=component=driver" --format "  {{.Names}}\t{{.Status}}"
echo.
echo RESUMEN:
for /f %%i in ('docker ps -q --filter "label=component=engine" ^| find /c /v ""') do echo   CPs activos: %%i
for /f %%i in ('docker ps -q --filter "label=component=driver" ^| find /c /v ""') do echo   Drivers activos: %%i
echo.
pause
goto MENU

REM ============================================================
:VER_LOGS
echo.
echo ============================================================
echo    VER LOGS DE UN CONTENEDOR
echo ============================================================
echo.
echo Contenedores disponibles:
docker ps --filter "label=project=evcharging-pc-b" --format "  - {{.Names}}"
echo.
set /p CONTAINER_NAME="Nombre del contenedor: "
if "%CONTAINER_NAME%"=="" goto MENU

echo.
echo Mostrando logs de %CONTAINER_NAME%...
echo (Presiona Ctrl+C para salir)
echo.
docker logs -f %CONTAINER_NAME%
goto MENU

REM ============================================================
:DETENER_TODO
echo.
call PC_B_STOP_ALL.bat
goto MENU

REM ============================================================
:ABRIR_WEB
echo.
echo Abriendo dashboard web...
start http://localhost:8080
goto MENU

REM ============================================================
:SALIR
echo.
echo Saliendo...
exit /b 0

