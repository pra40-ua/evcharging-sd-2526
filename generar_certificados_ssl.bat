@echo off
REM ============================================================
REM  GENERADOR DE CERTIFICADOS SSL PARA EV_Registry
REM ============================================================
REM
REM  Este script genera certificados SSL autofirmados para
REM  usar HTTPS en EV_Registry (desarrollo/pruebas).
REM
REM  Para producción, use certificados de una CA reconocida.
REM ============================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0" 2>nul || cd

echo.
echo ============================================================
echo   GENERADOR DE CERTIFICADOS SSL PARA EV_Registry
echo ============================================================
echo.

REM Verificar que OpenSSL está disponible
set "OPENSSL_CMD=openssl"
openssl version >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] OpenSSL no encontrado en PATH. Buscando en ubicaciones comunes...
    
    REM Buscar en ubicaciones comunes
    set "FOUND=0"
    if exist "C:\Program Files\OpenSSL-Win64\bin\openssl.exe" (
        set "OPENSSL_CMD=C:\Program Files\OpenSSL-Win64\bin\openssl.exe"
        set "FOUND=1"
    ) else if exist "C:\Program Files (x86)\OpenSSL-Win64\bin\openssl.exe" (
        set "OPENSSL_CMD=C:\Program Files (x86)\OpenSSL-Win64\bin\openssl.exe"
        set "FOUND=1"
    ) else if exist "C:\OpenSSL-Win64\bin\openssl.exe" (
        set "OPENSSL_CMD=C:\OpenSSL-Win64\bin\openssl.exe"
        set "FOUND=1"
    ) else if exist "C:\Program Files\OpenSSL\bin\openssl.exe" (
        set "OPENSSL_CMD=C:\Program Files\OpenSSL\bin\openssl.exe"
        set "FOUND=1"
    ) else if exist "C:\OpenSSL\bin\openssl.exe" (
        set "OPENSSL_CMD=C:\OpenSSL\bin\openssl.exe"
        set "FOUND=1"
    )
    
    if !FOUND! equ 0 (
        echo [ERROR] OpenSSL no encontrado
        echo.
        echo ============================================================
        echo   OPCIONES
        echo ============================================================
        echo.
        echo 1. Ejecuta diagnosticar_openssl.bat para encontrar OpenSSL
        echo.
        echo 2. O usa PowerShell (No requiere OpenSSL en PATH):
        echo    .\generar_certificados_ssl.ps1
        echo.
        echo 3. O agrega OpenSSL al PATH manualmente
        echo.
        echo ============================================================
        echo.
        pause
        exit /b 1
    ) else (
        echo [OK] OpenSSL encontrado en: !OPENSSL_CMD!
    )
) else (
    echo [OK] OpenSSL encontrado en PATH
)

REM Verificar que funciona
"%OPENSSL_CMD%" version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] OpenSSL encontrado pero no funciona
    pause
    exit /b 1
)

echo [OK] OpenSSL funcionando correctamente
"%OPENSSL_CMD%" version
echo.

REM Crear directorio para certificados
if not exist "certificados" mkdir "certificados"
cd certificados

echo Generando certificado SSL autofirmado...
echo.

REM Generar clave privada (RSA 2048 bits)
echo [1/3] Generando clave privada...
"%OPENSSL_CMD%" genrsa -out registry_key.pem 2048
if %errorlevel% neq 0 (
    echo [ERROR] Fallo al generar clave privada
    pause
    exit /b 1
)
echo [OK] Clave privada generada: registry_key.pem
echo.

REM Generar solicitud de certificado (CSR)
echo [2/3] Generando solicitud de certificado...
"%OPENSSL_CMD%" req -new -key registry_key.pem -out registry_csr.pem -subj "/C=ES/ST=Madrid/L=Madrid/O=EV_Registry/OU=IT/CN=localhost"
if %errorlevel% neq 0 (
    echo [ERROR] Fallo al generar solicitud de certificado
    pause
    exit /b 1
)
echo [OK] Solicitud de certificado generada: registry_csr.pem
echo.

REM Generar certificado autofirmado (válido por 365 días)
echo [3/3] Generando certificado autofirmado...
"%OPENSSL_CMD%" x509 -req -days 365 -in registry_csr.pem -signkey registry_key.pem -out registry_cert.pem
if %errorlevel% neq 0 (
    echo [ERROR] Fallo al generar certificado
    pause
    exit /b 1
)
echo [OK] Certificado generado: registry_cert.pem
echo.

REM Limpiar archivo CSR (ya no es necesario)
del registry_csr.pem >nul 2>&1

cd ..

echo ============================================================
echo   CERTIFICADOS SSL GENERADOS EXITOSAMENTE
echo ============================================================
echo.
echo Archivos generados en: certificados\
echo   - registry_cert.pem  (Certificado)
echo   - registry_key.pem   (Clave privada)
echo.
echo IMPORTANTE:
echo   - Estos son certificados autofirmados (solo para desarrollo)
echo   - Los navegadores mostraran advertencias de seguridad
echo   - Para produccion, use certificados de una CA reconocida
echo.
echo Para usar los certificados en EV_Registry:
echo   1. Modifica ev_registry\EV_Registry.py para cargar los certificados
echo   2. O usa el flag --ssl-cert y --ssl-key en el futuro
echo.
pause

