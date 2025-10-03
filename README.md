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
python EV_Central.py --port 5000 --kafka "localhost:9092" --db "mysql://user:pass@host/db"

2. Terminal para EV_CP_E (Servidor Local - Engine)
El Engine actúa como un servidor local, escuchando en el puerto 5001.
python EV_CP_E.py --port 5001

3. Terminal para EV_CP_M (Cliente/Monitor)
El Monitor es el cliente que se conecta a ambos servidores. Necesita saber dónde encontrarlos.

python EV_CP_M.py --cp_id CP001 --central_ip 127.0.0.1 --central_port 5000 --engine_ip 127.0.0.1 --engine_port 5001



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
  - Mantiene un bucle para mensajes posteriores (pendiente de ampliar: AVR, telemetría, etc.).

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
