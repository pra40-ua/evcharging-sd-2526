# 🔍 Diagnóstico: Web no muestra CPs conectados

## Problema
Los CPs se conectan a Central (aparecen en la terminal), pero no se muestran en el dashboard web.

## ✅ Cambios Realizados

He implementado mejoras para resolver este problema:

### 1. **Logging mejorado en Central** (`ev_central/EV_Central.py`)
- Ahora muestra claramente cuando publica telemetría inicial
- Indica si el productor Kafka está disponible
- Muestra heartbeats cada 10 segundos con estado de CPs

### 2. **Logging mejorado en Dashboard** (`web_dashboard.py`)
- Muestra cada mensaje de Kafka recibido
- Indica cuando detecta un CP nuevo
- Logs más verbosos para diagnóstico

### 3. **Endpoint de Diagnóstico** 
- Nuevo endpoint: `http://localhost:8080/api/debug`
- Muestra el estado interno del dashboard

### 4. **Script de Diagnóstico** (`diagnostico_dashboard.py`)
- Herramienta automática para verificar todo el sistema

---

## 🔬 Cómo Diagnosticar el Problema

### Opción 1: Script Automático (RECOMENDADO)

```batch
py diagnostico_dashboard.py
```

Este script verificará:
- ✓ Si el dashboard está respondiendo
- ✓ Si Kafka está accesible
- ✓ Si se está recibiendo telemetría

### Opción 2: Verificación Manual

#### Paso 1: Verificar Dashboard
Abre en tu navegador:
```
http://localhost:8080/api/debug
```

Deberías ver:
```json
{
  "status": "ok",
  "num_cps": 0,      // ← Si es 0, no se han detectado CPs
  "num_telemetria": 0,
  "config": {
    "kafka_broker": "192.168.1.43:9092",
    "db_configured": true
  }
}
```

#### Paso 2: Verificar logs de Dashboard
En la ventana del Dashboard, busca:
```
[DASHBOARD] ✓ Consumidor de telemetría conectado...
[DASHBOARD] Esperando telemetría de CPs...
```

Si ves mensajes como:
```
[DASHBOARD] ← Mensaje #1 recibido de CP: CP001
```
Significa que **SÍ** está recibiendo telemetría.

#### Paso 3: Verificar logs de Central
En la ventana de EV_Central, cuando un CP se conecta deberías ver:
```
[CENTRAL] → Publicando telemetría inicial de CP001 en topic 'telemetria_cp'...
[CENTRAL] ✓ Telemetría inicial de CP001 publicada correctamente en Kafka
```

Y cada 10 segundos:
```
[CENTRAL] 💓 Publicando heartbeat para 1 CP(s) conectados...
[CENTRAL]   → CP001: ACTIVADO
[CENTRAL] ✓ Heartbeat enviado correctamente a Kafka
```

#### Paso 4: Verificar Kafka directamente
En PowerShell/CMD:
```powershell
docker exec -it kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic telemetria_cp --from-beginning
```

Deberías ver mensajes JSON con telemetría de CPs.

---

## 🐛 Posibles Causas y Soluciones

### Causa 1: Dashboard iniciado ANTES que Central
**Síntoma**: Dashboard no carga CPs desde BD

**Solución**:
1. Cierra el Dashboard
2. Ejecuta de nuevo `PC_A_RUN.bat` 
3. El dashboard ahora carga estado inicial desde BD

### Causa 2: Kafka no está accesible desde Dashboard
**Síntoma**: Dashboard no recibe mensajes de Kafka

**Solución**:
```powershell
# Verificar que Kafka esté ejecutándose
docker ps | findstr kafka

# Verificar que el topic existe
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092
```

### Causa 3: Central no tiene Productor Kafka inicializado
**Síntoma**: En logs de Central ves: "Productor Kafka no disponible"

**Solución**:
1. Verifica que Kafka esté corriendo
2. Reinicia Central
3. Verifica en logs: `[KAFKA PRODUCER] Productor inicializado`

### Causa 4: IP incorrecta en configuración
**Síntoma**: Dashboard intenta conectar a IP diferente a la de Kafka

**Verificar**:
```
# En PC_A_RUN.bat, verifica que la IP coincida:
--kafka !CENTRAL_IP!:9092
```

**Verificar en docker-compose.yml**:
```yaml
KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://192.168.1.43:9092
```
Debe ser la misma IP.

### Causa 5: Group ID del Dashboard ya tiene offset antiguo
**Síntoma**: Dashboard solo lee mensajes nuevos desde que se conectó

**Solución**: Resetear el consumer group
```powershell
docker exec kafka kafka-consumer-groups --bootstrap-server localhost:9092 --group dashboard-telemetry-group --reset-offsets --to-earliest --topic telemetria_cp --execute
```

Luego reinicia el Dashboard.

---

## 🚀 Flujo Esperado

1. **PC_A inicia**: Kafka → MySQL → Central → Dashboard
2. **Central publica** telemetría inicial cuando CP se conecta
3. **Central publica** heartbeats cada 10 segundos
4. **Dashboard recibe** mensajes de Kafka y actualiza estado
5. **Web muestra** CPs en la interfaz

---

## 📊 Verificación Rápida (Checklist)

Marca cada item verificado:

```
□ Kafka está ejecutándose (docker ps)
□ Topic 'telemetria_cp' existe
□ Central muestra "Telemetría publicada" en logs
□ Central muestra "Heartbeat enviado" cada ~10s
□ Dashboard muestra "Consumidor conectado" en logs
□ Dashboard muestra mensajes "← recibido de CP"
□ /api/debug muestra num_cps > 0
□ Web en navegador muestra CPs
```

---

## 🆘 Si Nada Funciona

1. **Reinicia todo el sistema**:
   ```batch
   docker compose down
   # Cierra todas las ventanas de Central y Dashboard
   # Ejecuta de nuevo:
   PC_A_RUN.bat
   ```

2. **Ejecuta el script de diagnóstico**:
   ```batch
   py diagnostico_dashboard.py
   ```

3. **Verifica logs en orden**:
   - Logs de Kafka: `docker compose logs kafka`
   - Logs de Central: ventana "EV_Central-PC_A"
   - Logs de Dashboard: ventana "Dashboard-Web-PC_A"

4. **Captura pantallas de**:
   - Terminal de Central cuando CP se conecta
   - Terminal de Dashboard
   - Navegador en http://localhost:8080/api/debug

---

## 📝 Información para Reporte

Si el problema persiste, anota:

1. **¿Qué ves en la terminal de Central cuando un CP se conecta?**
   ```
   [Copia aquí los logs]
   ```

2. **¿Qué ves en la terminal del Dashboard?**
   ```
   [Copia aquí los logs]
   ```

3. **¿Qué muestra /api/debug?**
   ```
   [Copia el JSON aquí]
   ```

4. **¿Qué muestra el diagnóstico?**
   ```bash
   py diagnostico_dashboard.py
   [Copia la salida aquí]
   ```

