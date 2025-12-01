@echo off
setlocal
cd /d "%~dp0"

echo.
echo ============================================================
echo   GENERADOR DE CERTIFICADOS SSL PARA EV_Registry
echo ============================================================
echo.

REM Buscar OpenSSL
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

REM Verificar si está en PATH
openssl version >nul 2>&1
if %errorlevel% equ 0 (
    set "OPENSSL_CMD=openssl"
    goto :found
)

echo [ERROR] OpenSSL no encontrado
echo.
echo Ejecuta: .\generar_certificados_ssl.ps1
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

echo [1/3] Generando clave privada...
%OPENSSL_CMD% genrsa -out registry_key.pem 2048
if %errorlevel% neq 0 (
    echo [ERROR] Fallo al generar clave privada
    pause
    exit /b 1
)
echo [OK] Clave privada generada
echo.

echo [2/3] Generando certificado...
%OPENSSL_CMD% req -new -x509 -key registry_key.pem -out registry_cert.pem -days 365 -subj "/C=ES/ST=Madrid/L=Madrid/O=EV_Registry/CN=localhost"
if %errorlevel% neq 0 (
    echo [ERROR] Fallo al generar certificado
    pause
    exit /b 1
)
echo [OK] Certificado generado
echo.

cd ..

echo ============================================================
echo   CERTIFICADOS GENERADOS EXITOSAMENTE
echo ============================================================
echo.
echo Archivos en: certificados\
echo   - registry_cert.pem
echo   - registry_key.pem
echo.
pause

