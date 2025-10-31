# 📡 Aclaración: Telemetría y Estados del CP

## ⚠️ IMPORTANTE: Cuándo se Envía Telemetría

### ✅ Comportamiento Correcto

La telemetría **SOLO se envía durante sesiones de carga activa**. Esto es el comportamiento correcto del sistema.

| Estado del CP | ¿Envía Telemetría? | ¿Es Normal? |
|---------------|-------------------|-------------|
| **ACTIVADO** | ❌ NO | ✅ Sí, es correcto |
| **PRE-SUMINISTRO** | ❌ NO | ✅ Sí, es correcto |
| **SUMINISTRANDO** | ✅ SÍ (cada 1 segundo) | ✅ Sí, es correcto |
| **DESCONECTADO** | ❌ NO | ✅ Sí, es correcto |

---

## 🔍 ¿Por Qué Es Así?

### Razón Técnica
La telemetría incluye datos de consumo eléctrico:
- `kw_entregados`: Energía acumulada durante la sesión
- `tiempo_carga_s`: Duración de la sesión actual
- `estado_carga`: CARGANDO, REPOSO, etc.

Estos datos **solo tienen sentido durante una sesión activa de carga**.

### Razón de Eficiencia
- Un CP puede estar ACTIVADO durante horas esperando un Driver
- Enviar telemetría constantemente sería innecesario y consumiría recursos
- Kafka procesaría millones de mensajes vacíos sin valor

### Razón de Diseño
El estado del CP se determina por:
1. **Conexión TCP** con Central (gestionada por Monitor)
2. **Comunicación HCK** entre Monitor y Engine (cada 1 segundo)
3. **Telemetría de Kafka** SOLO durante carga (información de consumo)

---

## 🚨 Error Anterior (CORREGIDO)

### Lo que estaba mal
```
[19:24:49] [⚠️] CP CP_001 sin actividad → DESCONECTADO
```

El monitor de heartbeat marcaba CPs como DESCONECTADOS porque:
- Verificaba timestamp de última telemetría recibida
- Si pasaban 15 segundos sin telemetría → DESCONECTADO
- **Pero los CPs ACTIVADOS no envían telemetría**
- Resultado: falso positivo

### Lo que está correcto ahora
```
╭─────────────────────── 🚗 ESTADO CENTRAL DE CARGA ───────────────────────╮
│   CP ID   │       Estado       │  Energía (kWh)  │  Última telemetría  │
├───────────┼────────────────────┼─────────────────┼─────────────────────┤
│  CP_001   │     ACTIVADO       │      0.00       │   Sin telemetría    │
╰───────────────────────────────────────────────────────────────────────────╯
```

El monitor ahora verifica:
- **Socket TCP activo** = CP conectado
- **Estado reportado** por Monitor/Engine
- **Telemetría** solo como información adicional durante carga

---

## 📊 Flujo de Telemetría

### 1. CP Registrado (ACTIVADO)
```
Engine → Monitor → Central (Socket TCP)
Estado: ACTIVADO
Telemetría: ❌ No se envía
Mensaje TUI: "Sin telemetría" ← Esto es NORMAL
```

### 2. Driver Solicita Carga
```
Driver → Central → Monitor → Engine
Estado: PRE-SUMINISTRO
Telemetría: ❌ Aún no se envía
```

### 3. Vehículo Enchufado (Comando 'p')
```
Engine → Monitor → Central (Señal PLUGGED)
Monitor → Engine (Comando START)
Engine inicia hilo de telemetría
Estado: SUMINISTRANDO
Telemetría: ✅ Se envía cada 1 segundo
```

### 4. Durante Carga
```
Cada 1 segundo:
Engine → Kafka → Central
Telemetría: {'cp_id': 'CP_001', 'estado_carga': 'CARGANDO', 'kw_entregados': 2.50, ...}
Estado: SUMINISTRANDO
Mensaje TUI: Muestra energía y "1.2s" (última telemetría reciente)
```

### 5. Finalización (Comando 'f' o Auto)
```
Engine detiene hilo de telemetría
Engine → Monitor → Central (Trama FIN)
Central → Driver (Ticket vía Kafka)
Estado: ACTIVADO
Telemetría: ❌ Se deja de enviar
Mensaje TUI: "Sin telemetría" ← Esto es NORMAL otra vez
```

---

## 🎯 Qué Verificar para Confirmar que Todo Funciona

### ✅ CP Conectado y Esperando (ACTIVADO)
- **Socket TCP**: Activo en Central
- **Estado TUI**: Verde "ACTIVADO"
- **Telemetría TUI**: "Sin telemetría" ← **Esto es CORRECTO**
- **NO debe aparecer**: Mensaje de "sin actividad → DESCONECTADO"

### ✅ CP Durante Carga (SUMINISTRANDO)
- **Socket TCP**: Activo en Central
- **Estado TUI**: Cyan "SUMINISTRANDO"
- **Telemetría TUI**: Muestra segundos (ej: "1.2s") ← **Esto es CORRECTO**
- **Energía TUI**: Aumenta constantemente

### ✅ CP Tras Finalizar (ACTIVADO)
- **Socket TCP**: Sigue activo
- **Estado TUI**: Verde "ACTIVADO" (vuelve automáticamente)
- **Telemetría TUI**: "Sin telemetría" ← **Esto es CORRECTO**
- **Energía TUI**: Queda en 0.00 (se resetea para próxima sesión)

### ❌ CP Realmente Desconectado
- **Socket TCP**: Cerrado (Monitor apagado)
- **Estado TUI**: Rojo "DESCONECTADO"
- **Mensaje**: "[LIMPIEZA] CP XXX sin socket activo → DESCONECTADO"

---

## 💡 Preguntas Frecuentes

### ¿Por qué mi CP muestra "Sin telemetría"?
**R:** Porque está ACTIVADO esperando. Esto es correcto. La telemetría solo se envía durante carga.

### ¿Cómo sé que mi CP está funcionando si no envía telemetría?
**R:** Verifica:
1. Aparece en la tabla TUI de Central
2. Estado es "ACTIVADO" (verde)
3. Socket TCP está activo
4. Monitor muestra HCK OK cada segundo

### ¿Cuándo debería preocuparme?
**R:** Solo si:
- Estado es "DESCONECTADO" (rojo) pero el Monitor está ejecutándose
- Estado es "AVERÍA" (magenta)
- No aparece en la tabla TUI después de registrarse

### ¿La energía debe estar en 0.00 cuando está ACTIVADO?
**R:** Sí, es correcto. La energía se acumula solo durante sesiones activas.

---

## 🔧 Para Desarrolladores

### Modificar Intervalo de Telemetría
En `ev_cp_engine\EV_CP_E.py`, función `bucle_telemetria()`:
```python
def bucle_telemetria(cp_id: str, stop_event: threading.Event):
    while not stop_event.is_set():
        time.sleep(1)  # ← Cambiar aquí (1 segundo por defecto)
        # ... envía telemetría ...
```

### Añadir Telemetría en Estado ACTIVADO (NO recomendado)
Si realmente necesitas telemetría constante:
```python
# En main() de EV_CP_E.py, iniciar hilo de telemetría al arrancar
# ADVERTENCIA: Generará mucho tráfico innecesario en Kafka
```

### Verificar Socket TCP desde Terminal
En Windows PowerShell:
```powershell
# Ver conexión del Monitor al Central
netstat -an | findstr "5000"  # Puerto del Central

# Ver conexión del Monitor al Engine
netstat -an | findstr "7001"  # Puerto del Engine
```

---

## 📝 Resumen

| Concepto | Explicación |
|----------|-------------|
| **Socket TCP** | Determina si CP está CONECTADO o DESCONECTADO |
| **Comunicación HCK** | Verifica salud del Engine (cada 1 segundo) |
| **Telemetría Kafka** | Información de consumo SOLO durante carga |
| **"Sin telemetría"** | Es NORMAL cuando CP está ACTIVADO |
| **Estado DESCONECTADO** | Solo cuando socket TCP se cierra |

---

**Última actualización**: 31 de Octubre, 2025  
**Sistema**: EV Charging - Distributed System (SD-2526)  
**Cambio relacionado**: Corrección del monitor de heartbeat

