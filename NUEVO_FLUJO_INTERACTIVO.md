# Nuevo Flujo Interactivo de Suministro

## 🎯 Objetivo
Hacer el proceso de inicio y fin de suministro completamente visual e interactivo, requiriendo confirmación explícita tanto del operador del Engine como del operador de Central.

## 📊 Estados del Engine

```
REPOSO 
  ↓ (Driver solicita carga)
ESPERANDO_DRIVER (Central autorizó, esperando acción del operador del Engine)
  ↓ (Operador Engine: "Iniciar Suministro")
LISTO_PARA_INICIAR (Señal enviada a Central, esperando confirmación)
  ↓ (Central confirma START)
CARGANDO (Suministro activo)
  ↓ (Operador Engine: "Solicitar Fin")
ESPERANDO_CONFIRMACION_FIN (Señal enviada a Central, esperando confirmación)
  ↓ (Central confirma STOP)
REPOSO (Fin completado, ticket enviado)
```

## 🔄 Flujo de Inicio de Suministro

### Paso 1: Driver Solicita Carga
```
Driver → Kafka → Central
```
- Central valida disponibilidad del CP
- Central envía `AUTH_REQ` al Monitor
- Monitor reenvía a Engine

### Paso 2: Engine Recibe Autorización
```
Central → AUTH_REQ → Monitor → Engine
```
**Engine:**
- Cambia estado: `REPOSO` → `ESPERANDO_DRIVER`
- Guarda `driver_id` y `kw_objetivo`
- **Web del Engine:** Aparece botón **"Iniciar Suministro"**

### Paso 3: Operador del Engine Inicia
```
Web Engine [Click: Iniciar Suministro] → Engine
```
**Engine:**
- Cambia estado: `ESPERANDO_DRIVER` → `LISTO_PARA_INICIAR`
- Envía mensaje `READY_TO_START` al Monitor
- **Web del Engine:** Botón cambia a "Esperando confirmación..."

### Paso 4: Monitor Reenvía a Central
```
Engine → READY_TO_START → Monitor → Central
```
**Monitor:**
- Recibe `READY_TO_START`
- Reenvía a Central como mensaje

### Paso 5: Central Recibe Señal
```
Monitor → Central
```
**Central:**
- Guarda que el CP está listo
- **Web de Central:** Aparece botón **"Confirmar Inicio"** para ese CP

### Paso 6: Operador de Central Confirma
```
Web Central [Click: Confirmar Inicio] → Central
```
**Central:**
- Envía comando `START` al Monitor
- **Web de Central:** Botón desaparece, muestra "Suministrando"

### Paso 7: Monitor Ejecuta START
```
Central → START → Monitor → Engine
```
**Engine:**
- Cambia estado: `LISTO_PARA_INICIAR` → `CARGANDO`
- Inicia telemetría
- Comienza contadores
- **Web del Engine:** Muestra estado "CARGANDO" y botón **"Solicitar Fin"**

## 🛑 Flujo de Fin de Suministro

### Paso 1: Operador del Engine Solicita Fin
```
Web Engine [Click: Solicitar Fin] → Engine
```
**Engine:**
- Cambia estado: `CARGANDO` → `ESPERANDO_CONFIRMACION_FIN`
- Envía mensaje `REQUEST_STOP` al Monitor
- **Web del Engine:** Botón cambia a "Esperando confirmación de fin..."

### Paso 2: Monitor Reenvía a Central
```
Engine → REQUEST_STOP → Monitor → Central
```
**Monitor:**
- Recibe `REQUEST_STOP`
- Reenvía a Central

### Paso 3: Central Recibe Solicitud
```
Monitor → Central
```
**Central:**
- Guarda que el CP solicita fin
- **Web de Central:** Aparece botón **"Confirmar Fin"** para ese CP

### Paso 4: Operador de Central Confirma Fin
```
Web Central [Click: Confirmar Fin] → Central
```
**Central:**
- Envía comando `STOP` al Monitor
- **Web de Central:** Botón desaparece

### Paso 5: Monitor Ejecuta STOP
```
Central → STOP → Monitor → Engine
```
**Engine:**
- Cambia estado: `ESPERANDO_CONFIRMACION_FIN` → `REPOSO`
- Detiene telemetría
- Calcula datos finales
- Envía `FIN` al Monitor con datos
- **Web del Engine:** Vuelve a estado "REPOSO"

### Paso 6: Ticket al Driver
```
Engine → FIN → Monitor → Central → Kafka → Driver
```
**Central:**
- Recibe `FIN` con datos
- Genera y envía ticket al driver
- Limpia sesión del CP

## 📨 Nuevos Mensajes de Protocolo

### READY_TO_START
**Dirección:** Engine → Monitor → Central  
**Formato:** `READY_TO_START#<cp_id>#<driver_id>`  
**Significado:** El Engine está listo para iniciar el suministro y espera confirmación de Central

### REQUEST_STOP
**Dirección:** Engine → Monitor → Central  
**Formato:** `REQUEST_STOP#<cp_id>#<driver_id>#<kw_actual>#<segundos>`  
**Significado:** El Engine solicita detener el suministro y espera confirmación de Central

### CONFIRM_START (Opcional - usando START existente)
**Dirección:** Central → Monitor → Engine  
**Formato:** `CMD#START#<kw_objetivo>#<driver_id>`  
**Significado:** Central confirma que se puede iniciar el suministro

### CONFIRM_STOP (Opcional - usando STOP existente)
**Dirección:** Central → Monitor → Engine  
**Formato:** `CMD#STOP`  
**Significado:** Central confirma que se puede detener el suministro

## 🎨 Cambios en Interfaces Web

### Web del Engine

**Estado ESPERANDO_DRIVER:**
```
┌──────────────────────────────────┐
│ Estado: Esperando Driver         │
│ Driver: DRIVER_001               │
│ Objetivo: 50.0 kWh               │
│                                  │
│ [🔌 Iniciar Suministro]         │
└──────────────────────────────────┘
```

**Estado LISTO_PARA_INICIAR:**
```
┌──────────────────────────────────┐
│ Estado: Listo para Iniciar       │
│ Driver: DRIVER_001               │
│                                  │
│ ⏳ Esperando confirmación de     │
│    Central...                    │
└──────────────────────────────────┘
```

**Estado CARGANDO:**
```
┌──────────────────────────────────┐
│ Estado: CARGANDO                 │
│ Energía: 25.5 / 50.0 kWh        │
│ Tiempo: 3600s                    │
│                                  │
│ [🛑 Solicitar Fin de Suministro]│
└──────────────────────────────────┘
```

**Estado ESPERANDO_CONFIRMACION_FIN:**
```
┌──────────────────────────────────┐
│ Estado: Esperando Confirmación   │
│ Energía: 48.2 kWh                │
│                                  │
│ ⏳ Esperando confirmación de     │
│    Central para detener...       │
└──────────────────────────────────┘
```

### Web de Central (Dashboard)

**Tabla de CPs con acciones interactivas:**
```
┌─────────┬────────────┬─────────┬────────────────────────┐
│ CP ID   │ Estado     │ Driver  │ Acciones               │
├─────────┼────────────┼─────────┼────────────────────────┤
│ CP_001  │ Listo      │ DRV_001 │ [✓ Confirmar Inicio]   │
│ CP_002  │ Cargando   │ DRV_002 │ -                      │
│ CP_003  │ Solicitó   │ DRV_003 │ [✓ Confirmar Fin]      │
│         │ Fin        │         │                        │
└─────────┴────────────┴─────────┴────────────────────────┘
```

## 🔧 Implementación por Componentes

### Engine (EV_CP_E.py)
- ✅ Agregar variable `ESTADO_FLUJO` con lock
- ✅ Agregar endpoint `/api/iniciar_suministro`
- ✅ Agregar endpoint `/api/solicitar_fin`
- ✅ Modificar handler de `AUTH_REQ` para cambiar a `ESPERANDO_DRIVER`
- ✅ Modificar handler de `CMD START` para cambiar a `CARGANDO`
- ✅ Modificar handler de `CMD STOP` para generar FIN
- ✅ Actualizar interfaz web con botones condicionales
- ✅ Enviar mensajes `READY_TO_START` y `REQUEST_STOP`

### Monitor (EV_CP_M.py)
- ✅ Agregar handler para `READY_TO_START` → reenviar a Central
- ✅ Agregar handler para `REQUEST_STOP` → reenviar a Central
- ✅ Mantener handlers existentes de `START` y `STOP`

### Central (EV_Central.py)
- ✅ Agregar handler para recibir `READY_TO_START`
- ✅ Agregar handler para recibir `REQUEST_STOP`
- ✅ Agregar estructura de datos para guardar CPs pendientes de confirmación
- ✅ Modificar lógica de `AUTH_REQ` para NO enviar START automático
- ✅ Agregar endpoints web para confirmar inicio/fin
- ✅ Actualizar dashboard con botones interactivos

### Web Dashboard (web_dashboard.py)
- ✅ Agregar columna "Acciones" en tabla de CPs
- ✅ Mostrar botón "Confirmar Inicio" si CP en estado `LISTO_PARA_INICIAR`
- ✅ Mostrar botón "Confirmar Fin" si CP en estado `ESPERANDO_CONFIRMACION_FIN`
- ✅ Endpoints `/api/confirmar_inicio/<cp_id>`
- ✅ Endpoints `/api/confirmar_fin/<cp_id>`

## 🚀 Ventajas del Nuevo Flujo

1. **Control Total:** Operadores tienen control explícito en cada paso crítico
2. **Visual:** Estado claro en ambas interfaces (Engine y Central)
3. **Seguridad:** Doble confirmación previene arranques/paradas accidentales
4. **Trazabilidad:** Cada acción tiene timestamp y responsable
5. **Demostración:** Perfecto para mostrar al profesor el flujo completo
6. **Real World:** Similar a sistemas reales de gestión de carga

## 📝 Notas de Implementación

- Los estados anteriores se mantienen como referencia (disponible, suministrando, etc.)
- El estado `ESTADO_FLUJO` es adicional y controla el flujo interactivo
- Los mensajes existentes (`START`, `STOP`, `FIN`) se reutilizan
- Los mensajes nuevos (`READY_TO_START`, `REQUEST_STOP`) son informativos
- La compatibilidad hacia atrás se mantiene para drivers automáticos

