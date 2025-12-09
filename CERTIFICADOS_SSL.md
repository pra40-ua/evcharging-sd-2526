cg# Guía de Generación de Certificados SSL para EV_Registry

## Método 1: Usando OpenSSL (Recomendado)

### Requisitos
- OpenSSL instalado en Windows

### Instalación de OpenSSL

**Opción A: Descarga directa**
1. Ve a: https://slproweb.com/products/Win32OpenSSL.html
2. Descarga "Win64 OpenSSL" (versión ligera es suficiente)
3. Instala y agrega al PATH

**Opción B: Chocolatey**
```powershell
choco install openssl
```

**Opción C: Git Bash**
- Si tienes Git instalado, OpenSSL viene incluido en Git Bash

### Generación de Certificados

1. **Ejecuta el script automático:**
   ```batch
   generar_certificados_ssl.bat
   ```

2. **O manualmente:**
   ```batch
   mkdir certificados
   cd certificados
   
   # Generar clave privada
   openssl genrsa -out registry_key.pem 2048
   
   # Generar certificado autofirmado
   openssl req -new -x509 -key registry_key.pem -out registry_cert.pem -days 365 -subj "/C=ES/ST=Madrid/L=Madrid/O=EV_Registry/CN=localhost"
   ```

## Método 2: Usando PowerShell (Sin OpenSSL)

### Generación de Certificados

1. **Ejecuta el script PowerShell:**
   ```powershell
   .\generar_certificados_ssl.ps1
   ```

2. **Extrae la clave privada desde el PFX:**
   ```batch
   openssl pkcs12 -in certificados\registry.pfx -nocerts -nodes -out certificados\registry_key.pem
   ```
   Contraseña: `evregistry123`

## Método 3: Manual con OpenSSL (Línea de comandos)

```batch
# Crear directorio
mkdir certificados
cd certificados

# 1. Generar clave privada RSA de 2048 bits
openssl genrsa -out registry_key.pem 2048

# 2. Generar certificado autofirmado válido por 365 días
openssl req -new -x509 -key registry_key.pem -out registry_cert.pem -days 365 ^
    -subj "/C=ES/ST=Madrid/L=Madrid/O=EV_Registry/OU=IT/CN=localhost"

# 3. (Opcional) Verificar el certificado
openssl x509 -in registry_cert.pem -text -noout
```

## Uso de los Certificados

### En EV_Registry

**Con SSL habilitado:**
```batch
python ev_registry\EV_Registry.py --ssl --ssl-cert certificados\registry_cert.pem --ssl-key certificados\registry_key.pem --port 6000
```

**Sin SSL (HTTP):**
```batch
python ev_registry\EV_Registry.py --port 6000
```

### En PC_C_RUN.bat

El script `PC_C_RUN.bat` detecta automáticamente si existen certificados y usa HTTPS si están disponibles.

### En EV_CP_M

Si EV_Registry usa HTTPS, actualiza la URL en `EV_CP_M.py`:

```python
REGISTRY_URL = os.getenv('REGISTRY_URL', 'https://127.0.0.1:6000/api')
```

**Nota:** Con certificados autofirmados, Python mostrará advertencias. Para deshabilitarlas:

```python
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
```

## Verificación de Certificados

### Verificar certificado generado:
```batch
openssl x509 -in certificados\registry_cert.pem -text -noout
```

### Probar conexión HTTPS:
```batch
curl -k https://localhost:6000/api/health
```

## Certificados para Producción

Para producción, use certificados de una CA reconocida:

1. **Let's Encrypt (Gratis):**
   - https://letsencrypt.org/
   - Usa Certbot para generar certificados

2. **CA Comercial:**
   - Comprar certificado SSL de una CA reconocida
   - Obtener certificado y clave privada
   - Usar los mismos parámetros `--ssl-cert` y `--ssl-key`

## Solución de Problemas

### Error: "No se encuentra el certificado"
- Verifica que los archivos estén en `certificados\`
- Verifica las rutas en los argumentos

### Error: "Error cargando certificados SSL"
- Verifica que el certificado y la clave privada sean válidos
- Asegúrate de que la clave privada corresponda al certificado

### Advertencias del navegador
- Los certificados autofirmados generan advertencias (normal en desarrollo)
- En producción, use certificados de una CA reconocida

### Python muestra advertencias SSL
- Es normal con certificados autofirmados
- Para deshabilitar: `urllib3.disable_warnings()`



