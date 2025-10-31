## EV Charging (SD 25/26)

Pequeño sistema de ejemplo para simular una Central de Carga de VE y un Monitor de Punto de Carga (CP). Incluye:
- `ev_central/EV_Central.py`: servidor TCP que acepta conexiones de CP y gestiona el registro/autenticación y mensajes síncronos.
- `ev_cp_monitor/EV_CP_M.py`: cliente que simula un CP, se registra en la central y escucha comandos.

### Estructura del proyecto
- `ev_central/EV_Central.py`
- `ev_cp_monitor/EV_CP_M.py`
- `ev_common/` (utilidades comunes futuras)
- `requirements.txt`

### Requisitos
- Python 3.10+ (recomendado)
- Pip para instalar dependencias
- Opcional: Kafka (`confluent-kafka`) y MySQL (por ahora impresos/logs; integración futura)

Instala dependencias:
```bash
pip install -r requirements.txt
```
---NUEVO
 Terminal para EV_Central (Servidor Central)
El Central actúa como el servidor principal, escuchando en el puerto 5000
# Cambia localhost por 127.0.0.1
python ev_central/EV_Central.py --port 5000 --kafka "127.0.0.1:9092" --db "127.0.0.1:3306:root::evcharging"

2. Terminal para EV_CP_E (Servidor Local - Engine)
El Engine actúa como un servidor local, escuchando en el puerto 5001.
python ev_cp_engine/EV_CP_E.py --port 5001

3. Terminal para EV_CP_M (Cliente/Monitor)
El Monitor es el cliente que se conecta a ambos servidores. Necesita saber dónde encontrarlos.

python ev_cp_monitor/EV_CP_M.py --cp_id CP001 --central_ip 127.0.0.1 --central_port 5000 --engine_ip 127.0.0.1 --engine_port 5001

4.DRIVER
python ev_driver/EV_Driver.py --kafka "127.0.0.1:9092" --id DRIVER_456 --cp CP_001 --kw 25.0


Si todo va bien, verás en la Central un `REG` recibido y una respuesta `AUTH#OK` enviada; en el Monitor aparecerá el registro exitoso y quedará escuchando comandos.

### Parámetros principales
- Central (`EV_Central.py`):
  - `--port`: puerto TCP de escucha (obligatorio)
  - `--kafka`: broker Kafka `host:puerto` (obligatorio para el arranque; aún no se usa)
  - `--db`: URL de la base de datos (opcional; aún no se usa)

- Monitor (`EV_CP_M.py`): Aplicación que simula un módulo de gestión de observación de todo el CP
  - `--engine_ip` y `--engine_port`: datos del Engine local (placeholder)
  - `--central_ip` y `--central_port`: dirección de la Central
  - `--cp_id`: identificador del punto de carga

### Qué hace cada proceso
- Central:
  - Abre servidor TCP, acepta múltiples CP en hilos.
  - Al recibir `REG`, valida la trama y responde `AUTH#OK` si es correcta.
  - Consume `driver_requests` en Kafka, valida el CP en BD y su estado.
  - Si procede, envía `AUTH_REQ` al Monitor por socket y espera `AUTH_RESP`.
  - Notifica al driver en `driver_status_<ID_DRIVER>` los eventos (RECIBIDA, PENDIENTE, AUTORIZADO/DENEGADO).
  - Mantiene un bucle para mensajes posteriores (AVR, telemetría, etc.).

- Monitor:
  - Se conecta a la Central y envía `REG` con `cp_id`, ubicación y precio.
  - Valida `AUTH#OK` y, si es correcto, inicia un hilo para escuchar comandos.
  - Mantiene un bucle de vida (lógica adicional pendiente).

### Protocolo de comunicación (resumen)
- Envoltura binaria: `STX` + `DATA` + `ETX` + `LRC` (XOR de bytes de `DATA`).
- `DATA` se forma como: `COD_OP#campo1#campo2#...`.
- Ejemplos lógicos (sin STX/ETX/LRC):
  - Envío CP → Central: `REG#CP001#C/Mayor, 45#0.48`
  - Respuesta Central → CP: `AUTH#OK#Autenticacion exitosa`
  - Central → CP (autorización): `AUTH_REQ#ID_DRIVER#KW_DESEADOS`
  - CP → Central (respuesta): `AUTH_RESP#ID_DRIVER#OK|KO#mensaje`

### Flujo de autorización Driver → Central → CP
1) Driver publica en `driver_requests` un JSON: `{id_driver, id_charging_point, matricula, kw_deseados}`.
2) Central valida en BD que el CP exista y esté en estado `Activado`.
   - Estados denegados: `Parado`, `Averiado`, `Desconectado` o `Suministrando` (ocupado).
3) Central envía `AUTH_REQ` por el socket persistente al CP Monitor.
4) CP Monitor responde con `AUTH_RESP` (`OK` o `KO`). Si `OK`, encola `START` hacia el Engine.
5) Central notifica al driver en `driver_status_<ID_DRIVER>` los pasos y el resultado final.

### Solución de problemas
- Puerto en uso: cambia `--port` o cierra procesos previos.
- Firewall: permite conexiones locales en el puerto elegido.
- Dirección Central: asegúrate de que `--central_ip` y `--central_port` coinciden con la Central.
- Encoding/console en Windows: usa PowerShell o CMD; si ves caracteres raros, prueba otra consola.

### Siguientes pasos (roadmap)
- Integrar realmente Kafka (`confluent-kafka`) para eventos asíncronos.
- Persistencia en MySQL: estados de CP y auditoría.
- Ampliar comandos síncronos (p. ej., `START`, `STOP`) y validaciones.
- Extraer utilidades de protocolo a `ev_common/` compartido.

# Para solicitudes del conductor a la Central
kafka-topics.bat --create --topic driver_requests --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1

# Para telemetría del punto de carga a la Central
kafka-topics.bat --create --topic telemetria_cp --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1

# Para comandos de la Central a los puntos de carga
kafka-topics.bat --create --topic central_commands --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1

# Para notificaciones por driver (cada driver tiene su propio tópico)
# Ejemplo para DRIVER_456:
kafka-topics.bat --create --topic driver_status_DRIVER_456 --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1


    
    
    CHAT

========================================
[EV_CP_E] INICIADO
Puerto de escucha: 5001
CP ID: CP_001
Kafka: 172.21.42.3:9092
========================================
[EV_CP_E] Telemetría en reposo. A la espera de START para CP_001

[ENGINE] Menú CP: 'p' Enchufar (Plug) | 'x' Detener (Stop) | 'h' Ayuda
[ENGINE] Acción (p/x/h): [EV_CP_E] Servidor escuchando en TCP (:5001). Esperando Monitor...
[ENGINE] Acción (p/x/h): [ENGINE] Acción (p/x/h): [ENGINE] Acción