# Cómo Generar Certificados SSL en Otro Ordenador

Esta guía explica cómo generar los certificados SSL para EV_Registry en un ordenador diferente.

## Requisitos Previos

### Opción 1: OpenSSL instalado (Recomendado)

1. **Verificar si OpenSSL está instalado:**
   ```powershell
   openssl version
   ```

2. **Si NO está instalado, descargarlo:**
   - Descarga desde: https://slproweb.com/products/Win32OpenSSL.html
   - O usa Chocolatey: `choco install openssl`
   - O instala desde: https://www.openssl.org/source/

### Opción 2: PowerShell (No requiere OpenSSL)

Si no tienes OpenSSL, puedes usar PowerShell (Windows 10/11).

## Método 1: Usando OpenSSL (Más Simple)

### Paso 1: Crear el directorio de certificados

```powershell
# En el directorio del proyecto
mkdir certificados
cd certificados
```

### Paso 2: Generar la clave privada

```powershell
# Si OpenSSL está en PATH:
openssl genrsa -out registry_key.pem 2048

# O si está en ubicación específica (ajusta la ruta):
"C:\Program Files\OpenSSL-Win64\bin\openssl.exe" genrsa -out registry_key.pem 2048
```

### Paso 3: Generar el certificado autofirmado

```powershell
# Si OpenSSL está en PATH:
openssl req -new -x509 -key registry_key.pem -out registry_cert.pem -days 365 -subj "/C=ES/ST=Madrid/L=Madrid/O=EV_Registry/CN=localhost"

# O si está en ubicación específica:
"C:\Program Files\OpenSSL-Win64\bin\openssl.exe" req -new -x509 -key registry_key.pem -out registry_cert.pem -days 365 -subj "/C=ES/ST=Madrid/L=Madrid/O=EV_Registry/CN=localhost"
```

### Paso 4: Verificar que se generaron correctamente

```powershell
cd ..
Get-ChildItem certificados\registry*.pem
```

Deberías ver:
- `registry_key.pem` (aproximadamente 1700 bytes)
- `registry_cert.pem` (aproximadamente 1300 bytes)

### Paso 5: Verificar el contenido del certificado

```powershell
openssl x509 -in certificados\registry_cert.pem -text -noout | Select-String -Pattern "Subject:|Issuer:|Not After"
```

## Método 2: Usando PowerShell (Sin OpenSSL)

### Paso 1: Ejecutar el script de PowerShell

```powershell
.\generar_certificados_ssl.ps1
```

Este script:
- Genera un certificado autofirmado usando PowerShell
- Lo guarda en el almacén de certificados de Windows
- Exporta el certificado en formato PEM

### Paso 2: Extraer la clave privada (Requerido)

El script de PowerShell genera un archivo `.pfx` que contiene tanto el certificado como la clave privada. Para extraer la clave privada, necesitas OpenSSL:

```powershell
openssl pkcs12 -in certificados\registry.pfx -nocerts -nodes -out certificados\registry_key.pem
```

**Contraseña del PFX:** `evregistry123`

**Nota:** Si no tienes OpenSSL, el script de PowerShell no es suficiente. Usa el Método 1.

## Método 3: Script Batch Automático

### Paso 1: Copiar el script

Asegúrate de tener el archivo `generar_certificados_ssl.bat` en el proyecto.

### Paso 2: Ejecutar el script

```cmd
generar_certificados_ssl.bat
```

El script:
- Busca OpenSSL automáticamente
- Genera los certificados si encuentra OpenSSL
- Muestra instrucciones si no encuentra OpenSSL

## Verificación Final

### 1. Verificar que los archivos existen

```powershell
Test-Path certificados\registry_cert.pem  # Debe ser True
Test-Path certificados\registry_key.pem  # Debe ser True
```

### 2. Verificar el formato PEM

```powershell
# El certificado debe empezar con:
Get-Content certificados\registry_cert.pem -First 1
# Debe mostrar: -----BEGIN CERTIFICATE-----

# La clave privada debe empezar con:
Get-Content certificados\registry_key.pem -First 1
# Debe mostrar: -----BEGIN PRIVATE KEY----- o -----BEGIN RSA PRIVATE KEY-----
```

### 3. Verificar el tamaño de los archivos

```powershell
(Get-Item certificados\registry_cert.pem).Length  # Debe ser > 1000 bytes
(Get-Item certificados\registry_key.pem).Length   # Debe ser > 1500 bytes
```

### 4. Probar que EV_Registry puede cargarlos

```powershell
# Iniciar EV_Registry con SSL
python ev_registry\EV_Registry.py --db-host 127.0.0.1 --db-port 3306 --db-user root --db-password root --db-name evcharging --port 6000 --ssl --ssl-cert certificados\registry_cert.pem --ssl-key certificados\registry_key.pem
```

Si ves:
```
[EV_Registry] ✓ Certificados SSL cargados correctamente:
  - Certificado: certificados\registry_cert.pem (XXXX bytes)
  - Clave privada: certificados\registry_key.pem (XXXX bytes)
[EV_Registry] Iniciando servidor HTTPS en puerto 6000...
```

¡Los certificados están funcionando correctamente!

## Solución de Problemas

### Error: "OpenSSL no encontrado"

**Solución 1:** Instalar OpenSSL
- Descarga: https://slproweb.com/products/Win32OpenSSL.html
- Instala y agrega al PATH

**Solución 2:** Usar ruta completa
```powershell
"C:\Program Files\OpenSSL-Win64\bin\openssl.exe" genrsa -out certificados\registry_key.pem 2048
```

### Error: "Permission denied" o "Acceso denegado"

**Solución:** Ejecutar PowerShell como Administrador

### Error: "PEM lib" o "SSL error"

**Causa:** Los certificados están corruptos o mal formados

**Solución:**
1. Eliminar los certificados existentes:
   ```powershell
   Remove-Item certificados\registry*.pem -ErrorAction SilentlyContinue
   ```
2. Regenerar desde cero usando uno de los métodos anteriores

### Error: "Certificate verify failed"

**Causa:** El certificado es autofirmado (normal en desarrollo)

**Solución:** Esto es normal. Los certificados autofirmados mostrarán advertencias en navegadores, pero funcionarán correctamente.

## Notas Importantes

1. **Certificados autofirmados:** Estos certificados son solo para desarrollo/pruebas. Los navegadores mostrarán advertencias de seguridad.

2. **CN=localhost:** El certificado está configurado para `localhost`. Si necesitas usar una IP específica, cambia el CN:
   ```powershell
   openssl req -new -x509 -key registry_key.pem -out registry_cert.pem -days 365 -subj "/C=ES/ST=Madrid/L=Madrid/O=EV_Registry/CN=192.168.1.43"
   ```

3. **Validez:** Los certificados generados son válidos por 365 días. Después de ese tiempo, necesitarás regenerarlos.

4. **Seguridad:** Para producción, usa certificados de una CA reconocida (Let's Encrypt, etc.).

## Comandos Rápidos (Resumen)

```powershell
# Crear directorio
mkdir certificados -ErrorAction SilentlyContinue
cd certificados

# Generar clave privada
openssl genrsa -out registry_key.pem 2048

# Generar certificado
openssl req -new -x509 -key registry_key.pem -out registry_cert.pem -days 365 -subj "/C=ES/ST=Madrid/L=Madrid/O=EV_Registry/CN=localhost"

# Volver al directorio raíz
cd ..

# Verificar
Get-ChildItem certificados\registry*.pem
```

## Copiar Certificados Entre Ordenadores

Si ya tienes certificados en un ordenador y quieres usarlos en otro:

1. **Copiar los archivos:**
   ```powershell
   # En el ordenador origen
   Copy-Item certificados\registry_cert.pem -Destination \\otro_pc\ruta\certificados\
   Copy-Item certificados\registry_key.pem -Destination \\otro_pc\ruta\certificados\
   ```

2. **O usar USB/red:**
   - Copia la carpeta `certificados` completa
   - Pégala en el mismo lugar relativo en el otro ordenador

3. **Verificar permisos:**
   - Asegúrate de que los archivos no estén bloqueados
   - Verifica que tengan permisos de lectura

**⚠️ IMPORTANTE:** La clave privada es sensible. No la compartas públicamente ni la subas a repositorios públicos.

