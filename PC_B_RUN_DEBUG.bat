@echo off
setlocal EnableDelayedExpansion

REM Cambiar al directorio del script
cd /d "%~dp0"

echo ============================================================
echo   PC_B_RUN.bat - VERSION DEBUG
echo ============================================================
echo.
echo Este script mostrara TODOS los mensajes en pantalla
echo para ayudar a identificar el problema.
echo.
echo Presiona cualquier tecla para continuar...
pause >nul
echo.

REM Verificar Docker
echo [PASO 1] Verificando Docker...
docker --version
if %errorlevel% neq 0 (
    echo [ERROR] Docker no esta disponible
    echo Codigo de error: %errorlevel%
    pause
    exit /b 1
)
echo [OK] Docker esta disponible
echo.

REM Verificar archivo central_ip.txt
echo [PASO 2] Verificando central_ip.txt...
if exist central_ip.txt (
    set /p CENTRAL_IP=<central_ip.txt
    echo [OK] central_ip.txt encontrado
    echo [INFO] IP detectada: !CENTRAL_IP!
) else (
    set CENTRAL_IP=192.168.1.43
    echo [ADVERTENCIA] central_ip.txt no encontrado
    echo [INFO] Usando IP por defecto: !CENTRAL_IP!
)
echo.

REM Verificar Registry local
REM Nota: En un escenario normal, PC_B es otro ordenador y el Registry debería estar en PC_B
REM Pero también verificamos localhost por si se ejecuta todo en el mismo PC
echo [PASO 3] Verificando Registry local (puerto 6000)...
echo   - Intentando en 127.0.0.1:6000 (HTTPS)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $response = Invoke-WebRequest -Uri 'https://127.0.0.1:6000/api/health' -Method GET -SkipCertificateCheck -TimeoutSec 3 -ErrorAction Stop; Write-Host '[OK] Registry local detectado en 127.0.0.1 (HTTPS)'; exit 0 } catch { Write-Host '[INFO] Registry no disponible en 127.0.0.1 (HTTPS)'; exit 1 }"
if %errorlevel% equ 0 (
    set REGISTRY_URL=https://host.docker.internal:6000/api
    echo [OK] Registry URL configurado: !REGISTRY_URL!
    goto :registry_ok
)

echo   - Intentando en 127.0.0.1:6000 (HTTP)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $response = Invoke-WebRequest -Uri 'http://127.0.0.1:6000/api/health' -Method GET -TimeoutSec 3 -ErrorAction Stop; Write-Host '[OK] Registry local detectado en 127.0.0.1 (HTTP)'; exit 0 } catch { Write-Host '[INFO] Registry no disponible en 127.0.0.1 (HTTP)'; exit 1 }"
if %errorlevel% equ 0 (
    set REGISTRY_URL=http://host.docker.internal:6000/api
    echo [OK] Registry URL configurado: !REGISTRY_URL!
    goto :registry_ok
)

REM Verificar Registry en PC_A
echo [PASO 4] Verificando Registry en PC_A (!CENTRAL_IP!:6000)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $response = Invoke-WebRequest -Uri 'https://!CENTRAL_IP!:6000/api/health' -Method GET -SkipCertificateCheck -TimeoutSec 2 -ErrorAction Stop; Write-Host '[OK] Registry en PC_A detectado (HTTPS)'; exit 0 } catch { Write-Host '[INFO] Registry en PC_A no disponible (HTTPS)'; exit 1 }"
if %errorlevel% equ 0 (
    set REGISTRY_URL=https://!CENTRAL_IP!:6000/api
    echo [OK] Registry URL configurado: !REGISTRY_URL!
    goto :registry_ok
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $response = Invoke-WebRequest -Uri 'http://!CENTRAL_IP!:6000/api/health' -Method GET -TimeoutSec 2 -ErrorAction Stop; Write-Host '[OK] Registry en PC_A detectado (HTTP)'; exit 0 } catch { Write-Host '[INFO] Registry en PC_A no disponible (HTTP)'; exit 1 }"
if %errorlevel% equ 0 (
    set REGISTRY_URL=http://!CENTRAL_IP!:6000/api
    echo [OK] Registry URL configurado: !REGISTRY_URL!
    goto :registry_ok
)

echo.
echo [ERROR] Registry NO encontrado ni localmente ni en PC_A
echo.
echo El Registry es necesario para ejecutar los CPs.
echo.
echo Pasos:
echo   1. Ejecuta INICIAR_REGISTRY_PC_B.bat primero
echo   2. O asegurate de que el Registry este corriendo en PC_A
echo.
echo Presiona cualquier tecla para continuar de todas formas...
pause >nul
set REGISTRY_URL=

:registry_ok
echo.
echo ============================================================
echo   RESUMEN DE CONFIGURACION
echo ============================================================
echo   Central IP: !CENTRAL_IP!
echo   Registry URL: !REGISTRY_URL!
echo ============================================================
echo.
echo Presiona cualquier tecla para continuar al menu...
pause >nul
echo.

REM Llamar al script original
echo [INFO] Llamando al script original PC_B_RUN.bat...
echo.
call PC_B_RUN.bat

echo.
echo ============================================================
echo   PC_B_RUN_DEBUG.bat ha terminado
echo ============================================================
echo.
pause

