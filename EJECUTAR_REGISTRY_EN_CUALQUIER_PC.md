# Ejecutar EV_Registry en Cualquier Ordenador

**Respuesta corta:** Sí, puedes ejecutar EV_Registry en cualquiera de los 3 ordenadores (PC_A, PC_B o PC_C), pero necesitas configurar correctamente las conexiones.

## Requisitos para EV_Registry

EV_Registry necesita:

1. **Acceso a la base de datos MySQL** (que está en PC_A)
   - Debe poder conectarse a `192.168.1.43:3306` (o la IP de PC_A)
   - Usuario: `root`
   - Password: `root`
   - Base de datos: `evcharging`

2. **Ser accesible desde los Monitores de CP** (que están en PC_B)
   - Los Monitores deben poder conectarse al Registry
   - Puerto: `6000` (por defecto)
   - Protocolo: HTTP o HTTPS

## Configuraciones por Ordenador

### Opción 1: Ejecutar en PC_A (Recomendado) ✅

**Ventajas:**
- ✅ Más simple: está cerca de la base de datos
- ✅ Menos latencia
- ✅ No requiere configuración adicional de red

**Configuración:**

```bash
# En PC_A
INICIAR_REGISTRY.bat
```

O manualmente:
```bash
py ev_registry\EV_Registry.py --db-host 127.0.0.1 --db-port 3306 --db-user root --db-password root --db-name evcharging --port 6000 --ssl --ssl-cert certificados\registry_cert.pem --ssl-key certificados\registry_key.pem
```

**Configuración en PC_B (Monitor):**
```powershell
# Establecer variable de entorno antes de ejecutar el Monitor
$env:REGISTRY_URL = "https://192.168.1.43:6000/api"
# O para HTTP:
$env:REGISTRY_URL = "http://192.168.1.43:6000/api"
```

O editar el script de inicio del Monitor para incluir:
```powershell
$env:REGISTRY_URL = "https://192.168.1.43:6000/api"
```

---

### Opción 2: Ejecutar en PC_B

**Ventajas:**
- ✅ Está cerca de los Monitores (menos latencia para registro)
- ✅ Puede funcionar aunque PC_A tenga problemas de red

**Desventajas:**
- ⚠️ Necesita conectarse a BD remota (PC_A)
- ⚠️ Necesita configurar firewall

**Configuración:**

1. **En PC_B, iniciar EV_Registry:**
```bash
# Conectar a BD remota en PC_A
py ev_registry\EV_Registry.py --db-host 192.168.1.43 --db-port 3306 --db-user root --db-password root --db-name evcharging --port 6000 --ssl --ssl-cert certificados\registry_cert.pem --ssl-key certificados\registry_key.pem
```

2. **Configurar firewall en PC_B:**
```powershell
# Permitir puerto 6000
New-NetFirewallRule -DisplayName "EV_Registry" -Direction Inbound -LocalPort 6000 -Protocol TCP -Action Allow
```

3. **En PC_B, configurar Monitor para usar Registry local:**
```powershell
# El Monitor puede usar localhost si Registry está en el mismo PC
$env:REGISTRY_URL = "https://127.0.0.1:6000/api"
```

---

### Opción 3: Ejecutar en PC_C

**Ventajas:**
- ✅ Puede servir como respaldo
- ✅ Distribuye la carga

**Desventajas:**
- ⚠️ Necesita conectarse a BD remota (PC_A)
- ⚠️ Necesita configurar firewall
- ⚠️ Los Monitores (PC_B) deben conectarse a PC_C

**Configuración:**

1. **En PC_C, iniciar EV_Registry:**
```bash
# Conectar a BD remota en PC_A
py ev_registry\EV_Registry.py --db-host 192.168.1.43 --db-port 3306 --db-user root --db-password root --db-name evcharging --port 6000 --ssl --ssl-cert certificados\registry_cert.pem --ssl-key certificados\registry_key.pem
```

2. **Configurar firewall en PC_C:**
```powershell
# Permitir puerto 6000
New-NetFirewallRule -DisplayName "EV_Registry" -Direction Inbound -LocalPort 6000 -Protocol TCP -Action Allow
```

3. **En PC_B, configurar Monitor para usar Registry en PC_C:**
```powershell
# Necesitas conocer la IP de PC_C (ejemplo: 192.168.1.44)
$env:REGISTRY_URL = "https://192.168.1.44:6000/api"
```

---

## Configuración del Monitor (PC_B) y Central (PC_A)

Tanto el **Monitor del CP** como **EV_Central** buscan EV_Registry usando la variable de entorno `REGISTRY_URL`.

### Monitor (PC_B)

El Monitor del CP busca EV_Registry usando la variable de entorno `REGISTRY_URL`.

### Método 1: Variable de entorno temporal

```powershell
# Antes de ejecutar el Monitor
$env:REGISTRY_URL = "https://192.168.1.43:6000/api"  # Si Registry está en PC_A
# O
$env:REGISTRY_URL = "https://127.0.0.1:6000/api"     # Si Registry está en el mismo PC_B
# O
$env:REGISTRY_URL = "https://192.168.1.44:6000/api"  # Si Registry está en PC_C
```

### Método 2: Editar el script de inicio

Edita `PC_B_RUN.bat` o el script que ejecuta el Monitor y agrega:

```batch
set REGISTRY_URL=https://192.168.1.43:6000/api
```

### Método 3: Variable de entorno del sistema

```powershell
# Configurar permanentemente (requiere reiniciar)
[System.Environment]::SetEnvironmentVariable("REGISTRY_URL", "https://192.168.1.43:6000/api", "Machine")
```

### Central (PC_A)

EV_Central también necesita conocer la URL del Registry para verificar credenciales. Si Registry está en otro PC, configura:

```powershell
# Antes de ejecutar Central
$env:REGISTRY_URL = "https://192.168.1.44:6000/api"  # Si Registry está en PC_C
# O
$env:REGISTRY_URL = "https://192.168.1.45:6000/api"  # Si Registry está en PC_B
```

O edita el script de inicio de Central (`RUN_CENTRAL.bat` o `PC_A_RUN.bat`) y agrega:

```batch
set REGISTRY_URL=https://192.168.1.44:6000/api
```

---

## Verificación de Conexión

### 1. Verificar que Registry puede conectarse a MySQL

En el ordenador donde ejecutas Registry, prueba:

```powershell
# Probar conexión a MySQL
python -c "import mysql.connector; conn = mysql.connector.connect(host='192.168.1.43', port=3306, user='root', password='root', database='evcharging'); print('OK'); conn.close()"
```

### 2. Verificar que Registry está accesible

Desde el ordenador donde está el Monitor (PC_B):

```powershell
# Si Registry está en PC_A (192.168.1.43)
Invoke-RestMethod -Uri "https://192.168.1.43:6000/api/health" -Method GET -SkipCertificateCheck

# Si Registry está en PC_B (localhost)
Invoke-RestMethod -Uri "https://127.0.0.1:6000/api/health" -Method GET -SkipCertificateCheck

# Si Registry está en PC_C (192.168.1.44)
Invoke-RestMethod -Uri "https://192.168.1.44:6000/api/health" -Method GET -SkipCertificateCheck
```

Deberías recibir:
```json
{
  "status": "ok",
  "message": "EV_Registry funcionando correctamente"
}
```

### 3. Verificar desde el Monitor

Cuando ejecutes el Monitor, deberías ver:

```
[CP_M] PASO 1: REGISTRO/AUTENTICACIÓN EN EV_Registry
[CP_M] ✓ Registro exitoso en EV_Registry
```

Si ves errores de conexión, verifica:
- ✅ Registry está ejecutándose
- ✅ Firewall permite el puerto 6000
- ✅ REGISTRY_URL está configurado correctamente
- ✅ La red permite la conexión entre PC_B y el PC donde está Registry

---

## Configuración de Firewall

Si ejecutas Registry en un PC diferente a donde están los Monitores, necesitas abrir el puerto:

### En el PC donde está Registry:

```powershell
# Permitir puerto 6000 (HTTPS)
New-NetFirewallRule -DisplayName "EV_Registry HTTPS" -Direction Inbound -LocalPort 6000 -Protocol TCP -Action Allow

# O si usas HTTP:
New-NetFirewallRule -DisplayName "EV_Registry HTTP" -Direction Inbound -LocalPort 6000 -Protocol TCP -Action Allow
```

### Verificar reglas de firewall:

```powershell
Get-NetFirewallRule -DisplayName "*EV_Registry*"
```

---

## Resumen de Configuraciones

| Ordenador | BD Host | Registry URL (Monitor) | Firewall |
|-----------|---------|----------------------|----------|
| **PC_A** | `127.0.0.1` | `https://192.168.1.43:6000/api` | No necesario |
| **PC_B** | `192.168.1.43` | `https://127.0.0.1:6000/api` | Abrir puerto 6000 |
| **PC_C** | `192.168.1.43` | `https://192.168.1.44:6000/api` | Abrir puerto 6000 |

---

## Recomendación

**Para desarrollo/pruebas:** Ejecuta Registry en **PC_A** (más simple)

**Para producción/distribuida:** Puedes ejecutarlo en cualquier PC, pero considera:
- Latencia de red
- Disponibilidad
- Seguridad (firewall)

---

## Script de Inicio Personalizado

Puedes crear un script personalizado para cada ordenador:

### `INICIAR_REGISTRY_PC_B.bat`:

```batch
@echo off
echo Iniciando EV_Registry en PC_B...
py ev_registry\EV_Registry.py --db-host 192.168.1.43 --db-port 3306 --db-user root --db-password root --db-name evcharging --port 6000 --ssl --ssl-cert certificados\registry_cert.pem --ssl-key certificados\registry_key.pem
pause
```

### `INICIAR_REGISTRY_PC_C.bat`:

```batch
@echo off
echo Iniciando EV_Registry en PC_C...
py ev_registry\EV_Registry.py --db-host 192.168.1.43 --db-port 3306 --db-user root --db-password root --db-name evcharging --port 6000 --ssl --ssl-cert certificados\registry_cert.pem --ssl-key certificados\registry_key.pem
pause
```

---

## Solución de Problemas

### Error: "Connection refused" desde Monitor

**Causa:** Registry no está accesible desde PC_B

**Solución:**
1. Verifica que Registry está ejecutándose
2. Verifica REGISTRY_URL en el Monitor
3. Verifica firewall en el PC donde está Registry
4. Prueba conectividad: `Test-NetConnection -ComputerName IP_REGISTRY -Port 6000`

### Error: "Can't connect to MySQL server"

**Causa:** Registry no puede conectarse a MySQL en PC_A

**Solución:**
1. Verifica que MySQL está ejecutándose en PC_A
2. Verifica que MySQL permite conexiones remotas
3. Verifica firewall en PC_A (puerto 3306)
4. Prueba conexión: `mysql -h 192.168.1.43 -u root -p`

### Error: "SSL certificate verify failed"

**Causa:** Certificado autofirmado

**Solución:** Esto es normal. El código del Monitor maneja esto automáticamente (intenta HTTPS, luego HTTP).

