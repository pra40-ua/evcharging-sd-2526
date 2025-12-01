@echo off
REM ============================================================
REM  DIAGNOSTICO Y CONFIGURACION DE OPENSSL
REM ============================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo   DIAGNOSTICO DE OPENSSL
echo ============================================================
echo.

REM 1. Verificar si OpenSSL está en PATH
echo [1/5] Verificando si OpenSSL esta en PATH...
openssl version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] OpenSSL encontrado en PATH
    openssl version
    echo.
    echo OpenSSL esta funcionando correctamente!
    pause
    exit /b 0
) else (
    echo [INFO] OpenSSL no encontrado en PATH
    echo.
)

REM 2. Buscar OpenSSL en ubicaciones comunes
echo [2/5] Buscando OpenSSL en ubicaciones comunes...
echo.

set FOUND=0
set OPENSSL_PATH=

REM Buscar en ubicaciones comunes (una por una para evitar problemas con arrays)
if exist "C:\Program Files\OpenSSL-Win64\bin\openssl.exe" (
    echo [ENCONTRADO] C:\Program Files\OpenSSL-Win64\bin\openssl.exe
    set "OPENSSL_PATH=C:\Program Files\OpenSSL-Win64\bin\openssl.exe"
    set FOUND=1
    goto :check_found
)

if exist "C:\Program Files (x86)\OpenSSL-Win64\bin\openssl.exe" (
    echo [ENCONTRADO] C:\Program Files (x86)\OpenSSL-Win64\bin\openssl.exe
    set "OPENSSL_PATH=C:\Program Files (x86)\OpenSSL-Win64\bin\openssl.exe"
    set FOUND=1
    goto :check_found
)

if exist "C:\OpenSSL-Win64\bin\openssl.exe" (
    echo [ENCONTRADO] C:\OpenSSL-Win64\bin\openssl.exe
    set "OPENSSL_PATH=C:\OpenSSL-Win64\bin\openssl.exe"
    set FOUND=1
    goto :check_found
)

if exist "C:\Program Files\OpenSSL\bin\openssl.exe" (
    echo [ENCONTRADO] C:\Program Files\OpenSSL\bin\openssl.exe
    set "OPENSSL_PATH=C:\Program Files\OpenSSL\bin\openssl.exe"
    set FOUND=1
    goto :check_found
)

if exist "C:\OpenSSL\bin\openssl.exe" (
    echo [ENCONTRADO] C:\OpenSSL\bin\openssl.exe
    set "OPENSSL_PATH=C:\OpenSSL\bin\openssl.exe"
    set FOUND=1
    goto :check_found
)

if exist "C:\Program Files\Git\usr\bin\openssl.exe" (
    echo [ENCONTRADO] C:\Program Files\Git\usr\bin\openssl.exe
    set "OPENSSL_PATH=C:\Program Files\Git\usr\bin\openssl.exe"
    set FOUND=1
    goto :check_found
)

if exist "C:\Program Files (x86)\Git\usr\bin\openssl.exe" (
    echo [ENCONTRADO] C:\Program Files (x86)\Git\usr\bin\openssl.exe
    set "OPENSSL_PATH=C:\Program Files (x86)\Git\usr\bin\openssl.exe"
    set FOUND=1
    goto :check_found
)

:check_found

if !FOUND! equ 0 (
    echo [INFO] No se encontro OpenSSL en ubicaciones comunes
    echo.
    echo [3/5] Buscando en unidad C:...
    echo.
    
    REM Buscar solo en C: (búsqueda completa es muy lenta)
    for /f "delims=" %%f in ('dir /s /b C:\openssl.exe 2^>nul ^| findstr /i "openssl.exe"') do (
        if exist "%%f" (
            echo [ENCONTRADO] %%f
            set "OPENSSL_PATH=%%f"
            set FOUND=1
            goto :found
        )
    )
    :found
)

if !FOUND! equ 0 (
    echo.
    echo ============================================================
    echo   OPENSSL NO ENCONTRADO
    echo ============================================================
    echo.
    echo OpenSSL no se encuentra instalado o no esta en las ubicaciones
    echo comunes. Posibles soluciones:
    echo.
    echo 1. Verifica que OpenSSL se instalo correctamente
    echo 2. Busca manualmente openssl.exe en tu sistema
    echo 3. Reinstala OpenSSL y asegurate de marcar "Add to PATH"
    echo 4. O usa el script de PowerShell: generar_certificados_ssl.ps1
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   OPENSSL ENCONTRADO
echo ============================================================
echo.
echo Ruta: %OPENSSL_PATH%
echo.

REM 3. Verificar que funciona
echo [3/5] Verificando que OpenSSL funciona...
"%OPENSSL_PATH%" version
if %errorlevel% neq 0 (
    echo [ERROR] OpenSSL encontrado pero no funciona correctamente
    pause
    exit /b 1
)

echo [OK] OpenSSL funciona correctamente
echo.

REM 4. Obtener la ruta del directorio
for %%F in ("%OPENSSL_PATH%") do set "OPENSSL_DIR=%%~dpF"
set "OPENSSL_DIR=%OPENSSL_DIR:~0,-1%"

echo [4/5] Directorio de OpenSSL: %OPENSSL_DIR%
echo.

REM Si hay múltiples instalaciones, preferir OpenSSL-Win64 sobre Git
if not "%OPENSSL_PATH%"=="" (
    echo "%OPENSSL_PATH%" | findstr /i "OpenSSL-Win64" >nul
    if %errorlevel% equ 0 (
        echo [INFO] Usando instalacion principal de OpenSSL
    ) else (
        echo [INFO] Usando OpenSSL de Git (funcional pero puede ser version antigua)
    )
)
echo.

REM 5. Ofrecer agregar al PATH
echo [5/5] Configuracion del PATH
echo.
echo OpenSSL esta instalado pero no esta en el PATH del sistema.
echo.
echo OPCIONES:
echo.
echo A) Usar ruta completa en los scripts (Recomendado para pruebas)
echo    Los scripts usaran: %OPENSSL_PATH%
echo.
echo B) Agregar manualmente al PATH del sistema
echo    1. Copia esta ruta: %OPENSSL_DIR%
echo    2. Win+X -^> Sistema -^> Configuracion avanzada
echo    3. Variables de entorno -^> Editar "Path"
echo    4. Nuevo -^> Pega la ruta -^> Aceptar
echo    5. Reinicia la terminal
echo.
echo C) Usar script de PowerShell (No requiere OpenSSL en PATH)
echo    .\generar_certificados_ssl.ps1
echo.
set /p CHOICE="Selecciona opcion (A/B/C) o Enter para salir: "

if /i "!CHOICE!"=="A" (
    echo.
    echo Creando script con ruta completa...
    call :crear_script_con_ruta
    echo [OK] Script actualizado para usar ruta completa
    echo.
    echo Ahora puedes ejecutar: generar_certificados_ssl.bat
    pause
    exit /b 0
)

if /i "!CHOICE!"=="B" (
    echo.
    echo Abriendo configuracion del sistema...
    REM Intentar abrir la configuracion de variables de entorno
    start "" "ms-settings:about"
    echo.
    echo Sigue estos pasos:
    echo 1. Ve a: Configuracion avanzada del sistema
    echo 2. Variables de entorno
    echo 3. En "Variables del sistema", selecciona "Path" -^> Editar
    echo 4. Nuevo -^> Pega: %OPENSSL_DIR%
    echo 5. Aceptar en todas las ventanas
    echo 6. Cierra y abre una nueva terminal
    echo 7. Ejecuta: openssl version
    echo.
    pause
    exit /b 0
)

if /i "!CHOICE!"=="C" (
    echo.
    echo Ejecutando script de PowerShell...
    powershell -ExecutionPolicy Bypass -File "generar_certificados_ssl.ps1"
    exit /b 0
)

echo.
echo Saliendo sin cambios...
pause
exit /b 0

:crear_script_con_ruta
REM Crear una copia del script con la ruta completa
set "SCRIPT_ORIGINAL=generar_certificados_ssl.bat"
set "SCRIPT_TEMP=generar_certificados_ssl_temp.bat"

REM Leer el script original y reemplazar 'openssl' con la ruta completa
(
    for /f "usebackq delims=" %%a in ("%SCRIPT_ORIGINAL%") do (
        set "linea=%%a"
        setlocal EnableDelayedExpansion
        set "linea=!linea:openssl ="%OPENSSL_PATH%" !"
        set "linea=!linea:openssl.exe="%OPENSSL_PATH%"!"
        echo(!linea!
        endlocal
    )
) > "%SCRIPT_TEMP%"

REM Reemplazar el original
move /y "%SCRIPT_TEMP%" "%SCRIPT_ORIGINAL%" >nul
goto :eof

