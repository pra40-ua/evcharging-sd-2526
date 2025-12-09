# Orden Correcto de Ejecución con Registry en PC_B

Esta guía explica el orden correcto para ejecutar el sistema cuando **EV_Registry está en PC_B** y se conecta a la base de datos en **PC_A**.

## Orden de Ejecución

### Paso 1: En PC_A - Iniciar Base de Datos y Servicios Centrales

```bash
PC_A_RUN.bat
```

Este script:
- ✅ Inicia Kafka y MySQL (Docker)
- ✅ Inicia EV_Central
- ✅ Inicia Dashboard Web
- ✅ Genera `central_ip.txt` con la IP de PC_A

**Espera a que veas:**
```
[OK] Servicios Docker iniciados.
[OK] Kafka está listo y respondiendo.
```

### Paso 2: En PC_B - Copiar central_ip.txt

Copia el archivo `central_ip.txt` desde PC_A a PC_B.

Este archivo contiene la IP de PC_A y es necesario para que Registry se conecte a la BD.

### Paso 3: En PC_B - Generar Certificados SSL (si no existen)

```bash
generar_certificados_rapido.bat
```

O si prefieres PowerShell:
```powershell
.\generar_certificados_rapido.ps1
```

**Solo necesario la primera vez** o si los certificados no existen.

### Paso 4: En PC_B - Iniciar EV_Registry

```bash
INICIAR_REGISTRY_PC_B.bat
```

Este script:
- ✅ Detecta la IP de PC_A desde `central_ip.txt`
- ✅ Verifica que puede conectarse a MySQL en PC_A
- ✅ Inicia EV_Registry conectándose a la BD remota
- ✅ Muestra la configuración de REGISTRY_URL

**Espera a que veas:**
```
[OK] MySQL está accesible en 192.168.1.43:3306
[OK] EV_Registry iniciado con HTTPS (puerto 6000)
```

### Paso 5: En PC_B - Configurar REGISTRY_URL y Ejecutar Monitor

Antes de ejecutar el Monitor, configura la variable de entorno:

```powershell
# Si Registry usa HTTPS (recomendado)
$env:REGISTRY_URL = "https://127.0.0.1:6000/api"

# O si Registry usa HTTP
$env:REGISTRY_URL = "http://127.0.0.1:6000/api"
```

Luego ejecuta el Monitor:
```bash
PC_B_RUN.bat
```

## Verificación Rápida

### Verificar que MySQL está accesible desde PC_B

```powershell
# En PC_B, probar conexión a MySQL en PC_A
python -c "import mysql.connector; conn = mysql.connector.connect(host='192.168.1.43', port=3306, user='root', password='root', database='evcharging', connection_timeout=5); print('OK'); conn.close()"
```

### Verificar que Registry está corriendo

```powershell
# En PC_B
Invoke-RestMethod -Uri "https://127.0.0.1:6000/api/health" -Method GET -SkipCertificateCheck
```

Deberías recibir:
```json
{
  "status": "ok",
  "message": "EV_Registry funcionando correctamente"
}
```

### Verificar que el Monitor puede conectarse a Registry

Cuando ejecutes el Monitor, deberías ver:
```
[CP_M] PASO 1: REGISTRO/AUTENTICACIÓN EN EV_Registry
[CP_M] ✓ Registro exitoso en EV_Registry
```

## Configuración de Firewall

### En PC_A (MySQL)

Asegúrate de que MySQL permite conexiones remotas:

```powershell
# Abrir puerto 3306 en PC_A
New-NetFirewallRule -DisplayName "MySQL" -Direction Inbound -LocalPort 3306 -Protocol TCP -Action Allow
```

### En PC_B (Registry)

Si otros PCs necesitan acceder a Registry en PC_B:

```powershell
# Abrir puerto 6000 en PC_B
New-NetFirewallRule -DisplayName "EV_Registry" -Direction Inbound -LocalPort 6000 -Protocol TCP -Action Allow
```

## Resumen del Flujo

```
PC_A                          PC_B
─────────────────────────────────────────────────────
1. PC_A_RUN.bat
   ├─ Inicia MySQL
   ├─ Inicia Kafka
   ├─ Inicia Central
   └─ Genera central_ip.txt
                              │
                              │ (Copia central_ip.txt)
                              │
                              ▼
                              2. INICIAR_REGISTRY_PC_B.bat
                                 ├─ Lee central_ip.txt
                                 ├─ Conecta a MySQL en PC_A
                                 └─ Inicia Registry (puerto 6000)
                              │
                              ▼
                              3. Configurar REGISTRY_URL
                                 $env:REGISTRY_URL = "https://127.0.0.1:6000/api"
                              │
                              ▼
                              4. PC_B_RUN.bat
                                 └─ Monitor se conecta a Registry local
                                    y luego a Central en PC_A
```

## Solución de Problemas

### Error: "No se pudo conectar a MySQL"

**Causa:** MySQL no está accesible desde PC_B

**Solución:**
1. Verifica que `PC_A_RUN.bat` está ejecutándose
2. Verifica que MySQL está activo: `docker ps` en PC_A
3. Verifica firewall en PC_A (puerto 3306)
4. Verifica que `central_ip.txt` tiene la IP correcta de PC_A

### Error: "Connection refused" al conectar a Registry

**Causa:** Registry no está ejecutándose o REGISTRY_URL está mal configurado

**Solución:**
1. Verifica que `INICIAR_REGISTRY_PC_B.bat` se ejecutó correctamente
2. Verifica REGISTRY_URL: `echo $env:REGISTRY_URL`
3. Prueba conexión: `Invoke-RestMethod -Uri "https://127.0.0.1:6000/api/health" -SkipCertificateCheck`

### Error: "central_ip.txt no encontrado"

**Causa:** No copiaste el archivo desde PC_A

**Solución:**
1. Ejecuta `PC_A_RUN.bat` en PC_A primero
2. Copia `central_ip.txt` desde PC_A a PC_B
3. O ingresa la IP manualmente cuando el script lo solicite

## Scripts Disponibles

- `PC_A_RUN.bat` - Inicia servicios en PC_A
- `INICIAR_REGISTRY_PC_B.bat` - Inicia Registry en PC_B conectándose a PC_A
- `INICIAR_REGISTRY.bat` - Inicia Registry en PC_A (local)
- `PC_B_RUN.bat` - Inicia Monitor y otros servicios en PC_B

## Notas Importantes

1. **Orden crítico:** Siempre ejecuta `PC_A_RUN.bat` primero para iniciar MySQL
2. **central_ip.txt:** Debe estar en PC_B antes de ejecutar Registry
3. **REGISTRY_URL:** Debe configurarse antes de ejecutar el Monitor
4. **Firewall:** Asegúrate de que los puertos necesarios están abiertos

