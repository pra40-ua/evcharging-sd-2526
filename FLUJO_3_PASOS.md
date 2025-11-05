# Flujo de Suministro en 3 Pasos

## 🎯 Objetivo
Sistema de confirmación triple donde cada operador tiene control explícito sobre el inicio del suministro.

## 📊 Flujo Completo

### PASO 1: Driver Solicita → Central Registra
```
Driver → Kafka → Central
```
**Central:**
- Valida la solicitud del driver
- Registra sesión (driver_id, kw_objetivo)
- Cambia estado a `PENDIENTE_CONFIRMACION_CENTRAL`
- **NO envía AUTH_REQ todavía**
- Publica telemetría para que aparezca en dashboard

**Dashboard de Central:**
- Muestra botón **"🚀 PREPARAR SUMINISTRO"**
- Botón pulsante (animación) para llamar la atención

**Driver:**
- Recibe notificación: "EN_ESPERA_CONFIRMACION"

---

### PASO 2: Central Prepara → Engine Recibe
```
Web Central [Click: Preparar Suministro] → Kafka → Central → AUTH_REQ → Monitor → Engine
```

**Operador de Central:**
- Da click en botón "PREPARAR SUMINISTRO"

**Dashboard de Central:**
- Envía comando `PREPARE_SUPPLY` vía Kafka

**Central:**
- Recibe comando `PREPARE_SUPPLY`
- Envía `AUTH_REQ` al Monitor/Engine
- Cambia estado a `ESPERANDO_OPERADOR_ENGINE`

**Monitor:**
- Recibe `AUTH_REQ`
- Reenvía al Engine

**Engine:**
- Recibe `AUTH_REQ`
- Guarda datos de sesión (driver_id, kw_objetivo)
- Cambia estado interno a `ESPERANDO_DRIVER`
- **Web del Engine** muestra botón **"🔌 Iniciar Suministro"**

**Dashboard de Central:**
- Muestra: "⏳ Esperando confirmación de Engine..."

---

### PASO 3: Engine Confirma → Central Aprueba
```
Web Engine [Click: Iniciar Suministro] → READY_TO_START → Monitor → Central
```

**Operador del Engine:**
- Da click en botón "Iniciar Suministro"

**Engine:**
- Cambia estado a `LISTO_PARA_INICIAR`
- Envía mensaje `READY_TO_START` al Monitor

**Monitor:**
- Recibe `READY_TO_START`
- Reenvía a Central

**Central:**
- Recibe `READY_TO_START`
- Cambia estado a `LISTO_PARA_INICIAR`
- Notifica al driver: "AUTORIZADO" (ahora sí)

**Dashboard de Central:**
- Muestra botón **"✓ CONFIRMAR INICIO"** (pulsante, verde)

---

### PASO 4: Central Confirma → Suministro Comienza
```
Web Central [Click: Confirmar Inicio] → Kafka → Central → START → Monitor → Engine
```

**Operador de Central:**
- Da click en botón "CONFIRMAR INICIO"

**Dashboard de Central:**
- Envía comando `START` vía Kafka

**Central:**
- Recibe comando `START`
- Envía `CMD START` al Monitor/Engine

**Monitor:**
- Recibe `CMD START`
- Reenvía al Engine

**Engine:**
- Recibe `CMD START`
- Cambia estado a `CARGANDO`
- Inicia contadores y telemetría
- **Comienza el suministro real**

---

## 🎭 Estados del Sistema

### En Central (Dashboard)
1. `PENDIENTE_CONFIRMACION_CENTRAL` → Botón "🚀 PREPARAR SUMINISTRO"
2. `ESPERANDO_OPERADOR_ENGINE` → Texto "⏳ Esperando confirmación de Engine..."
3. `LISTO_PARA_INICIAR` → Botón "✓ CONFIRMAR INICIO"
4. `CARGANDO` → Texto "⚡ Suministrando..."

### En Engine (Web Local)
1. `REPOSO` → Sin driver asignado
2. `ESPERANDO_DRIVER` → Botón "🔌 Iniciar Suministro"
3. `LISTO_PARA_INICIAR` → Texto "⏳ Esperando confirmación de Central..."
4. `CARGANDO` → Botón "🛑 Solicitar Fin de Suministro"

---

## 🔄 Fin de Suministro

Similar al inicio, con confirmación desde Engine:

1. **Operador Engine** da click en "Solicitar Fin"
2. Engine envía `REQUEST_STOP` → Monitor → Central
3. Central muestra botón "✓ CONFIRMAR FIN"
4. **Operador Central** da click en "CONFIRMAR FIN"
5. Central envía `CMD STOP` → Monitor → Engine
6. Engine detiene suministro y envía `FIN` con datos
7. Central genera ticket y lo envía al driver

---

## 📝 Resumen de Confirmaciones

| Paso | Actor | Acción | Resultado |
|------|-------|--------|-----------|
| 1 | Driver | Solicita carga | Central registra sesión |
| 2 | **Operador Central** | Click "Preparar" | AUTH_REQ → Engine |
| 3 | **Operador Engine** | Click "Iniciar" | READY_TO_START → Central |
| 4 | **Operador Central** | Click "Confirmar" | START → Engine (SUMINISTRO) |

**Engine tiene la última palabra**: El suministro NO puede iniciar sin que el operador del Engine confirme explícitamente en el PASO 3.

---

## 🔧 Archivos Modificados

### 1. `ev_central/EV_Central.py`
- No envía AUTH_REQ automáticamente al recibir solicitud
- Estado nuevo: `PENDIENTE_CONFIRMACION_CENTRAL`
- Handler para comando `PREPARE_SUPPLY`
- Notifica "AUTORIZADO" solo tras recibir READY_TO_START

### 2. `web_dashboard.py`
- Endpoint `/api/preparar_suministro/<cp_id>`
- Función JavaScript `prepararSuministro()`
- Botón "PREPARAR SUMINISTRO" en estado PENDIENTE_CONFIRMACION_CENTRAL
- Estilos CSS para nuevo estado

### 3. `ev_cp_monitor/EV_CP_M.py`
- Sin cambios (ya reenviaba AUTH_REQ)

### 4. `ev_cp_engine/EV_CP_E.py`
- Sin cambios adicionales (ya maneja AUTH_REQ y READY_TO_START)

---

## ✅ Ventajas del Flujo

1. **Control Total**: 3 confirmaciones explícitas
2. **Engine tiene última palabra**: Suministro solo si Engine confirma
3. **Visibilidad**: Cada operador ve estado en tiempo real
4. **Seguridad**: Triple confirmación previene arranques accidentales
5. **Demostración**: Flujo claro para mostrar al profesor
6. **Trazabilidad**: Cada paso registrado en logs

---

## 🚨 Importante

- El driver recibe "AUTORIZADO" solo DESPUÉS del PASO 3 (Engine confirmó)
- Central puede "preparar" múltiples solicitudes, pero Engine decide cuándo empezar
- Si Engine está ocupado/averiado, no mostrará el botón de inicio

