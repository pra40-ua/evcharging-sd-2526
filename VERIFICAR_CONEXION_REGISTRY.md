# Cómo Verificar que un CP se Conectó usando Credenciales del Registry

Este documento explica cómo verificar que un Charging Point (CP) se ha conectado correctamente a Central usando las credenciales del EV_Registry.

## ⚠️ IMPORTANTE: Iniciar EV_Registry Primero

**ANTES de ejecutar el Monitor del CP, debes iniciar EV_Registry.**

### Opción 1: Usar el script (Recomendado)

```bash
# En Windows:
INICIAR_REGISTRY.bat

# O en PowerShell:
.\INICIAR_REGISTRY.ps1
```

### Opción 2: Iniciar manualmente

```bash
py ev_registry\EV_Registry.py --db-host 127.0.0.1 --db-port 3306 --db-user root --db-password root --db-name evcharging --port 6000
```

**Espera unos segundos** hasta que veas el mensaje:
```
[EV_Registry] Iniciando servidor en puerto 6000...
```

Luego puedes ejecutar el Monitor del CP.

## Proceso de Autenticación

El proceso de autenticación sigue estos pasos:

1. **Monitor se registra/autentica en EV_Registry**
   - El Monitor primero se registra o autentica en el servicio EV_Registry
   - Obtiene credenciales (username y password) del Registry

2. **Monitor envía REG a Central con credenciales**
   - El Monitor envía el mensaje `REG#cp_id#ubicacion#precio#username#password` a Central
   - Las credenciales del Registry se incluyen en el mensaje

3. **Central verifica con EV_Registry**
   - Central recibe las credenciales
   - Central consulta EV_Registry para verificar que las credenciales son válidas
   - Si son válidas, acepta la conexión y envía la clave de cifrado

## Cómo Verificar la Conexión

### 1. En la Terminal del Monitor (CP)

Cuando el Monitor se conecta, deberías ver mensajes como estos:

```
======================================================================
  [CP_M] PASO 1: REGISTRO/AUTENTICACIÓN EN EV_Registry
======================================================================
[CP_M] ✓ Registro exitoso en EV_Registry
[CP_M]   Username: CP_xxxxxxxxxxxxx
[CP_M]   Password: xxxxxxxxxx... (mostrando primeros 10 caracteres)
======================================================================

======================================================================
  [CP_M] PASO 2: ENVIANDO REG A CENTRAL CON CREDENCIALES
======================================================================
[CP_M] ✓ Enviando REG con credenciales del Registry:
[CP_M]   CP_ID: CP001
[CP_M]   Username: CP_xxxxxxxxxxxxx
[CP_M]   Password: xxxxxxxxxx... (enviado completo)
======================================================================

======================================================================
  [CP_M] ✓ REGISTRO Y AUTENTICACIÓN EXITOSOS
======================================================================
[CP_M] ✓ Credenciales del Registry verificadas correctamente por Central
[CP_M]   Username: CP_xxxxxxxxxxxxx
[CP_M]   Central validó las credenciales con EV_Registry
[CP_M]   CP ID: CP001
[CP_M]   Estado: ACTIVADO
======================================================================
```

### 2. En la Terminal de Central

Cuando Central recibe la conexión, deberías ver:

```
[CENTRAL] ╔═══════════════════════════════════════════╗
[CENTRAL] ║  ✅ NUEVO CHARGING POINT REGISTRADO      ║
[CENTRAL] ╚═══════════════════════════════════════════╝
[CENTRAL]    CP ID: CP001
[CENTRAL]    Ubicación: Madrid,ES
[CENTRAL]    Precio: 0.48 €/kWh
[CENTRAL]    Estado: ACTIVADO
[CENTRAL] ═══════════════════════════════════════════

[CENTRAL] ╔═══════════════════════════════════════════╗
[CENTRAL] ║  🔐 VERIFICANDO CREDENCIALES CON REGISTRY  ║
[CENTRAL] ╚═══════════════════════════════════════════╝
[CENTRAL]    CP ID: CP001
[CENTRAL]    Username: CP_xxxxxxxxxxxxx
[CENTRAL]    Verificando con EV_Registry...
[CENTRAL] ✓ CREDENCIALES VÁLIDAS
[CENTRAL]    EV_Registry confirmó que las credenciales son correctas
[CENTRAL]    Autenticación exitosa mediante Registry
[CENTRAL] ═══════════════════════════════════════════

[CENTRAL] ✓ Credenciales verificadas correctamente con EV_Registry para CP001
```

### 3. En la Base de Datos (Tabla de Auditoría)

Puedes consultar la tabla de auditoría para ver el registro de autenticación:

```sql
SELECT * FROM auditoria 
WHERE cp_id = 'CP001' 
  AND accion IN ('VERIFICACION_CREDENCIALES', 'AUTENTICACION')
ORDER BY timestamp DESC 
LIMIT 5;
```

Deberías ver registros con:
- `accion`: `VERIFICACION_CREDENCIALES`
- `resultado`: `OK`
- `descripcion`: Contiene "Credenciales verificadas correctamente con EV_Registry"

### 4. Verificar en EV_Registry

Puedes consultar directamente el servicio EV_Registry para ver los CPs registrados:

```bash
# Listar todos los CPs registrados
curl http://127.0.0.1:6000/api/cps

# O desde PowerShell:
Invoke-RestMethod -Uri http://127.0.0.1:6000/api/cps -Method GET
```

Deberías ver tu CP en la lista con su `username` y estado `activo: true`.

## Indicadores de Éxito

✅ **Conexión exitosa con Registry:**
- Mensajes en Monitor: "✓ Registro exitoso en EV_Registry"
- Mensajes en Monitor: "✓ Enviando REG con credenciales del Registry"
- Mensajes en Central: "🔐 VERIFICANDO CREDENCIALES CON REGISTRY"
- Mensajes en Central: "✓ CREDENCIALES VÁLIDAS"
- Mensajes en Central: "EV_Registry confirmó que las credenciales son correctas"

❌ **Si hay problemas:**
- Si no hay credenciales: "⚠️ Enviando REG sin credenciales (modo compatibilidad)"
- Si las credenciales son inválidas: "❌ CREDENCIALES INVÁLIDAS" en Central
- Si el Registry no está disponible: El Monitor intentará continuar sin credenciales

## Para Mostrar al Profesor

Para demostrar que el CP se conectó usando las credenciales del Registry, muestra:

1. **Terminal del Monitor**: Muestra los mensajes del "PASO 1" y "PASO 2" que indican el registro en Registry y el envío de credenciales.

2. **Terminal de Central**: Muestra el bloque "🔐 VERIFICANDO CREDENCIALES CON REGISTRY" y el mensaje "✓ CREDENCIALES VÁLIDAS".

3. **Base de Datos**: Consulta la tabla de auditoría para mostrar el registro de verificación de credenciales.

4. **EV_Registry**: Muestra la lista de CPs registrados con sus credenciales.

## Notas Importantes

- Las credenciales se muestran parcialmente en los logs por seguridad (solo primeros 10 caracteres del password).
- Si el Registry no está disponible, el sistema puede funcionar en modo compatibilidad, pero sin verificación de credenciales.
- Las credenciales se almacenan en memoria en el Monitor y se reutilizan en reconexiones.
- Si las credenciales fallan, el Monitor intentará registrarse nuevamente en el Registry.

