# Guía de Instalación de OpenSSL en Windows

## Opción 1: Descarga Directa (Recomendada)

### Paso 1: Descargar OpenSSL
1. Ve a: https://slproweb.com/products/Win32OpenSSL.html
2. Descarga la versión **"Win64 OpenSSL"** (versión ligera es suficiente)
   - Para sistemas de 64 bits: `Win64 OpenSSL v3.x.x Light`
   - Para sistemas de 32 bits: `Win32 OpenSSL v3.x.x Light`
3. Ejecuta el instalador descargado

### Paso 2: Instalación
1. Ejecuta el instalador `.exe`
2. Durante la instalación:
   - **IMPORTANTE**: Marca la opción **"Copy OpenSSL DLLs to"** → Selecciona **"The OpenSSL binaries (/bin) directory"**
   - O mejor aún, marca **"Add OpenSSL to PATH"** si está disponible
3. Completa la instalación

### Paso 3: Verificar Instalación
Abre una nueva terminal (PowerShell o CMD) y ejecuta:
```batch
openssl version
```

Si muestra la versión, está instalado correctamente.

### Paso 4: Agregar al PATH (si no se agregó automáticamente)
Si `openssl version` no funciona:

1. Busca la ruta de instalación (normalmente: `C:\Program Files\OpenSSL-Win64\` o `C:\OpenSSL-Win64\`)
2. Copia la ruta completa a `bin` (ej: `C:\Program Files\OpenSSL-Win64\bin`)
3. Agrega al PATH:
   - Presiona `Win + X` → "Sistema"
   - "Configuración avanzada del sistema"
   - "Variables de entorno"
   - En "Variables del sistema", selecciona "Path" → "Editar"
   - "Nuevo" → Pega la ruta del bin
   - "Aceptar" en todas las ventanas
4. Cierra y abre una nueva terminal
5. Verifica: `openssl version`

---

## Opción 2: Chocolatey (Si tienes Chocolatey instalado)

### Instalación
Abre PowerShell como Administrador y ejecuta:
```powershell
choco install openssl
```

### Verificar
```batch
openssl version
```

---

## Opción 3: Usar Git Bash (Si tienes Git instalado)

Si ya tienes Git para Windows instalado, OpenSSL viene incluido en Git Bash.

### Uso
1. Abre Git Bash (no CMD ni PowerShell)
2. Ejecuta:
```bash
openssl version
```

**Nota**: Si usas Git Bash, los scripts `.bat` no funcionarán directamente. 
Puedes ejecutar los comandos OpenSSL manualmente desde Git Bash.

---

## Opción 4: Usar PowerShell (Sin OpenSSL)

Si no puedes instalar OpenSSL, puedes usar el script PowerShell que creé:
```powershell
.\generar_certificados_ssl.ps1
```

Este script usa comandos nativos de PowerShell y no requiere OpenSSL.

---

## Verificación Rápida

Después de instalar, abre una **nueva terminal** y ejecuta:

```batch
openssl version
```

Deberías ver algo como:
```
OpenSSL 3.x.x ...
```

---

## Solución de Problemas

### "openssl no se reconoce como comando"
- **Solución**: Agrega OpenSSL al PATH (ver Paso 4 arriba)
- O reinicia tu terminal después de agregar al PATH

### "No se encuentra el archivo DLL"
- **Solución**: Durante la instalación, asegúrate de marcar la opción para copiar DLLs
- O copia manualmente los archivos `.dll` de `bin` a `System32`

### "Error al generar certificado"
- Verifica que OpenSSL esté en el PATH: `where openssl`
- Prueba con ruta completa: `"C:\Program Files\OpenSSL-Win64\bin\openssl.exe" version`

---

## Recomendación

**Para la mayoría de usuarios**: Usa la **Opción 1 (Descarga Directa)** - es la más simple y confiable.

**Si ya tienes Git**: Usa **Opción 3 (Git Bash)** - no requiere instalación adicional.

**Si no puedes instalar nada**: Usa **Opción 4 (PowerShell)** - no requiere OpenSSL.



