# 🚗⚡ Guía de Uso Masivo - Sistema EV Charging

## Descripción

Esta guía explica cómo lanzar y probar el sistema con **múltiples instancias** de Puntos de Recarga (CPs) y Drivers simultáneamente, verificando la capacidad de escalabilidad del sistema.

---

## 📋 Requisitos Previos

### 1. Dependencias de Python

```bash
pip install -r requirements.txt
```

Asegúrate de que estén instaladas:
- `kafka-python` (Cliente Kafka)
- `mysql-connector-python` (Base de datos)
- `flask` (Dashboard web)
- `flask-cors` (CORS para API)
- `rich` (Interfaz de texto mejorada)

### 2. Servicios Externos

**Kafka** debe estar ejecutándose:
```bash
# En Windows (dentro de la carpeta de Kafka)
.\bin\windows\zookeeper-server-start.bat .\config\zookeeper.properties
.\bin\windows\kafka-server-start.bat .\config\server.properties
```

**MySQL** debe estar disponible con la base de datos `evcharging` creada:
```sql
CREATE DATABASE evcharging;
USE evcharging;
-- Ejecutar script db/init.sql
```

### 3. Crear tópicos de Kafka

```bash
# Windows
kafka-topics.bat --create --topic telemetria_cp --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
kafka-topics.bat --create --topic driver_requests --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
kafka-topics.bat --create --topic central_commands --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1

# Linux/Mac
kafka-topics.sh --create --topic telemetria_cp --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
kafka-topics.sh --create --topic driver_requests --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
kafka-topics.sh --create --topic central_commands --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
```

---

## 🚀 Métodos de Lanzamiento

### Método 1: Script Automático de Prueba Masiva (RECOMENDADO)

El script `test_masivo.py` lanza todo el sistema automáticamente.

#### Uso Básico
```bash
python test_masivo.py --cps 10 --drivers 8
```

#### Opciones Completas
```bash
python test_masivo.py \
  --cps 10 \
  --drivers 8 \
  --kafka 127.0.0.1:9092 \
  --db 127.0.0.1:3306:root::evcharging \
  --central-port 5000 \
  --dashboard-port 8080 \
  --delay-drivers 10
```

**Parámetros:**
- `--cps N`: Número de Puntos de Recarga a lanzar (cada uno con Engine + Monitor)
- `--drivers M`: Número de Drivers (clientes) a lanzar
- `--kafka IP:PUERTO`: Dirección del broker Kafka
- `--db CONFIG`: Configuración de BD (formato: `host:port:user:password:database`)
- `--central-port`: Puerto de EV_Central (default: 5000)
- `--dashboard-port`: Puerto del dashboard web (default: 8080)
- `--delay-drivers`: Segundos de espera antes de lanzar drivers (default: 10)
- `--no-dashboard`: No lanzar el dashboard web

#### ¿Qué hace este script?

1. ✅ Lanza **EV_Central** (servidor principal)
2. ✅ Lanza **Dashboard Web** en `http://localhost:8080`
3. ✅ Lanza **N Puntos de Recarga** (cada uno con Engine + Monitor)
4. ✅ Espera a que todo se estabilice
5. ✅ Lanza **M Drivers** que solicitan servicio

**Para detener todo:** Presiona `Ctrl+C` (detendrá todos los procesos ordenadamente)

---

### Método 2: Lanzamiento Manual Modular

Si prefieres control total, puedes lanzar cada componente por separado.

#### Paso 1: Lanzar EV_Central
```bash
python ev_central/EV_Central.py \
  --port 5000 \
  --kafka 127.0.0.1:9092 \
  --db 127.0.0.1:3306:root::evcharging
```

#### Paso 2: Lanzar Dashboard Web (opcional)
```bash
python web_dashboard.py \
  --port 8080 \
  --kafka 127.0.0.1:9092 \
  --central-ip 127.0.0.1 \
  --central-port 5000
```

Accede en: **http://localhost:8080**

#### Paso 3: Lanzar Múltiples CPs
```bash
python launch_multiple_cps.py \
  --num 10 \
  --central-ip 127.0.0.1 \
  --central-port 5000 \
  --kafka 127.0.0.1:9092 \
  --base-port 6000
```

**Parámetros:**
- `--num N`: Cantidad de CPs a crear
- `--central-ip`: IP de la Central
- `--central-port`: Puerto de la Central (default: 5000)
- `--kafka`: Broker Kafka
- `--base-port`: Puerto base para Engines (cada Engine usa `base + N`)
- `--delay`: Segundos entre lanzamientos (default: 1.0)

**Ejemplo de puertos:**
- CP001: Engine en puerto 6001
- CP002: Engine en puerto 6002
- CP010: Engine en puerto 6010

#### Paso 4: Lanzar Múltiples Drivers
```bash
python launch_multiple_drivers.py \
  --num 8 \
  --kafka 127.0.0.1:9092 \
  --cps 10 \
  --mode random
```

**Parámetros:**
- `--num M`: Cantidad de Drivers a lanzar
- `--kafka`: Broker Kafka
- `--cps N`: Número total de CPs disponibles en la red
- `--mode`: Modo de asignación:
  - `random`: Asignación aleatoria (default)
  - `uniform`: Distribución uniforme (round-robin)
  - `first`: Todos al CP001 (prueba de saturación)
- `--kw`: kWh deseados (aleatorio entre 10-50 si no se especifica)
- `--delay`: Segundos entre lanzamientos (default: 0.5)

---

## 📊 Dashboard Web

El dashboard proporciona una interfaz visual para monitorear el sistema en tiempo real.

### Acceso
```
http://localhost:8080
```

### Características

#### Panel de Estadísticas
- **Total CPs**: Número total de puntos de carga registrados
- **Activos**: CPs en estado `ACTIVADO` o `SUMINISTRANDO`
- **Suministrando**: CPs actualmente cargando vehículos
- **Averiados**: CPs con fallos reportados
- **Energía Total**: kWh totales entregados por todos los CPs
- **Sesiones Activas**: Número de cargas en curso

#### Tabla de CPs
Muestra en tiempo real:
- ID del CP
- Estado actual (con código de colores)
- Energía entregada (kWh)
- Potencia actual (kW)
- Tiempo de carga (segundos)
- Última actualización

#### Log de Eventos
Últimos 50 eventos del sistema en orden cronológico inverso.

### API REST del Dashboard

El dashboard expone varios endpoints REST:

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/status` | GET | Estado general del sistema |
| `/api/cps` | GET | Lista de todos los CPs |
| `/api/events` | GET | Log de eventos recientes |
| `/api/stats` | GET | Estadísticas agregadas |
| `/api/command` | POST | Enviar comando a un CP |

**Ejemplo de uso:**
```bash
# Obtener estado general
curl http://localhost:8080/api/status

# Enviar comando STOP a CP001
curl -X POST http://localhost:8080/api/command \
  -H "Content-Type: application/json" \
  -d '{"cp_id":"CP001","command":"STOP"}'
```

---

## 🧪 Escenarios de Prueba

### Escenario 1: Carga Moderada
```bash
python test_masivo.py --cps 5 --drivers 3
```
- 5 Puntos de Recarga
- 3 Drivers simultáneos
- Ideal para verificar funcionalidad básica

### Escenario 2: Alta Concurrencia (Requerimiento del Profesor)
```bash
python test_masivo.py --cps 10 --drivers 8
```
- 10 Puntos de Recarga
- 8 Drivers simultáneos
- Demuestra capacidad de manejo masivo

### Escenario 3: Saturación de un CP
```bash
python launch_multiple_drivers.py --num 5 --kafka 127.0.0.1:9092 --cps 10 --mode first
```
- Todos los drivers solicitan servicio al CP001
- Prueba manejo de cola y denegaciones

### Escenario 4: Estrés Máximo
```bash
python test_masivo.py --cps 20 --drivers 15 --delay-drivers 5
```
- 20 Puntos de Recarga
- 15 Drivers
- Sistema al límite de capacidad

---

## 📈 Monitorización y Logs

### Logs de Central
```bash
# En contenedor Docker
docker exec -it <central_container> cat /app/central.log

# En local
cat central.log
```

### Monitoreo en Tiempo Real
```bash
# Ver mensajes de Kafka (telemetría)
kafka-console-consumer.bat --bootstrap-server localhost:9092 --topic telemetria_cp --from-beginning

# Ver solicitudes de drivers
kafka-console-consumer.bat --bootstrap-server localhost:9092 --topic driver_requests --from-beginning
```

### Dashboard Web
El dashboard muestra información en tiempo real con actualización automática cada 2 segundos.

---

## 🔧 Solución de Problemas

### Error: "Central no responde"
```bash
# Verificar que Central está corriendo
netstat -an | grep 5000

# Verificar logs
docker logs <central_container>
```

### Error: "Kafka no disponible"
```bash
# Verificar Kafka
nc -zv localhost 9092

# Verificar tópicos
kafka-topics.bat --list --bootstrap-server localhost:9092
```

### Error: "Puertos en uso"
```bash
# Cambiar puerto de Central
python test_masivo.py --cps 10 --drivers 8 --central-port 5001

# Cambiar puerto de Dashboard
python test_masivo.py --cps 10 --drivers 8 --dashboard-port 8081
```

### CPs no se registran
1. Verificar que Central está corriendo
2. Verificar IP de Central (si está en Docker, usar IP del contenedor)
3. Revisar logs del Monitor

### Drivers no reciben respuesta
1. Verificar tópicos de Kafka
2. Verificar que los CPs están en estado `ACTIVADO`
3. Revisar logs de Central

---

## 🎯 Validación de Capacidad

Para demostrar al profesor que el sistema soporta **10 CPs y 8 Drivers**:

```bash
# 1. Lanzar prueba masiva
python test_masivo.py --cps 10 --drivers 8

# 2. Abrir dashboard en navegador
# http://localhost:8080

# 3. Observar en el dashboard:
#    - 10 CPs registrados y activos
#    - 8 solicitudes de servicio procesadas
#    - Telemetría en tiempo real de todos los CPs
#    - Estado de cada sesión de carga

# 4. Verificar logs de Central
#    - Registro exitoso de 10 CPs
#    - Procesamiento de 8 solicitudes
#    - Telemetría recibida de todos los CPs
```

**Métricas a mostrar:**
- ✅ Todos los CPs se registran correctamente
- ✅ Todos los Drivers reciben respuesta (autorizado/denegado)
- ✅ Telemetría fluye correctamente por Kafka
- ✅ Dashboard muestra información en tiempo real
- ✅ Sistema mantiene estabilidad durante toda la prueba

---

## 📝 Notas Adicionales

### Arquitectura de Puertos
- **Central**: 5000 (configurable con `--central-port`)
- **Dashboard**: 8080 (configurable con `--dashboard-port`)
- **Engines**: 6001-6020 (base 6000 + número de CP)
- **Kafka**: 9092
- **MySQL**: 3306

### Identificadores
- **CPs**: `CP001`, `CP002`, ..., `CP010` (formato `CP{num:03d}`)
- **Drivers**: `DRIVER_001`, `DRIVER_002`, ..., `DRIVER_008`

### Recursos del Sistema
Para 10 CPs + 8 Drivers:
- **Procesos**: ~31 (1 Central + 1 Dashboard + 20 CPs + 8 Drivers + servicios)
- **RAM estimada**: ~500 MB
- **Puertos usados**: ~21

---

## 🎓 Presentación al Profesor

### Demostración Recomendada

1. **Preparación (5 min)**
   ```bash
   # Terminal 1: Iniciar servicios
   # (Kafka y MySQL deben estar corriendo)
   
   # Terminal 2: Lanzar sistema
   python test_masivo.py --cps 10 --drivers 8
   ```

2. **Mostrar Dashboard (2 min)**
   - Abrir http://localhost:8080 en navegador
   - Mostrar estadísticas en tiempo real
   - Mostrar tabla de CPs con telemetría
   - Mostrar log de eventos

3. **Explicar Arquitectura (3 min)**
   - Mostrar que hay 10 procesos Engine + 10 Monitor
   - Explicar comunicación asíncrona vía Kafka
   - Explicar socket persistente Monitor-Central
   - Mostrar escalabilidad horizontal

4. **Demostrar Funcionalidad (5 min)**
   - Mostrar CPs pasando de ACTIVADO → SUMINISTRANDO
   - Mostrar telemetría actualizada cada segundo
   - Mostrar tickets entregados a Drivers
   - Mostrar manejo de estados

5. **Pruebas Adicionales (opcional)**
   - Lanzar más drivers mientras el sistema está corriendo
   - Simular avería de un CP (Ctrl+C en un Engine)
   - Mostrar recuperación del sistema

---

## 📞 Soporte

Si encuentras problemas:
1. Verifica que Kafka y MySQL estén corriendo
2. Revisa los logs en `central.log`
3. Verifica conectividad de red (especialmente si usas Docker)
4. Asegúrate de que los puertos no estén en uso

**¡Buena suerte con la demostración!** 🚀


