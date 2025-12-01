# Generar Certificados SSL - Guía Rápida

## Problema: Error al ejecutar desde PowerShell

Si ejecutas `.\generar_certificados_ssl.bat` desde PowerShell y obtienes errores, usa una de estas soluciones:

## Solución 1: Ejecutar desde CMD (Recomendado)

1. Abre **CMD** (no PowerShell)
2. Navega al directorio del proyecto:
   ```cmd
   cd C:\Users\luisi\Documents\sd\evcharging-sd-2526
   ```
3. Ejecuta:
   ```cmd
   generar_certificados_ssl.bat
   ```

## Solución 2: Ejecutar desde PowerShell usando CMD

Desde PowerShell, ejecuta:
```powershell
cmd /c generar_certificados_ssl.bat
```

## Solución 3: Usar el Script de PowerShell (Más Fácil)

Desde PowerShell, ejecuta directamente:
```powershell
.\generar_certificados_ssl.ps1
```

Este script:
- ✅ No requiere OpenSSL en PATH
- ✅ Funciona nativamente en PowerShell
- ✅ Genera los certificados automáticamente

**Nota**: Después de ejecutar el script PowerShell, necesitarás extraer la clave privada:
```cmd
openssl pkcs12 -in certificados\registry.pfx -nocerts -nodes -out certificados\registry_key.pem
```
Contraseña: `evregistry123`

## Solución 4: Usar OpenSSL Directamente

Si OpenSSL está instalado (lo encontramos en `C:\Program Files\OpenSSL-Win64\bin\`):

```cmd
mkdir certificados
cd certificados

"C:\Program Files\OpenSSL-Win64\bin\openssl.exe" genrsa -out registry_key.pem 2048

"C:\Program Files\OpenSSL-Win64\bin\openssl.exe" req -new -x509 -key registry_key.pem -out registry_cert.pem -days 365 -subj "/C=ES/ST=Madrid/L=Madrid/O=EV_Registry/CN=localhost"

cd ..
```

## Recomendación

**Para PowerShell**: Usa `.\generar_certificados_ssl.ps1`

**Para CMD**: Usa `generar_certificados_ssl.bat`

