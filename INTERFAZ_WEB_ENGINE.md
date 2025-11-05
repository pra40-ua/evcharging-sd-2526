# Interfaz Web para Control de Engines

## Descripción General

Se ha implementado una interfaz web para cada punto de carga (Engine), permitiendo la simulación y control de operaciones en tiempo real. Cada engine ahora cuenta con su propia aplicación web accesible desde el navegador.

## Características Implementadas

### 1️⃣ **Botón: Simular Avería**
Permite simular una avería en el punto de carga.

**Funcionamiento:**
- Al activar la avería, el engine responde **KO** en lugar de **OK** a los chequeos de salud (HCK) del monitor
- El monitor detecta el estado KO y notifica automáticamente a la central enviando un mensaje **AVR** (Avería)
- La central registra el estado de avería y lo muestra en su dashboard
- Se puede desactivar la avería en cualquier momento para volver al funcionamiento normal

**Flujo de comunicación:**
```
Engine (KO) → Monitor → Central (AVR) → Dashboard Web Central (Estado: AVERÍA)
```

### 2️⃣ **Botón: Simular Conexión de Driver**
Simula que un vehículo se ha enchufado físicamente al punto de carga.

**Funcionamiento:**
- Envía un mensaje **STATE: PLUGGED** al monitor
- El monitor reenvía el estado a la central
- Si hay una autorización previa pendiente (solicitud de un driver), el sistema inicia automáticamente el suministro
- La central habilita el botón "Iniciar Carga" en su dashboard web

**Flujo de comunicación:**
```
Engine (PLUGGED) → Monitor → Central → Autorización automática si hay sesión pendiente
```

### 2️⃣ **Botón: Solicitar Cierre de Suministro**
Cierra el suministro actual y genera el ticket para el driver.

**Funcionamiento:**
- Detiene la telemetría y el contador de carga
- Calcula la energía total entregada (kWh), el importe (€) y la duración
- Envía un mensaje **FIN** al monitor con todos los datos de la sesión
- El monitor reenvía el FIN a la central
- La central genera y envía el ticket final al driver a través de Kafka
- El punto de carga queda disponible para una nueva sesión

**Flujo de comunicación:**
```
Engine (FIN) → Monitor → Central → Ticket enviado al Driver vía Kafka
```

## Panel de Estado en Tiempo Real

La interfaz muestra información actualizada cada 2 segundos:

- **Estado**: DISPONIBLE, CARGANDO, PRE-SUMINISTRO, etc.
- **Monitor**: Estado de conexión con el monitor
- **Energía (kWh)**: Energía acumulada en la sesión actual
- **Tiempo (s)**: Duración de la carga en segundos
- **Driver Actual**: ID del conductor conectado
- **Objetivo (kWh)**: Energía solicitada por el driver

## Acceso a las Interfaces Web

Cada engine se levanta en un puerto web diferente, calculado automáticamente:

| Engine | Puerto Web | URL |
|--------|------------|-----|
| CP001  | 9001       | http://localhost:9001 |
| CP002  | 9002       | http://localhost:9002 |
| CP003  | 9003       | http://localhost:9003 |
| CP00N  | 9000+N     | http://localhost:9000+N |

El puerto se calcula sumando 9000 + número extraído del CP_ID.

## Cambios Técnicos Realizados

### Archivo: `ev_cp_engine/EV_CP_E.py`

#### 1. Imports nuevos
```python
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
```

#### 2. Variables globales agregadas
```python
SIMULAR_AVERIA = False
SIMULAR_AVERIA_LOCK = threading.Lock()

app = Flask(__name__)
CORS(app)
WEB_PORT = 9000
```

#### 3. Modificación del chequeo HCK
```python
if cod_op == 'HCK':
    with SIMULAR_AVERIA_LOCK:
        if SIMULAR_AVERIA:
            status = "KO"
        else:
            status = "OK"
    
    respuesta = construir_trama('HCK_RESP', [status])
    conn.sendall(respuesta)
```

#### 4. Endpoints Flask implementados

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/` | GET | Página principal de control |
| `/api/status` | GET | Estado actual del engine (JSON) |
| `/api/simular_averia` | POST | Activar/desactivar avería |
| `/api/conectar_driver` | POST | Simular conexión física |
| `/api/desconectar_driver` | POST | Simular desconexión |
| `/api/solicitar_cierre_suministro` | POST | Cerrar suministro y generar ticket |

#### 5. Argumento nuevo para el engine
```bash
--web-port PORT    # Puerto para la interfaz web (default: 9000 + número del CP)
```

### Archivo: `ev_cp_engine/templates/engine_control.html`

Template HTML completo con:
- Interfaz moderna y responsive
- Actualización automática cada 2 segundos
- Notificaciones visuales de acciones
- Panel de estado en tiempo real
- Botones claramente identificados con descripciones

## Cómo Usar

### 1. Iniciar un Engine
```bash
# Iniciar CP001 (puerto web: 9001)
python ev_cp_engine/EV_CP_E.py --port 7001 --cp-id CP001 --kafka 127.0.0.1:9092

# Iniciar CP002 con puerto web personalizado
python ev_cp_engine/EV_CP_E.py --port 7002 --cp-id CP002 --kafka 127.0.0.1:9092 --web-port 9050
```

### 2. Acceder a la Interfaz Web
Abrir en el navegador:
- Para CP001: `http://localhost:9001`
- Para CP002: `http://localhost:9002`

### 3. Simular una Avería
1. Click en "Activar Avería"
2. Introducir motivo de la avería (opcional)
3. El monitor detectará el KO y notificará a la central
4. Ver el estado en el dashboard de la central
5. Click en "Desactivar Avería" para volver a la normalidad

### 4. Simular Conexión y Carga
1. Desde la web del driver, solicitar una carga (esto crea una sesión en la central)
2. En la web del engine, click en "Simular Conexión de Driver"
3. El sistema envía PLUGGED → monitor → central
4. La central autoriza automáticamente y envía START al monitor
5. El monitor inicia la carga en el engine
6. Ver el progreso en tiempo real en todas las interfaces

### 5. Cerrar Suministro
1. Durante una carga activa, click en "Solicitar Cierre de Suministro"
2. Confirmar la acción
3. El engine calcula los datos finales y envía FIN al monitor
4. El monitor reenvía a la central
5. La central genera el ticket y lo envía al driver
6. El punto de carga queda disponible para nueva sesión

## Integración con el Sistema Existente

### Monitor (EV_CP_M.py)
Ya está preparado para:
- Detectar respuestas KO en el chequeo HCK
- Enviar mensaje AVR a la central cuando detecta KO
- Procesar mensajes STATE (PLUGGED/UNPLUGGED) del engine
- Reenviar mensajes FIN a la central con todos los campos

### Central (EV_Central.py)
Ya está preparado para:
- Recibir y procesar mensajes AVR (avería)
- Cambiar el estado del CP a "AVERÍA" en la base de datos y dashboard
- Recibir mensajes STATE desde el monitor
- Procesar mensajes FIN y generar tickets para drivers
- Notificar eventos a través de Kafka

### Web Dashboard (web_dashboard.py)
Muestra automáticamente:
- CPs con estado "AVERÍA" cuando se simula desde el engine
- Estados en tiempo real recibidos por telemetría
- Sesiones activas con driver_id asociado

## Ventajas de la Implementación

✅ **Independencia**: Cada engine tiene su propia interfaz web
✅ **Simulación realista**: Los botones replican el comportamiento físico del hardware
✅ **Trazabilidad completa**: Todos los eventos quedan registrados en logs y base de datos
✅ **Sin modificar protocolo**: Usa los mensajes existentes (HCK, STATE, FIN, AVR)
✅ **Tiempo real**: Actualización automática del estado cada 2 segundos
✅ **Facilidad de uso**: Interfaz intuitiva con descripciones claras

## Notas Técnicas

- El servidor Flask se ejecuta en un hilo separado (daemon) para no bloquear el socket del engine
- El estado de avería se controla con un lock para thread-safety
- Los templates se buscan en la carpeta `ev_cp_engine/templates/`
- El puerto web se calcula automáticamente pero puede personalizarse con `--web-port`
- La interfaz es compatible con múltiples navegadores modernos

## Dependencias

Ya incluidas en `requirements.txt`:
- Flask 3.0.0
- Flask-CORS 4.0.0

## Pruebas Recomendadas

1. **Test de Avería:**
   - Activar avería desde web del engine
   - Verificar que el monitor envía AVR a la central
   - Comprobar estado en dashboard central
   - Desactivar avería y verificar normalización

2. **Test de Conexión:**
   - Solicitar carga desde driver
   - Ver estado "PRE-SUMINISTRO" en central
   - Simular PLUGGED desde engine
   - Verificar inicio automático de carga

3. **Test de Cierre:**
   - Durante una carga, cerrar desde engine
   - Verificar recepción de ticket en driver
   - Comprobar que CP queda ACTIVADO
   - Verificar datos en base de datos

## Soporte

Para cualquier duda sobre el funcionamiento de la interfaz web:
1. Revisar los logs del engine en consola
2. Abrir la consola del navegador (F12) para ver mensajes de debug
3. Verificar que el monitor está conectado al engine
4. Comprobar la conectividad con Kafka

