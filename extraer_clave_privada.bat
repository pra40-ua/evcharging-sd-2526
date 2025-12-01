@echo off
echo Extrayendo clave privada del archivo PFX...
"C:\Program Files\OpenSSL-Win64\bin\openssl.exe" pkcs12 -in certificados\registry.pfx -nocerts -nodes -out certificados\registry_key.pem -passin pass:evregistry123
if %errorlevel% equ 0 (
    echo [OK] Clave privada extraida: certificados\registry_key.pem
) else (
    echo [ERROR] Fallo al extraer clave privada
    pause
)
pause

