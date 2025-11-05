# Cómo Usar el Nuevo Flujo Interactivo de Suministro

## 🎯 Descripción General

El nuevo sistema requiere **confirmación explícita** tanto del operador del Engine como del operador de Central para iniciar y finalizar el suministro eléctrico. Esto proporciona control total, trazabilidad y seguridad en las operaciones.

## 🚀 Instalación y Arranque

### Paso 1: Detener todo el sistema actual
```powershell
.\PC_B_STOP_ALL.bat
```

### Paso 2: Limpiar imágenes antiguas (IMPORTANTE)
```powershell
docker rmi ev_engine:local ev_monitor:local ev_central:local
```

### Paso 3: Iniciar el sistema
```powershell
# PC_A: Iniciar Central
.\PC_A_RUN.bat

# PC_B: Iniciar CPs
.\PC_B_RUN.bat
```

Selecciona:
- **Opción 3** (Clásico) para pruebas simples
- **Opción 1** (Múltiples CPs) para demo completa

### Paso 4: Verificar interfaces web

**Interfaces del Engine (automáticas):**
- CP_001: http://localhost:9001
- CP_002: http://localhost:9002
- CP_003: http://localhost:9003

**Dashboard Central:**
- http://localhost:8080 (si usas web_dashboard.py)

## 📖 Flujo Completo de Operación

### 🔋 INICIO DE CARGA

#### 1. Driver Solicita Carga
**Acción:** Driver ejecuta su aplicación
```powershell
python ev_driver/EV_Driver.py --kafka 192.168.1.43:9092 --driver-id DRIVER_456 --cp-id CP_001 --mat ABC-1234 --kw 50
```

**Resultado:**
- ✅ Solicitud enviada a Kafka
- ✅ Central recibe y valida
- ✅ Central envía AUTH_REQ al Engine

---

#### 2. Central Autoriza Driver
**¿Dónde ocurre?** Automático (Central)

**Resultado:**
- ✅ Engine recibe AUTH_REQ
- ✅ Engine cambia estado: `REPOSO` → `ESPERANDO_DRIVER`
- ✅ **Web del Engine:** Aparece botón verde **"Iniciar Suministro"** 🔌
- ✅ **Web Central:** Estado muestra "Esperando Operador Engine"

```
┌────────────────────────────────────┐
│ Web Engine (http://localhost:9001)│
├────────────────────────────────────┤
│ Estado: ESPERANDO_DRIVER           │
│ Driver: DRIVER_456                 │
│ Objetivo: 50.0 kWh                 │
│                                    │
│ [🔌 Iniciar Suministro]           │
└────────────────────────────────────┘
```

---

#### 3. Operador del Engine Inicia
**Acción:** Click en **"Iniciar Suministro"** en http://localhost:9001

**Resultado:**
- ✅ Engine envía `READY_TO_START` al Monitor
- ✅ Monitor reenvía a Central
- ✅ Engine cambia estado: `ESPERANDO_DRIVER` → `LISTO_PARA_INICIAR`
- ✅ **Web del Engine:** Spinner de "Esperando confirmación..."
- ✅ **Web Central:** Aparece botón verde pulsante **"✓ Confirmar Inicio"**

```
┌────────────────────────────────────┐
│ Web Central (http://localhost:8080)│
├────────────────────────────────────┤
│ CP_001 │ Listo Para Iniciar        │
│ Driver: DRIVER_456                 │
│ [✓ Confirmar Inicio] ← PULSANTE    │
└────────────────────────────────────┘
```

---

#### 4. Operador de Central Confirma
**Acción:** Click en **"✓ Confirmar Inicio"** en http://localhost:8080

**Resultado:**
- ✅ Central envía comando `START` al Monitor
- ✅ Monitor envía `CMD START` al Engine
- ✅ Engine cambia estado: `LISTO_PARA_INICIAR` → `CARGANDO`
- ✅ **Engine inicia telemetría y contadores**
- ✅ **Web del Engine:** Muestra "CARGANDO" y botón **"Solicitar Fin"** 🛑
- ✅ **Web Central:** Muestra "Suministrando" con energía en tiempo real

```
┌────────────────────────────────────┐
│ Web Engine (http://localhost:9001)│
├────────────────────────────────────┤
│ Estado: CARGANDO                   │
│ Energía: 12.5 / 50.0 kWh (25%)    │
│ Tiempo: 250s                       │
│ Driver: DRIVER_456                 │
│                                    │
│ [🛑 Solicitar Fin de Suministro]  │
└────────────────────────────────────┘
```

---

### 🛑 FIN DE CARGA

#### 5. Operador del Engine Solicita Fin
**Acción:** Click en **"🛑 Solicitar Fin de Suministro"** en http://localhost:9001

**Resultado:**
- ✅ Engine envía `REQUEST_STOP` al Monitor con datos actuales
- ✅ Monitor reenvía a Central
- ✅ Engine cambia estado: `CARGANDO` → `ESPERANDO_CONFIRMACION_FIN`
- ✅ **Web del Engine:** Spinner de "Esperando confirmación de fin..."
- ✅ **Web Central:** Aparece botón rojo pulsante **"✓ Confirmar Fin"**

```
┌────────────────────────────────────┐
│ Web Central (http://localhost:8080)│
├────────────────────────────────────┤
│ CP_001 │ Esperando Confirmación Fin│
│ Energía: 48.2 kWh                  │
│ [✓ Confirmar Fin] ← PULSANTE       │
└────────────────────────────────────┘
```

---

#### 6. Operador de Central Confirma Fin
**Acción:** Click en **"✓ Confirmar Fin"** en http://localhost:8080

**Resultado:**
- ✅ Central envía comando `STOP` al Monitor
- ✅ Monitor envía `CMD STOP` al Engine
- ✅ Engine detiene telemetría y contadores
- ✅ Engine calcula datos finales (kWh, €, duración)
- ✅ Engine envía `FIN` al Monitor
- ✅ Monitor reenvía `FIN` a Central
- ✅ Central genera ticket y lo envía al Driver vía Kafka
- ✅ Engine cambia estado: `ESPERANDO_CONFIRMACION_FIN` → `REPOSO`
- ✅ **Web del Engine:** Vuelve a "En Reposo"
- ✅ **Web Central:** CP disponible para nueva sesión
- ✅ **Driver recibe ticket** con detalles de la carga

```
Ticket recibido:
├─ Energía: 48.20 kWh
├─ Importe: €23.14
├─ Duración: 3612s
└─ TX ID: TX-CP_001-1699123456
```

---

## 🎨 Estados Visuales

### Web del Engine

| Estado | Color Fondo | Botones Visibles |
|--------|-------------|------------------|
| REPOSO | Gris | Ninguno (mensaje "En reposo") |
| ESPERANDO_DRIVER | Verde claro | **[🔌 Iniciar Suministro]** |
| LISTO_PARA_INICIAR | Amarillo | Spinner + "Esperando confirmación..." |
| CARGANDO | Azul claro | **[🛑 Solicitar Fin de Suministro]** |
| ESPERANDO_CONFIRMACION_FIN | Rojo claro | Spinner + "Esperando confirmación de fin..." |

### Web Central (Dashboard)

| Estado del CP | Acción Visible |
|---------------|----------------|
| Activado | ✓ Disponible |
| Esperando Operador Engine | ⏳ Esperando Engine... |
| **Listo Para Iniciar** | **[✓ Confirmar Inicio]** ← PULSANTE |
| Suministrando | ⚡ Suministrando... |
| **Esperando Confirmación Fin** | **[✓ Confirmar Fin]** ← PULSANTE |
| Desconectado | Sin Conexión |

Los botones de confirmación tienen **animación pulsante** para llamar la atención del operador.

---

## 🧪 Escenario de Prueba Completo

### Preparación (5 min)
```powershell
# Terminal 1: Central (PC_A)
.\PC_A_RUN.bat

# Terminal 2: CP (PC_B)
.\PC_B_RUN.bat
# Opción: 3 (Clásico)

# Esperar a que se abran las ventanas y navegadores
```

### Ejecución (Demo de 2-3 min)

**T+0s:** Driver solicita carga
- Ejecuta driver o usa web del driver
- Central valida y envía AUTH_REQ

**T+5s:** Operador del Engine
- Abre http://localhost:9001
- Ve botón verde "Iniciar Suministro"
- **Click** → Envía señal a Central

**T+10s:** Operador de Central
- Abre http://localhost:8080
- Ve botón verde pulsante "✓ Confirmar Inicio"
- **Click** → Inicia el suministro

**T+15s:** Carga en progreso
- Web del Engine muestra progreso en tiempo real
- Web Central muestra energía consumida
- Telemetría activa en Kafka

**T+60s:** Operador del Engine decide finalizar
- En http://localhost:9001
- **Click** en "Solicitar Fin de Suministro"
- Envía solicitud a Central

**T+65s:** Operador de Central confirma fin
- En http://localhost:8080
- Ve botón rojo pulsante "✓ Confirmar Fin"
- **Click** → Finaliza suministro

**T+70s:** Sistema completa ciclo
- Engine envía FIN con datos
- Central genera ticket
- Driver recibe ticket
- CP vuelve a estado REPOSO
- ✅ Listo para nueva sesión

---

## 🔍 Verificación de Estados

### En la Web del Engine (http://localhost:9001)

**Panel de Estado Superior:**
```
Estado:     ESPERANDO_DRIVER / LISTO_PARA_INICIAR / CARGANDO / etc.
Monitor:    Conectado ✓
Energía:    12.5 kWh
Tiempo:     250s
Driver:     DRIVER_456
Objetivo:   50.0 kWh
```

**Sección de Control (dinámica):**
- Cambia automáticamente según el estado
- Muestra botones solo cuando corresponde
- Spinners durante esperas

### En la Web Central (http://localhost:8080)

**Tabla de CPs:**
```
┌────────┬──────────────────┬─────────┬──────────┬─────────────────────┐
│ CP ID  │ Estado           │ Energía │ Driver   │ Acciones            │
├────────┼──────────────────┼─────────┼──────────┼─────────────────────┤
│ CP_001 │ Listo Para       │ 0.00    │ DRV_456  │ [✓ Confirmar Inicio]│
│        │ Iniciar          │         │          │     (pulsante)      │
└────────┴──────────────────┴─────────┴──────────┴─────────────────────┘
```

---

## 🐛 Solución de Problemas

### Problema: No aparece botón "Iniciar Suministro" en Engine

**Causa:** El Engine no recibió AUTH_REQ de Central

**Solución:**
1. Verifica que el driver se ejecutó correctamente
2. Mira los logs de Central: `logs/central.log`
3. Verifica que el CP está registrado en la BD
4. Comprueba la conexión TCP entre Monitor y Central

---

### Problema: Botón "Confirmar Inicio" no aparece en Central

**Causa:** Central no recibió READY_TO_START del Engine

**Verificación:**
1. Abre consola del Monitor (ventana PowerShell)
2. Busca: `READY_TO_START recibido del Engine`
3. Busca: `READY_TO_START reenviado a Central`

**Solución:**
- Verifica conexión Engine ↔ Monitor (puerto 5001)
- Verifica conexión Monitor ↔ Central (puerto 5000)
- Mira logs del Engine en su ventana PowerShell

---

### Problema: El suministro no inicia después de confirmar

**Causa:** El comando START no llegó del Central al Engine

**Verificación:**
1. Consola del Central: `[KAFKA CONSUMER] Comando recibido: START para CP_001`
2. Consola del Monitor: `Orden 'START' encolada para Engine`
3. Consola del Engine: `CMD START (Confirmado por Central)`

**Solución:**
- Verifica que Kafka está corriendo
- Revisa topic `central_commands`
- Comprueba que el Monitor puede enviar al Engine

---

### Problema: No se genera ticket al finalizar

**Causa:** FIN no llegó de Engine a Central

**Verificación:**
1. Consola del Engine: `FIN enviado al Monitor`
2. Consola del Monitor: `FIN recibido del Engine. Reenviando a Central`
3. Consola del Central: `Fin de carga recibido de CP_001`
4. Consola del Driver: `TICKET_FINAL recibido`

---

## 📊 Diagrama de Flujo Resumido

```
┌──────────┐
│  DRIVER  │ Solicita carga
└────┬─────┘
     │ (Kafka)
     ▼
┌──────────┐
│ CENTRAL  │ Valida y envía AUTH_REQ
└────┬─────┘
     │ (TCP)
     ▼
┌──────────┐
│ MONITOR  │ Reenvía AUTH_REQ
└────┬─────┘
     │ (TCP)
     ▼
┌──────────┐
│  ENGINE  │ Estado: ESPERANDO_DRIVER
│   WEB    │ [🔌 Iniciar Suministro] ← OPERADOR CLICK
└────┬─────┘
     │ READY_TO_START
     ▼
┌──────────┐
│ MONITOR  │ Reenvía READY_TO_START
└────┬─────┘
     │
     ▼
┌──────────┐
│ CENTRAL  │ Estado: LISTO_PARA_INICIAR
│   WEB    │ [✓ Confirmar Inicio] ← OPERADOR CLICK (pulsante)
└────┬─────┘
     │ CMD START
     ▼
┌──────────┐
│ MONITOR  │ Reenvía START
└────┬─────┘
     │
     ▼
┌──────────┐
│  ENGINE  │ Estado: CARGANDO
│          │ ⚡ Suministrando energía...
│   WEB    │ [🛑 Solicitar Fin] ← OPERADOR CLICK
└────┬─────┘
     │ REQUEST_STOP
     ▼
┌──────────┐
│ MONITOR  │ Reenvía REQUEST_STOP
└────┬─────┘
     │
     ▼
┌──────────┐
│ CENTRAL  │ Estado: ESPERANDO_CONFIRMACION_FIN
│   WEB    │ [✓ Confirmar Fin] ← OPERADOR CLICK (pulsante)
└────┬─────┘
     │ CMD STOP
     ▼
┌──────────┐
│ MONITOR  │ Reenvía STOP
└────┬─────┘
     │
     ▼
┌──────────┐
│  ENGINE  │ Genera FIN y envía
└────┬─────┘
     │ FIN
     ▼
┌──────────┐
│ CENTRAL  │ Genera Ticket → Driver
└────┬─────┘
     │ (Kafka)
     ▼
┌──────────┐
│  DRIVER  │ Recibe Ticket 🎫
└──────────┘
```

---

## 🎬 Demo para el Profesor

### Preparación (2 min antes)
1. Iniciar Central (PC_A)
2. Iniciar 2 CPs (PC_B, opción 1, 2 CPs)
3. Tener abiertas las pestañas:
   - Dashboard Central: http://localhost:8080
   - Engine CP_001: http://localhost:9001
   - Engine CP_002: http://localhost:9002
4. Proyectar o compartir pantalla mostrando las 3 webs

### Demostración (5 min)

**Parte 1: Solicitud y Autorización (1 min)**
```
1. Ejecutar driver para CP_001
2. Mostrar cómo aparece en Dashboard Central "Esperando Operador Engine"
3. Cambiar a web del Engine CP_001
4. Mostrar botón verde "Iniciar Suministro" que apareció
```

**Parte 2: Confirmación Distribuida (1 min)**
```
5. Click en "Iniciar Suministro" en Engine
6. Mostrar spinner de "Esperando confirmación"
7. Cambiar a Dashboard Central
8. Mostrar botón pulsante "✓ Confirmar Inicio"
9. Click en "Confirmar Inicio"
```

**Parte 3: Suministro Activo (1 min)**
```
10. Mostrar cómo cambia a "CARGANDO" en Engine
11. Mostrar contadores de energía aumentando en tiempo real
12. Mostrar telemetría en Dashboard Central actualizándose
13. Dejar cargando ~30 segundos
```

**Parte 4: Finalización Controlada (1 min)**
```
14. Click en "Solicitar Fin" en Engine
15. Mostrar spinner de "Esperando confirmación de fin"
16. Cambiar a Dashboard Central
17. Mostrar botón pulsante "✓ Confirmar Fin"
18. Click en "Confirmar Fin"
```

**Parte 5: Cierre y Ticket (1 min)**
```
19. Mostrar mensaje FIN en consola del Engine
20. Mostrar ticket generado en consola del Driver
21. Mostrar que CP vuelve a estado "Activado" en Dashboard
22. Explicar que está listo para nueva sesión
```

---

## ✨ Ventajas Demostradas

1. **Control Distribuido:** Dos operadores independientes confirman acciones críticas
2. **Visibilidad Total:** Estados claros en ambas interfaces (Engine y Central)
3. **Seguridad:** No hay arranques/paradas accidentales
4. **Trazabilidad:** Cada acción queda registrada con timestamp
5. **Escalabilidad:** Funciona con múltiples CPs simultáneamente
6. **Professional:** Similar a sistemas industriales reales (SCADA, DCS)

---

## 📝 Mensajes del Protocolo

### Nuevos Mensajes

**READY_TO_START** (Engine → Monitor → Central)
- Formato: `READY_TO_START#<cp_id>#<driver_id>`
- Significado: Engine listo para iniciar, esperando confirmación

**REQUEST_STOP** (Engine → Monitor → Central)
- Formato: `REQUEST_STOP#<cp_id>#<driver_id>#<kw_actual>#<segundos>`
- Significado: Engine solicita fin, esperando confirmación

### Mensajes Existentes (Reutilizados)

**AUTH_REQ** (Central → Monitor → Engine)
- Ahora: Informa al Engine pero NO inicia automáticamente
- Engine cambia a estado ESPERANDO_DRIVER

**CMD START** (Central → Monitor → Engine)
- Ahora: Solo se envía tras confirmación del operador de Central
- Engine inicia la carga

**CMD STOP** (Central → Monitor → Engine)
- Ahora: Solo se envía tras confirmación del operador de Central
- Engine detiene y envía FIN

**FIN** (Engine → Monitor → Central)
- Sin cambios: Envía datos finales de la sesión

---

## 🔧 Archivos Modificados

1. **ev_cp_engine/EV_CP_E.py**
   - Variable `ESTADO_FLUJO` para control de estados
   - Handler `AUTH_REQ` para cambiar a ESPERANDO_DRIVER
   - Handler `CMD START` para iniciar desde LISTO_PARA_INICIAR
   - Handler `CMD STOP` para finalizar desde ESPERANDO_CONFIRMACION_FIN
   - Endpoints `/api/iniciar_suministro` y `/api/solicitar_fin`
   - Interfaz web con botones condicionales

2. **ev_cp_monitor/EV_CP_M.py**
   - Handler `READY_TO_START` → reenvía a Central
   - Handler `REQUEST_STOP` → reenvía a Central
   - Removido START automático tras PLUGGED

3. **ev_central/EV_Central.py**
   - Variable `CP_PENDIENTE_CONFIRMACION` para tracking
   - Handler `READY_TO_START` → actualiza estado
   - Handler `REQUEST_STOP` → actualiza estado
   - Nuevos estados en mapa de BD

4. **web_dashboard.py**
   - Endpoint `/api/confirmar_inicio/<cp_id>`
   - Endpoint `/api/confirmar_fin/<cp_id>`

5. **templates/dashboard.html**
   - Botones condicionales según estado
   - Funciones `confirmarInicio()` y `confirmarFin()`
   - Animaciones pulsantes para botones de confirmación
   - Estilos para nuevos estados

---

## 💡 Tips para la Demostración

1. **Preparar ventanas:** Organiza las 3 webs en pantalla para verlas simultáneamente
2. **Narrar el flujo:** Explica cada paso mientras lo ejecutas
3. **Mostrar logs:** Ten una consola visible mostrando los mensajes de protocolo
4. **Usar 2 CPs:** Demuestra que funciona con múltiples CPs en paralelo
5. **Simular avería:** Muestra también el botón de avería como bonus

---

## ✅ Checklist Pre-Demo

- [ ] Central ejecutándose (PC_A)
- [ ] Al menos 1 CP ejecutándose (PC_B)
- [ ] Dashboard Central abierto (http://localhost:8080)
- [ ] Web del Engine abierto (http://localhost:9001)
- [ ] Driver listo para ejecutar
- [ ] Todas las interfaces actualizándose (indicador verde pulsante)
- [ ] Base de datos conectada y funcionando
- [ ] Kafka operativo

¡El sistema está listo para demostrar un flujo de control profesional y distribuido! 🚀

