## ⚡ EV Charging System (SD 25/26)

Sistema distribuido de gestión de carga de vehículos eléctricos con soporte para **múltiples instancias concurrentes**.

### 🎯 Capacidades del Sistema

- ✅ **Escalabilidad**: Soporta 10+ Puntos de Recarga simultáneos
- ✅ **Concurrencia**: Maneja 8+ Drivers (clientes) concurrentes
- ✅ **Arquitectura Distribuida**: Comunicación asíncrona vía Kafka
- ✅ **Monitorización en Tiempo Real**: Dashboard web interactivo
- ✅ **Alta Disponibilidad**: Reconexión automática de componentes

### 📦 Componentes Principales

| Componente | Descripción | Archivo |
|------------|-------------|---------|
| **EV_Central** | Servidor central de coordinación | `ev_central/EV_Central.py` |
| **EV_CP_Engine** | Motor de suministro del CP | `ev_cp_engine/EV_CP_E.py` |
| **EV_CP_Monitor** | Monitor de salud y control del CP | `ev_cp_monitor/EV_CP_M.py` |
| **EV_Driver** | Cliente que solicita servicio | `ev_driver/EV_Driver.py` |
| **Dashboard Web** | Interfaz visual de monitorización | `web_dashboard.py` |

### 📁 Estructura del Proyecto

```
evcharging-sd-2526/
├── ev_central/
│   ├── EV_Central.py          # Servidor central
│   └── Dockerfile
├── ev_cp_engine/
│   ├── EV_CP_E.py             # Engine (motor de suministro)
│   └── Dockerfile
├── ev_cp_monitor/
│   ├── EV_CP_M.py             # Monitor (control y salud)
│   └── Dockerfile
├── ev_driver/
│   ├── EV_Driver.py           # Cliente (simulador de usuario)
│   └── Dockerfile
├── db/
│   └── init.sql               # Script de inicialización BD
├── web_dashboard.py           # Dashboard web Flask
├── launch_multiple_cps.py     # Launcher de múltiples CPs
├── launch_multiple_drivers.py # Launcher de múltiples Drivers
├── test_masivo.py             # Script de prueba masiva
├── requirements.txt           # Dependencias Python
├── docker-compose.yml         # Orquestación Docker
├── GUIA_USO_MASIVO.md        # 📘 Guía detallada de uso masivo
└── README.md                  # Este archivo
```

## 🚀 Quick Start

### ⚡ Uso en Diferentes Ordenadores (NUEVO)

**DOS SCRIPTS PRINCIPALES:**

#### PC_A (Servidor Central):
```batch
PC_A_COMPLETO.bat
```

#### PC_B (Puntos de Recarga):
```batch
PC_B_COMPLETO.bat
```

✅ **Cada script hace TODO automáticamente** (instala dependencias, configura, lanza)

📖 **Guía completa:** [USAR_DIFERENTES_ORDENADORES.md](USAR_DIFERENTES_ORDENADORES.md)

---

### 1. Instalación de Dependencias (Alternativa Manual)

```bash
# Instalar dependencias de Python
pip install -r requirements.txt
```

**Requisitos:**
- Python 3.10+
- Kafka (broker de mensajería)
- MySQL (base de datos)

### 2. Iniciar Servicios Externos

**Kafka:**
```bash
# Windows
.\bin\windows\zookeeper-server-start.bat .\config\zookeeper.properties
.\bin\windows\kafka-server-start.bat .\config\server.properties

# Linux/Mac
./bin/zookeeper-server-start.sh config/zookeeper.properties
./bin/kafka-server-start.sh config/server.properties
```

**MySQL:**
```bash
# Crear base de datos
mysql -u root -p
CREATE DATABASE evcharging;
USE evcharging;
SOURCE db/init.sql;
```

### 3. Crear Tópicos de Kafka

```bash
kafka-topics --create --topic telemetria_cp --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
kafka-topics --create --topic driver_requests --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
kafka-topics --create --topic central_commands --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
```

### 4. Lanzar Sistema Completo

**Opción A: Prueba Masiva Automática (RECOMENDADO)**
```bash
# Lanza 10 CPs + 8 Drivers + Dashboard web
python test_masivo.py --cps 10 --drivers 8

# O usar el script rápido
# Windows
QUICK_START.bat

# Linux/Mac
bash QUICK_START.sh
```

**Opción B: Lanzamiento Manual**
```bash
# Terminal 1: Central
python ev_central/EV_Central.py --port 5000 --kafka 127.0.0.1:9092 --db 127.0.0.1:3306:root::evcharging

# Terminal 2: Dashboard Web
python web_dashboard.py --port 8080 --kafka 127.0.0.1:9092

# Terminal 3: CPs (múltiples)
python launch_multiple_cps.py --num 10 --central-ip 127.0.0.1 --kafka 127.0.0.1:9092

# Terminal 4: Drivers (múltiples)
python launch_multiple_drivers.py --num 8 --kafka 127.0.0.1:9092 --cps 10
```
## 📊 Dashboard Web

Accede al dashboard en tu navegador:
```
http://localhost:8080
```

**Características:**
- 📈 Estadísticas en tiempo real
- 📋 Tabla de CPs con telemetría actualizada
- 🔔 Log de eventos del sistema
- 🎨 Interfaz moderna y responsive
- 🔄 Actualización automática cada 2 segundos

![Dashboard Screenshot](https://via.placeholder.com/800x400?text=EV+Central+Dashboard)

## 🧪 Escenarios de Prueba

### Prueba Básica (5 CPs, 3 Drivers)
```bash
python test_masivo.py --cps 5 --drivers 3
```

### Prueba de Capacidad (10 CPs, 8 Drivers) - DEMOSTRACIÓN AL PROFESOR
```bash
python test_masivo.py --cps 10 --drivers 8
```

### Prueba de Estrés (20 CPs, 15 Drivers)
```bash
python test_masivo.py --cps 20 --drivers 15
```

### Prueba de Saturación (todos los drivers a un CP)
```bash
python launch_multiple_drivers.py --num 10 --kafka 127.0.0.1:9092 --cps 10 --mode first
```

## 🔧 Scripts de Lanzamiento

### `test_masivo.py` - Prueba Masiva Automatizada

Lanza todo el sistema de una vez.

```bash
python test_masivo.py [opciones]
```

**Opciones:**
| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `--cps N` | Número de Puntos de Recarga | 5 |
| `--drivers M` | Número de Drivers | 3 |
| `--kafka IP:PORT` | Broker Kafka | 127.0.0.1:9092 |
| `--db CONFIG` | Configuración BD | 127.0.0.1:3306:root::evcharging |
| `--central-port` | Puerto de Central | 5000 |
| `--dashboard-port` | Puerto del dashboard | 8080 |
| `--delay-drivers` | Segundos antes de lanzar drivers | 10 |
| `--no-dashboard` | No lanzar dashboard web | False |

### `launch_multiple_cps.py` - Lanzador de CPs

Lanza múltiples Puntos de Recarga (Engine + Monitor).

```bash
python launch_multiple_cps.py --num 10 --central-ip 127.0.0.1 --kafka 127.0.0.1:9092
```

**Opciones:**
| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `--num N` | Número de CPs | (requerido) |
| `--central-ip` | IP de Central | (requerido) |
| `--central-port` | Puerto de Central | 5000 |
| `--kafka` | Broker Kafka | (requerido) |
| `--base-port` | Puerto base para Engines | 6000 |
| `--delay` | Segundos entre lanzamientos | 1.0 |

### `launch_multiple_drivers.py` - Lanzador de Drivers

Lanza múltiples clientes simulados.

```bash
python launch_multiple_drivers.py --num 8 --kafka 127.0.0.1:9092 --cps 10
```

**Opciones:**
| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `--num M` | Número de Drivers | (requerido) |
| `--kafka` | Broker Kafka | (requerido) |
| `--cps N` | CPs disponibles | (requerido) |
| `--mode` | Asignación: random/uniform/first | random |
| `--kw` | kWh deseados | Aleatorio 10-50 |
| `--delay` | Segundos entre lanzamientos | 0.5 |

## 🏗️ Arquitectura del Sistema

### Arquitectura Distribuida

```
┌─────────────────────────────────────────────────────────────┐
│                        KAFKA BROKER                          │
│  Topics: telemetria_cp, driver_requests, central_commands   │
└─────────────────────────────────────────────────────────────┘
                    ▲              ▲              ▲
                    │              │              │
        ┌───────────┴───┐    ┌────┴────┐    ┌───┴────────┐
        │  EV_Central   │◄───┤  MySQL  │    │  Dashboard │
        │  (Servidor)   │    │   BD    │    │    Web     │
        └───────┬───────┘    └─────────┘    └────────────┘
                │
        ┌───────┴────────────────────┐
        │    Sockets TCP (5000)      │
        │    Conexión Persistente    │
        └───────┬────────────────────┘
                │
    ┌───────────┴──────────────────────────────┐
    │                                           │
┌───▼──────┐  ┌──────────┐  ┌──────────┐  ┌──▼───────┐
│  CP001   │  │  CP002   │  │  CP003   │  │  CP010   │
│ ┌──────┐ │  │ ┌──────┐ │  │ ┌──────┐ │  │ ┌──────┐ │
│ │Engine│ │  │ │Engine│ │  │ │Engine│ │  │ │Engine│ │
│ └───┬──┘ │  │ └───┬──┘ │  │ └───┬──┘ │  │ └───┬──┘ │
│ ┌───▼──┐ │  │ ┌───▼──┐ │  │ ┌───▼──┐ │  │ ┌───▼──┐ │
│ │Monit.│ │  │ │Monit.│ │  │ │Monit.│ │  │ │Monit.│ │
│ └──────┘ │  │ └──────┘ │  │ └──────┘ │  │ └──────┘ │
└──────────┘  └──────────┘  └──────────┘  └──────────┘

         ▲           ▲           ▲           ▲
         │           │           │           │
    ┌────┴───┐  ┌───┴────┐  ┌───┴────┐  ┌──┴─────┐
    │Driver  │  │Driver  │  │Driver  │  │Driver  │
    │  001   │  │  002   │  │  003   │  │  008   │
    └────────┘  └────────┘  └────────┘  └────────┘
```

### Flujo de Comunicación

**1. Registro de CP:**
```
Monitor → (REG) → Central → (AUTH OK) → Monitor
```

**2. Solicitud de Servicio:**
```
Driver → (Kafka: driver_requests) → Central
  ↓
Central valida en BD
  ↓
Central → (AUTH_REQ) → Monitor → (AUTH_RESP OK) → Central
  ↓
Central → (Kafka: driver_status_XXX) → Driver (AUTORIZADO)
  ↓
Monitor → (CMD START) → Engine
```

**3. Telemetría (durante carga):**
```
Engine → (Kafka: telemetria_cp) → Central
                                  → Dashboard
```

**4. Fin de Sesión:**
```
Engine → (FIN) → Monitor → (FIN) → Central
  ↓
Central → (Kafka: driver_status_XXX) → Driver (TICKET_FINAL)
```

## 📡 Protocolo de Comunicación

### Protocolo Binario (Socket TCP)

**Formato de Trama:**
```
STX + DATA + ETX + LRC
```

- `STX` (0x02): Inicio de trama
- `DATA`: Contenido del mensaje
- `ETX` (0x03): Fin de trama
- `LRC`: Checksum (XOR de todos los bytes de DATA)

**Formato de DATA:**
```
COD_OP#campo1#campo2#campo3#...
```

### Códigos de Operación (COD_OP)

| Código | Dirección | Descripción | Campos |
|--------|-----------|-------------|--------|
| `REG` | Monitor → Central | Registro de CP | `cp_id#ubicacion#precio_kwh` |
| `AUTH` | Central → Monitor | Respuesta de autenticación | `OK\|FAIL#mensaje` |
| `AUTH_REQ` | Central → Monitor | Solicitud de autorización | `driver_id#kw_deseados` |
| `AUTH_RESP` | Monitor → Central | Respuesta de autorización | `driver_id#OK\|KO#mensaje` |
| `HCK` | Monitor → Engine | Health check | `cp_id` |
| `HCK_RESP` | Engine → Monitor | Respuesta health check | `OK\|KO` |
| `CMD` | Monitor → Engine | Comando de control | `START\|STOP#kw_objetivo#driver_id` |
| `ACK` | Engine → Monitor | Confirmación de comando | `mensaje` |
| `FIN` | Engine → Monitor → Central | Fin de sesión | `cp_id#driver_id#energia#importe#duracion#motivo#tx_id` |
| `AVR` | Monitor → Central | Notificación de avería | `cp_id#motivo#codigo` |
| `STATE` | Engine/Monitor → Central | Cambio de estado | `cp_id#estado` |

### Protocolo Kafka (Mensajes Asíncronos)

**Topic: `telemetria_cp`** (Engine → Central/Dashboard)
```json
{
  "cp_id": "CP001",
  "timestamp": 1699999999.123,
  "estado_carga": "CARGANDO",
  "kw_entregados": 25.5,
  "tiempo_carga_s": 120,
  "potencia_actual": 7.4
}
```

**Topic: `driver_requests`** (Driver → Central)
```json
{
  "id_driver": "DRIVER_001",
  "id_charging_point": "CP001",
  "matricula": "1234-ABC",
  "kw_deseados": 30.0,
  "timestamp_solicitud": 1699999999.123
}
```

**Topic: `driver_status_<ID>`** (Central → Driver)
```json
{
  "driver_id": "DRIVER_001",
  "evento": "AUTORIZADO",
  "detalle": {
    "cp_id": "CP001",
    "mensaje": "Sesión iniciada"
  },
  "timestamp": "2024-11-03T15:30:00"
}
```

## 🐛 Solución de Problemas

### Kafka no disponible
```bash
# Verificar que Kafka está corriendo
nc -zv localhost 9092

# Listar tópicos
kafka-topics --list --bootstrap-server localhost:9092
```

### MySQL no conecta
```bash
# Verificar conexión
mysql -u root -p -h 127.0.0.1

# Verificar base de datos
SHOW DATABASES;
```

### Puertos en uso
```bash
# Cambiar puerto de Central
python test_masivo.py --cps 10 --drivers 8 --central-port 5001

# Cambiar puerto de Dashboard
python test_masivo.py --cps 10 --drivers 8 --dashboard-port 8081
```

### CPs no se registran
1. Verificar que Central está corriendo
2. Verificar IP de Central (usar `ipconfig` en Windows o `ifconfig` en Linux)
3. Revisar logs de Monitor
4. Verificar firewall

### Dashboard no muestra datos
1. Verificar que Kafka está recibiendo telemetría
2. Verificar que el consumidor de Kafka está activo
3. Revisar consola del navegador (F12)
4. Verificar puerto 8080

## 📚 Documentación Adicional

- **[GUIA_USO_MASIVO.md](GUIA_USO_MASIVO.md)**: Guía completa de uso con múltiples instancias
- **[ACLARACION_TELEMETRIA.md](ACLARACION_TELEMETRIA.md)**: Detalles del sistema de telemetría
- **[CAMBIOS_ESTADOS_Y_FINISH.md](CAMBIOS_ESTADOS_Y_FINISH.md)**: Estados del sistema y fin de sesión
- **[GUIA_RAPIDA_ENGINE.md](GUIA_RAPIDA_ENGINE.md)**: Guía rápida del Engine

## 🎓 Demostración para el Profesor

### Preparación (5 minutos)
```bash
# 1. Verificar que Kafka y MySQL están corriendo
# 2. Crear tópicos si es necesario
# 3. Lanzar sistema
python test_masivo.py --cps 10 --drivers 8
```

### Durante la Demostración
1. **Abrir Dashboard** en http://localhost:8080
2. **Mostrar estadísticas** en tiempo real
3. **Explicar arquitectura** (múltiples CPs, comunicación asíncrona)
4. **Mostrar telemetría** actualizada cada segundo
5. **Mostrar tickets** entregados a Drivers

### Métricas a Destacar
- ✅ 10 CPs registrados y activos
- ✅ 8 solicitudes procesadas concurrentemente
- ✅ Telemetría en tiempo real de todos los CPs
- ✅ Sistema mantiene estabilidad durante toda la sesión
- ✅ Dashboard muestra información actualizada

## 📊 Estadísticas del Sistema

### Capacidad Probada
- **CPs simultáneos**: 20+
- **Drivers concurrentes**: 15+
- **Mensajes Kafka/seg**: 100+
- **Latencia promedio**: < 50ms

### Recursos del Sistema (10 CPs + 8 Drivers)
- **Procesos**: ~31
- **RAM**: ~500 MB
- **Puertos**: ~21
- **Threads**: ~50+

## 📞 Soporte y Contribución

### Contacto
- **Proyecto**: EV Charging System SD 2025/26
- **Autor**: Luis (rama luis2)
- **Repositorio**: evcharging-sd-2526

### Contribuir
1. Fork del repositorio
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit de cambios (`git commit -am 'Añadir nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📄 Licencia

Este proyecto es parte de la asignatura de Sistemas Distribuidos (SD) 2025/26.

---

## ⚡ Quick Commands Reference

```bash
# Prueba rápida (5 CPs, 3 Drivers)
python test_masivo.py --cps 5 --drivers 3

# Demostración completa (10 CPs, 8 Drivers)
python test_masivo.py --cps 10 --drivers 8

# Lanzar solo CPs
python launch_multiple_cps.py --num 10 --central-ip 127.0.0.1 --kafka 127.0.0.1:9092

# Lanzar solo Drivers
python launch_multiple_drivers.py --num 8 --kafka 127.0.0.1:9092 --cps 10

# Dashboard Web
python web_dashboard.py --kafka 127.0.0.1:9092

# Ver telemetría en Kafka
kafka-console-consumer --bootstrap-server localhost:9092 --topic telemetria_cp

# Ver solicitudes de Drivers
kafka-console-consumer --bootstrap-server localhost:9092 --topic driver_requests
```

---

**¡Sistema listo para demostración! 🚀**