@echo off
REM ============================================================
REM  GENERADOR RÁPIDO DE CERTIFICADOS SSL
REM  Para usar en cualquier ordenador
REM ============================================================

setlocal
cd /d "%~dp0"

echo.
echo ============================================================
echo   GENERADOR DE CERTIFICADOS SSL PARA EV_Registry
echo ============================================================
echo.

REM Buscar OpenSSL en ubicaciones comunes
set OPENSSL_CMD=
if exist "C:\Program Files\OpenSSL-Win64\bin\openssl.exe" (
    set "OPENSSL_CMD=C:\Program Files\OpenSSL-Win64\bin\openssl.exe"
    goto :found
)
if exist "C:\Program Files (x86)\OpenSSL-Win64\bin\openssl.exe" (
    set "OPENSSL_CMD=C:\Program Files (x86)\OpenSSL-Win64\bin\openssl.exe"
    goto :found
)
if exist "C:\OpenSSL-Win64\bin\openssl.exe" (
    set "OPENSSL_CMD=C:\OpenSSL-Win64\bin\openssl.exe"
    goto :found
)
if exist "C:\Program Files\OpenSSL\bin\openssl.exe" (
    set "OPENSSL_CMD=C:\Program Files\OpenSSL\bin\openssl.exe"
    goto :found
)

REM Verificar si está en PATH
openssl version >nul 2>&1
if %errorlevel% equ 0 (
    set "OPENSSL_CMD=openssl"
    goto :found
)

echo [ERROR] OpenSSL no encontrado
echo.
echo OPCIONES:
echo   1. Instalar OpenSSL desde: https://slproweb.com/products/Win32OpenSSL.html
echo   2. O usar PowerShell: .\generar_certificados_ssl.ps1
echo   3. O ejecutar manualmente con la ruta completa de OpenSSL
echo.
echo Si OpenSSL está instalado en otra ubicación, edita este script
echo y cambia la ruta en la línea que dice "set OPENSSL_CMD=..."
echo.
pause
exit /b 1

:found
echo [OK] OpenSSL encontrado: %OPENSSL_CMD%
%OPENSSL_CMD% version
echo.

REM Crear directorio
if not exist "certificados" mkdir "certificados"
cd certificados

echo [1/2] Generando clave privada RSA 2048 bits...
%OPENSSL_CMD% genrsa -out registry_key.pem 2048
if %errorlevel% neq 0 (
    echo [ERROR] Fallo al generar clave privada
    pause
    exit /b 1
)
echo [OK] Clave privada generada: registry_key.pem
echo.

echo [2/2] Generando certificado autofirmado (válido 365 días)...
%OPENSSL_CMD% req -new -x509 -key registry_key.pem -out registry_cert.pem -days 365 -subj "/C=ES/ST=Madrid/L=Madrid/O=EV_Registry/CN=localhost"
if %errorlevel% neq 0 (
    echo [ERROR] Fallo al generar certificado
    pause
    exit /b 1
)
echo [OK] Certificado generado: registry_cert.pem
echo.

cd ..

echo ============================================================
echo   CERTIFICADOS GENERADOS EXITOSAMENTE
echo ============================================================
echo.
echo Archivos generados en: certificados\
echo   - registry_cert.pem  (Certificado)
echo   - registry_key.pem    (Clave privada)
echo.
echo Para verificar:
echo   dir certificados\registry*.pem
echo.
echo Para usar en EV_Registry:
echo   INICIAR_REGISTRY.bat
echo.
pause

