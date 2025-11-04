# Cambios Realizados - Sistema de Múltiples Charging Points

## 📅 Fecha
4 de Noviembre de 2025

## 🎯 Objetivo
Permitir lanzar hasta 5 Charging Points (CPs) simultáneamente en PC_B, cada uno con su propia terminal interactiva que muestre:
- Estado actual del CP
- Comunicaciones OCPP-like
- Menú interactivo para simular acciones del conductor

---

## ✅ Archivos Creados

### 1. `PC_B_RUN_MULTIPLE_CPS.bat`
**Descripción**: Script principal para lanzar múltiples CPs
**Características**:
- Pregunta cuántos CPs lanzar (1-5)
- Detecta automáticamente la IP de la Central desde `central_ip.txt`
- Construye las imágenes Docker necesarias
- Lanza cada CP en su propia terminal de PowerShell
- Asigna puertos únicos a cada CP (5001, 5002, 5003, ...)
- Asigna IDs únicos a cada CP (CP_001, CP_002, ...)

### 2. `launch_single_cp.ps1`
**Descripción**: Script de PowerShell para lanzar un CP individual
**Parámetros**:
- `-CpId`: ID del CP (ej: CP_001)
- `-EnginePort`: Puerto del Engine (ej: 5001)
- `-CentralIp`: IP de la Central
- `-CentralPort`: Puerto de la Central (default: 5000)

### 3. `INSTRUCCIONES_MULTIPLES_CPS.md`
**Descripción**: Documentación completa del sistema
**Contenido**:
- Guía de uso paso a paso
- Descripción de la interfaz
- Comandos disponibles
- Ejemplos de mensajes OCPP-like
- Solución de problemas
- Configuración técnica

---

## 🔧 Archivos Modificados

### 1. `ev_cp_engine/EV_CP_E.py`
**Cambios principales**:

#### a) Nueva función `obtener_estado_actual()`
```python
def obtener_estado_actual() -> str:
    """Retorna el estado actual del CP como string legible."""
```
Devuelve el estado actual en formato legible:
- "DESCONECTADO (Sin Monitor)"
- "CARGANDO (X.XX kWh, XXs)"
- "PRE-SUMINISTRO (Autorizado, esperando enchufar)"
- "DISPONIBLE (Available)"

#### b) Nueva función `mostrar_interfaz_cp()`
```python
def mostrar_interfaz_cp(cp_id: str):
    """Muestra el banner y estado del CP."""
```
Muestra un banner visual con:
- ID del CP
- Estado actual
- Menú de opciones disponibles

#### c) Menú interactivo mejorado `menu_interactivo_engine()`
**Comandos nuevos/mejorados**:
- `[p]` Enchufar vehículo - Con emojis y mensajes claros
- `[d]` Desenchufar vehículo - Detiene la carga y envía señal
- `[r]` Simular RFID - Información sobre autenticación
- `[s]` Mostrar estado - Estado detallado del CP
- `[h]` Ayuda - Muestra el menú completo
- `[q]` Salir - Sale del menú de forma limpia

#### d) Mensajes de comunicación mejorados
**En `handle_monitor_connection()`**:

Cuando se recibe START:
```
======================================================================
  [CP_001] 📩 MENSAJE RECIBIDO: CMD START
  Driver: DRIVER_123
  Objetivo: 10.0 kWh
======================================================================

[CP_001] ⚡ CARGA INICIADA - Estado: CARGANDO

======================================================================
  [CP_001] 📤 MENSAJE ENVIADO: ACK START_OK 10.0kWh
======================================================================
```

Cuando se recibe STOP:
```
======================================================================
  [CP_001] 📩 MENSAJE RECIBIDO: CMD STOP
======================================================================

[CP_001] 🛑 CARGA DETENIDA - Estado: REPOSO

======================================================================
  [CP_001] 📤 MENSAJE ENVIADO: FIN
  Energía entregada: 8.5 kWh
  Importe: €4.08
  Duración: 170s
  Transacción: TX-CP_001-1730759243
======================================================================
```

Cuando se conecta el Monitor:
```
======================================================================
  [CP_001] 🔗 MONITOR CONECTADO desde 192.168.1.43:12345
======================================================================
```

### 2. `PC_B_RUN.bat`
**Cambios principales**:
- Añadido menú de selección de modo:
  - [1] NUEVO: Múltiples CPs
  - [2] CLÁSICO: 1 CP + 1 Driver
- Redirección automática a `PC_B_RUN_MULTIPLE_CPS.bat` si se elige modo múltiple
- Mantiene la funcionalidad original para el modo clásico

---

## 📊 Arquitectura del Sistema

### Antes (1 CP):
```
PC_B_RUN.bat
    ├─> Engine (CP_001, puerto 5001)
    ├─> Monitor (CP_001)
    └─> Driver (DRIVER_456)
```

### Ahora (Hasta 5 CPs):
```
PC_B_RUN.bat
    ├─> [1] Modo Múltiples CPs
    │       └─> PC_B_RUN_MULTIPLE_CPS.bat
    │               ├─> Terminal 1: Engine CP_001 (puerto 5001)
    │               ├─> Terminal 2: Monitor CP_001
    │               ├─> Terminal 3: Engine CP_002 (puerto 5002)
    │               ├─> Terminal 4: Monitor CP_002
    │               ├─> Terminal 5: Engine CP_003 (puerto 5003)
    │               ├─> Terminal 6: Monitor CP_003
    │               └─> ... (hasta 5 CPs)
    │
    └─> [2] Modo Clásico
            ├─> Engine (CP_001, puerto 5001)
            ├─> Monitor (CP_001)
            └─> Driver (DRIVER_456)
```

---

## 🎨 Mejoras en la Experiencia de Usuario

### 1. Visibilidad del Estado
- **Antes**: Solo logs técnicos sin estructura
- **Ahora**: Banner visual con estado claro y actualizado

### 2. Comunicaciones OCPP-like
- **Antes**: Mensajes mezclados con otros logs
- **Ahora**: Mensajes destacados con emojis y formato claro:
  - 📩 Mensaje recibido
  - 📤 Mensaje enviado
  - ⚡ Carga iniciada
  - 🛑 Carga detenida
  - 🔗 Conexión establecida

### 3. Interacción del Conductor
- **Antes**: Menú básico con letras (p/x/h)
- **Ahora**: Menú completo con:
  - Descripción clara de cada acción
  - Feedback visual de las acciones
  - Estado actualizado en tiempo real
  - Manejo de errores con mensajes claros

---

## 🔄 Compatibilidad

### Hacia Atrás
✅ El sistema mantiene compatibilidad completa con el modo clásico
✅ Los scripts antiguos siguen funcionando
✅ No se modificó la lógica de negocio del Engine o Monitor

### Docker
✅ Usa las mismas imágenes Docker
✅ Compatible con Docker Desktop en Windows
✅ Usa `host.docker.internal` para la comunicación entre contenedores

### Central (PC_A)
✅ No requiere cambios en la Central
✅ La Central puede gestionar múltiples CPs sin modificaciones

---

## 🧪 Testing

### Casos de Prueba Recomendados

#### 1. Lanzamiento de 1 CP
```batch
PC_B_RUN.bat
> Seleccionar opción [1]
> Ingresar número: 1
```
**Resultado esperado**: 1 CP lanzado correctamente con 2 terminales

#### 2. Lanzamiento de 5 CPs
```batch
PC_B_RUN.bat
> Seleccionar opción [1]
> Ingresar número: 5
```
**Resultado esperado**: 5 CPs lanzados con 10 terminales (5 Engine + 5 Monitor)

#### 3. Interacción con el Engine
En la terminal del Engine:
1. Presionar `s` para ver el estado
2. Presionar `p` para enchufar
3. Desde la web, autorizar la carga
4. Verificar que se inicia la carga
5. Presionar `s` para ver el progreso
6. Presionar `d` para desenchufar

#### 4. Modo Clásico
```batch
PC_B_RUN.bat
> Seleccionar opción [2]
```
**Resultado esperado**: Funciona igual que antes (1 CP + 1 Driver)

---

## 📝 Notas de Implementación

### Puertos Utilizados
- **Base**: 5000
- **CP_001**: 5001
- **CP_002**: 5002
- **CP_003**: 5003
- **CP_004**: 5004
- **CP_005**: 5005

### IDs de CPs
Formato: `CP_00X` donde X es el número del CP (1-5)

### Contenedores Docker
Nombres de contenedores:
- Engine: `engine_CP_001`, `engine_CP_002`, ...
- Monitor: `monitor_CP_001`, `monitor_CP_002`, ...

### Variables de Entorno
Cada CP recibe:
```
ENGINE_PORT=500X
CP_ID=CP_00X
KAFKA_SERVER=192.168.1.43:9092
CENTRAL_IP=192.168.1.43
CENTRAL_PORT=5000
ENGINE_IP=host.docker.internal
```

---

## 🚀 Próximos Pasos Sugeridos

1. **Telemetría mejorada**: Mostrar métricas en tiempo real en el Engine
2. **Dashboard local**: Crear un dashboard web local que muestre todos los CPs
3. **Simulación de fallos**: Añadir comando para simular averías
4. **Logs persistentes**: Guardar logs de cada sesión de carga
5. **Modo de depuración**: Opción para ver todos los mensajes HCK

---

## 📞 Soporte

Para más información, consulta:
- `INSTRUCCIONES_MULTIPLES_CPS.md` - Guía de uso completa
- `DIAGNOSTICO_WEB_NO_MUESTRA_CPS.md` - Solución de problemas de conectividad
- `CAMBIOS_REALIZADOS.md` - Historial de cambios del proyecto

---

## ✨ Resumen de Beneficios

1. **Escalabilidad**: Prueba con hasta 5 CPs simultáneos
2. **Visibilidad**: Ver claramente el estado y las comunicaciones
3. **Interactividad**: Simular acciones del conductor fácilmente
4. **Práctica**: Ideal para entender el protocolo OCPP-like
5. **Flexibilidad**: Modo múltiple o clásico según necesidad

