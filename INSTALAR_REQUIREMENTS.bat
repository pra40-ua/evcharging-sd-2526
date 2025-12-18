@echo off
REM Script para instalar todas las dependencias del proyecto
REM Este script instala los requirements de todos los módulos

cd /d "%~dp0"

echo ============================================================
echo   INSTALANDO DEPENDENCIAS DEL PROYECTO
echo ============================================================
echo.

REM Verificar si Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no está instalado o no está en el PATH
    echo Por favor, instala Python 3.10 o superior
    pause
    exit /b 1
)

echo [INFO] Python detectado
python --version
echo.

REM Opción 1: Instalar en el entorno virtual si existe (Windows)
if exist venv\Scripts\activate.bat (
    echo [INFO] Activando entorno virtual existente...
    call venv\Scripts\activate.bat
    echo [OK] Entorno virtual activado
    echo.
) else if exist venv\bin\activate (
    echo [INFO] Entorno virtual detectado (Linux/WSL)
    echo [ADVERTENCIA] Este entorno virtual parece ser de Linux
    echo.
    echo ¿Deseas crear un nuevo entorno virtual para Windows? (S/N)
    set /p crear_venv=
    if /i "!crear_venv!"=="S" (
        echo.
        echo [INFO] Creando nuevo entorno virtual...
        python -m venv venv
        call venv\Scripts\activate.bat
        echo [OK] Entorno virtual creado y activado
        echo.
    )
) else (
    echo [INFO] No se encontró entorno virtual
    echo ¿Deseas crear uno? (S/N)
    set /p crear_venv=
    if /i "!crear_venv!"=="S" (
        echo.
        echo [INFO] Creando entorno virtual...
        python -m venv venv
        call venv\Scripts\activate.bat
        echo [OK] Entorno virtual creado y activado
        echo.
    ) else (
        echo [INFO] Instalando en el sistema global (no recomendado)
        echo.
    )
)

REM Actualizar pip
echo ============================================================
echo [1/4] Actualizando pip...
echo ============================================================
python -m pip install --upgrade pip
echo.

REM Instalar requirements principal
echo ============================================================
echo [2/4] Instalando requirements.txt principal...
echo ============================================================
if exist requirements.txt (
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Error instalando requirements.txt principal
        pause
        exit /b 1
    )
    echo [OK] requirements.txt principal instalado
) else (
    echo [ADVERTENCIA] No se encontró requirements.txt
)
echo.

REM Instalar requirements de EV_Registry
echo ============================================================
echo [3/4] Instalando requirements de EV_Registry...
echo ============================================================
if exist ev_registry\requirements.txt (
    pip install -r ev_registry\requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Error instalando ev_registry\requirements.txt
        pause
        exit /b 1
    )
    echo [OK] Requirements de EV_Registry instalados
) else (
    echo [ADVERTENCIA] No se encontró ev_registry\requirements.txt
)
echo.

REM Instalar requirements de EV_Weather
echo ============================================================
echo [4/4] Instalando requirements de EV_Weather...
echo ============================================================
if exist ev_weather\requirements.txt (
    pip install -r ev_weather\requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Error instalando ev_weather\requirements.txt
        pause
        exit /b 1
    )
    echo [OK] Requirements de EV_Weather instalados
) else (
    echo [ADVERTENCIA] No se encontró ev_weather\requirements.txt
)
echo.

echo ============================================================
echo   INSTALACION COMPLETADA
echo ============================================================
echo.
echo Para activar el entorno virtual en el futuro, ejecuta:
echo   venv\Scripts\activate.bat
echo.
echo O en PowerShell:
echo   venv\Scripts\Activate.ps1
echo.
pause

