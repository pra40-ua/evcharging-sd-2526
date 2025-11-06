import socket
import argparse
import threading
import time
from collections import deque
from queue import Queue, Empty
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from kafka import KafkaConsumer, KafkaProducer
import json
import os
import sys
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich import box
import logging
try:
    import msvcrt as MSVCRT
except Exception:
    MSVCRT = None

# =================================================================
#                 ESTADO GLOBAL DE CONEXIONES ACTIVAS
# =================================================================

# Diccionario de CP_ID -> socket
CONEXIONES_ACTIVAS = {}
CONEXIONES_ACTIVAS_LOCK = threading.Lock()

# Diccionario para almacenar la telemetría más reciente de cada CP
TELEMETRIA_ACTUAL = {}
TELEMETRIA_ACTUAL_LOCK = threading.Lock()

# Estado manual (START/STOP ordenado por la Central) para reflejar en TUI
CP_ESTADO_MANUAL = {}
CP_ESTADO_MANUAL_LOCK = threading.Lock()

# Estado de alerta/avería detectado (por AVR o telemetría)
CP_ALERTA = {}
CP_ALERTA_LOCK = threading.Lock()

# Estado explícito de cada CP (pilar de la TUI y lógica)
CP_ESTADO = {}
CP_ESTADO_LOCK = threading.Lock()

# Precio kWh anunciado por cada CP (desde REG)
CP_PRECIO_KWH = {}
CP_PRECIO_KWH_LOCK = threading.Lock()

# Objetivo de kWh solicitado por Driver (por CP) para mostrar durante la sesión
CP_SESION_OBJETIVO_KWH = {}
CP_SESION_OBJETIVO_KWH_LOCK = threading.Lock()

# Driver actual de la sesión (por CP) para tickets y referencia
CP_SESION_DRIVER_ID = {}
CP_SESION_DRIVER_ID_LOCK = threading.Lock()

# Cola de espera por CP (cuando múltiples drivers solicitan el mismo CP)
CP_COLA_ESPERA = {}  # cp_id -> Queue de (driver_id, kw_deseados, timestamp)
CP_COLA_ESPERA_LOCK = threading.Lock()

# Estados del flujo interactivo (para confirmaciones en web)
# cp_id -> 'LISTO_PARA_INICIAR' o 'ESPERANDO_CONFIRMACION_FIN'
CP_PENDIENTE_CONFIRMACION = {}
CP_PENDIENTE_CONFIRMACION_LOCK = threading.Lock()

# Lista de hilos de clientes para cierre ordenado
CLIENT_THREADS = []
CLIENT_THREADS_LOCK = threading.Lock()

# Variable global para controlar el apagado limpio
SHUTDOWN_REQUESTED = False
SHUTDOWN_LOCK = threading.Lock()

# Cola de comandos ingresados por el operador (desde consola)
COMMAND_QUEUE: Queue = Queue()

# Registro de eventos (histórico en memoria)
EVENT_LOG = deque(maxlen=300)
EVENT_LOG_LOCK = threading.Lock()

# =================================================================
#                         REGISTRO / LOGS
# =================================================================

console = Console()
# Usar una ruta compatible con Windows y Linux
log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'central.log')
logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(message)s')

def registrar_evento(mensaje: str, tipo="info") -> None:
    """Registro de eventos con Rich + logging a archivo."""
    timestamp = datetime.now().strftime('%H:%M:%S')
    linea = f"[{timestamp}] {mensaje}"
    color = {"info": "cyan", "warn": "yellow", "error": "red", "ok": "green"}.get(tipo, "white")
    with EVENT_LOG_LOCK:
        EVENT_LOG.append(linea)
    try:
        console.print(f"[{color}]{linea}[/{color}]")
    except Exception:
        try:
            print(linea)
        except Exception:
            pass
    try:
        logging.info(linea)
    except Exception:
        pass

def resumen_telemetria(telemetria: dict) -> str:
    """Devuelve un breve resumen textual de una telemetría para logs."""
    if not isinstance(telemetria, dict):
        return "-"
    estado = telemetria.get('estado') or telemetria.get('estado_carga') or 'N/D'
    energia = (
        telemetria.get('energia_total')
        if 'energia_total' in telemetria
        else telemetria.get('kwh', telemetria.get('kw_entregados', 'N/D'))
    )
    potencia = telemetria.get('potencia_actual', 'N/D')
    try:
        energia_str = f"{float(energia):.2f}" if energia not in ('N/D', None) else 'N/D'
    except Exception:
        energia_str = str(energia)
    return f"est={estado}, E={energia_str}, P={potencia}"

def bucle_entrada_comandos_windows() -> None:
    """Lector no bloqueante de teclado en Windows usando msvcrt.
    Acepta:
      - Teclas rápidas: '1' y '3' (si el buffer está vacío)
      - Comandos completos: escribir texto y pulsar Enter (\r)
    """
    if MSVCRT is None:
        # Fallback: usar entrada clásica por consola si MSVCRT no está disponible
        interfaz_consola_central()
        return
    buffer_chars = []
    while True:
        with SHUTDOWN_LOCK:
            if SHUTDOWN_REQUESTED:
                return
        try:
            if MSVCRT.kbhit():
                ch = MSVCRT.getwch()
                if ch in ('\r', '\n'):
                    cmd = ''.join(buffer_chars).strip()
                    buffer_chars = []
                    if cmd:
                        COMMAND_QUEUE.put(cmd)
                        registrar_evento(f"Entrada recibida: {cmd}")
                elif ch in ('\x08', '\x7f'):  # Backspace
                    if buffer_chars:
                        buffer_chars.pop()
                elif not buffer_chars and ch in ('1', '3'):
                    # Atajos rápidos cuando no hay texto previo
                    COMMAND_QUEUE.put(ch)
                    registrar_evento(f"Entrada rápida: {ch}")
                elif ch == '\x03':  # Ctrl+C
                    COMMAND_QUEUE.put('3')
                    registrar_evento("Entrada Ctrl+C -> 3 (Salir)")
                else:
                    # Acumular caracteres para comandos largos (ej.: 2 START CP001)
                    # Filtrar caracteres no imprimibles básicos
                    if ch.isprintable() or ch == ' ':
                        buffer_chars.append(ch)
            else:
                time.sleep(0.05)
        except Exception:
            # En caso de error inesperado, pequeño backoff
            time.sleep(0.1)

def _enviar_comando_cp(cp_id: str, orden: str) -> bool:
    with CONEXIONES_ACTIVAS_LOCK:
        cp_socket = CONEXIONES_ACTIVAS.get(cp_id)
    if not cp_socket:
        registrar_evento(f"ERROR: CP {cp_id} no conectado")
        return False
    try:
        # Para START, necesitamos enviar los parámetros de sesión si existen
        if orden.upper() == 'START':
            # Obtener los parámetros de la sesión activa
            with CP_SESION_DRIVER_ID_LOCK:
                driver_id = CP_SESION_DRIVER_ID.get(cp_id)
            with CP_SESION_OBJETIVO_KWH_LOCK:
                kw_objetivo = CP_SESION_OBJETIVO_KWH.get(cp_id)
            
            if driver_id and kw_objetivo:
                # Hay sesión activa válida: iniciar carga
                trama = construir_trama('START', [driver_id, str(kw_objetivo)])
                registrar_evento(f"Iniciando carga en {cp_id} (Driver: {driver_id}, kW: {kw_objetivo})")
            else:
                # Sin sesión activa: NO se puede iniciar
                registrar_evento(f"ERROR: No hay sesión activa en {cp_id}. Se requiere solicitud de driver primero.", "error")
                return False
        else:
            # Para STOP y otros comandos
            trama = construir_trama(orden, ['MANUAL'])
        
        cp_socket.sendall(trama)
        
        if orden.upper() == 'START':
            # Publicar telemetría actualizada con sesión activa
            try:
                with CP_SESION_DRIVER_ID_LOCK:
                    driver_id_sesion = CP_SESION_DRIVER_ID.get(cp_id)
                with TELEMETRIA_ACTUAL_LOCK:
                    telemetria_actual = TELEMETRIA_ACTUAL.get(cp_id, {})
                telemetria_actualizada = {
                    **telemetria_actual,
                    'cp_id': cp_id,
                    'estado_carga': 'PRE-SUMINISTRO',
                    'estado': 'PRE-SUMINISTRO',
                    'timestamp': time.time(),
                    'tiene_sesion_activa': True,
                    'driver_id_sesion': driver_id_sesion
                }
                with TELEMETRIA_ACTUAL_LOCK:
                    TELEMETRIA_ACTUAL[cp_id] = telemetria_actualizada
                if KAFKA_PRODUCER:
                    KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_actualizada)
                    KAFKA_PRODUCER.flush(timeout=1)
                    print(f"[CENTRAL] Telemetría actualizada publicada para {cp_id} (sesión iniciada manualmente)")
            except Exception as e:
                print(f"[CENTRAL] No se pudo publicar telemetría actualizada: {e}")
        elif orden.upper() == 'STOP':
            # Al hacer STOP, el CP enviará FIN con los datos finales
            # No limpiamos la sesión aquí, se limpiará al recibir FIN
            registrar_evento(f"Enviando STOP a {cp_id}. Esperando FIN con datos finales...")
            print(f"[CENTRAL] Comando STOP enviado a {cp_id}. Aguardando respuesta FIN del CP...")
        
        registrar_evento(f"Comando {orden} enviado a {cp_id}")
        return True
    except Exception as e:
        registrar_evento(f"ERROR enviando {orden} a {cp_id}: {e}")
        return False

def bucle_procesador_comandos() -> None:
    global SHUTDOWN_REQUESTED
    while True:
        with SHUTDOWN_LOCK:
            if SHUTDOWN_REQUESTED:
                return
        try:
            cmd = COMMAND_QUEUE.get(timeout=0.25)
        except Empty:
            continue
        texto = cmd.strip()
        up = texto.upper()
        if up == '1':
            # Mostrar todos los CP (engines/monitores) conectados y su estado
            try:
                mostrar_estado_red()
            except Exception:
                registrar_evento("Error mostrando estado de la red")
            continue
        if up == '3' or up == 'EXIT' or up == 'QUIT':
            registrar_evento("Apagado solicitado por operador")
            with SHUTDOWN_LOCK:
                SHUTDOWN_REQUESTED = True
            continue
        # Comando tipo: admite "2 CP_001 START" o "2 START CP_001"
        if up.startswith('2'):
            partes = texto.split()
            if len(partes) < 3:
                registrar_evento("Uso: 2 START|STOP CP_ID (ej.: 2 START CP001)")
                continue
            token_a = partes[1].upper()
            token_b = partes[2].upper()
            orden = None
            cp_id = None
            if token_a in ("START", "STOP") and token_b not in ("START", "STOP"):
                orden = token_a
                cp_id = partes[2]
            elif token_b in ("START", "STOP") and token_a not in ("START", "STOP"):
                orden = token_b
                cp_id = partes[1]
            else:
                registrar_evento("Uso: 2 START|STOP CP_ID (ej.: 2 START CP001)")
                continue
            _enviar_comando_cp(cp_id, orden)
            continue
        # También admitir formato directo: START CP_ID o STOP CP_ID
        if up.startswith('START ') or up.startswith('STOP '):
            partes = texto.split()
            if len(partes) >= 2:
                orden = partes[0].upper()
                cp_id = partes[1]
                _enviar_comando_cp(cp_id, orden)
                continue
        registrar_evento(f"Comando no reconocido: {texto}")

# =================================================================
#                         FUNCIONES DE PROTOCOLO
# =================================================================

# Constantes de Protocolo
STX = b'\x02'
ETX = b'\x03'
DELIMITER = '#'
TELEMETRIA_TOPIC = 'telemetria_cp'
DRIVER_REQUESTS_TOPIC = 'driver_requests'
CENTRAL_COMMANDS_TOPIC = 'central_commands'

# Productor Kafka global para notificar a Drivers
KAFKA_PRODUCER = None
KAFKA_PRODUCER_LOCK = threading.Lock()

def publicar_telemetria_kafka(cp_id: str, telemetria_data: dict):
    """
    Publica telemetría actualizada a Kafka para que el dashboard la vea.
    """
    try:
        if KAFKA_PRODUCER:
            # Enriquecer con información de sesión
            with CP_SESION_DRIVER_ID_LOCK:
                telemetria_data['tiene_sesion_activa'] = cp_id in CP_SESION_DRIVER_ID
                telemetria_data['driver_id_sesion'] = CP_SESION_DRIVER_ID.get(cp_id, None)
            
            # Asegurar campos obligatorios
            if 'timestamp' not in telemetria_data:
                telemetria_data['timestamp'] = time.time()
            if 'cp_id' not in telemetria_data:
                telemetria_data['cp_id'] = cp_id
            
            # Publicar a Kafka
            KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_data)
            KAFKA_PRODUCER.flush(timeout=1)
            print(f"[CENTRAL] → Telemetría de {cp_id} publicada a Kafka: kW={telemetria_data.get('kw_entregados', 0)}, P={telemetria_data.get('potencia_actual', 0)}")
    except Exception as e:
        print(f"[CENTRAL] Error publicando telemetría a Kafka: {e}")

def consumir_telemetria_kafka(broker_list: str):
    """
    Se conecta a Kafka y consume mensajes del tópico de telemetría.
    """
    print(f"[KAFKA CONSUMER] Conectando al broker: {broker_list}")
    consumer = None
    try:
        # Configuración del Consumidor
        consumer = KafkaConsumer(
            TELEMETRIA_TOPIC,
            bootstrap_servers=[broker_list],
            security_protocol='PLAINTEXT',
            api_version=(2, 5, 0),
            # Deserializador para convertir los bytes del mensaje a un diccionario de Python
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            # Si hay offset confirmado previo, retomamos desde ahí; si no, desde lo más reciente
            auto_offset_reset='latest',
            enable_auto_commit=True,
            group_id='central-telemetry-group' # Grupo para distribuir la carga si hay múltiples centrales
        )
        
        print(f"[KAFKA CONSUMER] Suscrito al tópico '{TELEMETRIA_TOPIC}'. Esperando telemetría...")

        # Bucle de consumo con verificación de apagado no bloqueante
        while True:
            # Verificar si se solicita el apagado
            with SHUTDOWN_LOCK:
                if SHUTDOWN_REQUESTED:
                    print("[KAFKA CONSUMER] Apagado solicitado, cerrando consumidor de telemetría...")
                    break

            records = consumer.poll(timeout_ms=1000)
            if not records:
                continue

            for _tp, batch in records.items():
                for message in batch:
                    # Aquí 'message.value' es el diccionario de Python gracias al deserializador
                    telemetria = message.value
                    cp_id = telemetria.get('cp_id', 'UNKNOWN')

                    # Validar que el CP esté REGISTRADO/CONECTADO por socket
                    with CONEXIONES_ACTIVAS_LOCK:
                        conectado = cp_id in CONEXIONES_ACTIVAS
                    if not conectado:
                        continue

                    # --- Almacenar telemetría en estructura global ---
                    # Asegurar timestamp presente para heartbeat/TUI
                    if 'timestamp' not in telemetria or not telemetria.get('timestamp'):
                        telemetria['timestamp'] = time.time()
                    
                    # Enriquecer telemetría con información de sesión activa
                    with CP_SESION_DRIVER_ID_LOCK:
                        telemetria['tiene_sesion_activa'] = cp_id in CP_SESION_DRIVER_ID
                        telemetria['driver_id_sesion'] = CP_SESION_DRIVER_ID.get(cp_id, None)
                    
                    with TELEMETRIA_ACTUAL_LOCK:
                        TELEMETRIA_ACTUAL[cp_id] = telemetria

                    # --- Guardar histórico de telemetría en BD si disponible ---
                    try:
                        # Intentar usar variable cerrada sobre db_connection si existe en enclosing scope
                        db_conn = globals().get('_DB_CONN_FOR_CONSUMER')
                        if db_conn and db_conn.is_connected():
                            cursor = db_conn.cursor()
                            cursor.execute("""
                                INSERT INTO telemetria_log (cp_id, timestamp, estado_carga, kw_entregados, tiempo_carga_s)
                                VALUES (%s, %s, %s, %s, %s)
                            """, (
                                cp_id,
                                telemetria.get('timestamp', time.time()),
                                telemetria.get('estado_carga', telemetria.get('estado', 'N/D')),
                                telemetria.get('kw_entregados', telemetria.get('energia_total', 0.0)),
                                telemetria.get('tiempo_carga_s', 0)
                            ))
                            db_conn.commit()
                            cursor.close()
                    except Exception as e:
                        registrar_evento(f"[WARN] No se pudo registrar telemetría: {e}", "warn")

                    # --- Lógica principal del Central ---
                    # Mostrar objetivo solicitado si existe
                    objetivo_txt = ''
                    objetivo_kwh = None
                    try:
                        with CP_SESION_OBJETIVO_KWH_LOCK:
                            obj = CP_SESION_OBJETIVO_KWH.get(cp_id)
                        if obj is not None:
                            objetivo_kwh = float(obj)
                            objetivo_txt = f" | Solicitado={objetivo_kwh:.2f} kWh"
                    except Exception:
                        objetivo_txt = ''
                    registrar_evento(f"Telemetría recibida de {cp_id}: {resumen_telemetria(telemetria)}{objetivo_txt}")
                    print(f"[KAFKA CONSUMER] -> Telemetría de {cp_id} recibida: {telemetria}{objetivo_txt}")

                    # Promover estados por telemetría (respetando PARADO manual)
                    est_raw = telemetria.get('estado') or telemetria.get('estado_carga')
                    est = str(est_raw or '').strip().lower()
                    try:
                        manual_parado = False
                        with CP_ESTADO_MANUAL_LOCK:
                            manual_parado = CP_ESTADO_MANUAL.get(cp_id) == 'PARADO'
                        if est in ("cargando", "suministrando", "charging", "en_carga"):
                            if not manual_parado:
                                # Mostrar objetivo en el mensaje de cambio de estado
                                estado_info = f'SUMINISTRANDO{objetivo_txt}'
                                cambiar_estado_cp(cp_id, 'SUMINISTRANDO')
                                if objetivo_kwh:
                                    energia_actual = telemetria.get('kw_entregados', 0.0)
                                    try:
                                        progreso = (float(energia_actual) / objetivo_kwh) * 100
                                        print(f"[{cp_id}] Progreso: {energia_actual:.2f}/{objetivo_kwh:.2f} kWh ({progreso:.1f}%)")
                                    except Exception:
                                        pass
                        elif est in ("finalizado", "reposo", "idle", "ready"):
                            # Solo volver a ACTIVADO si no está PARADO manualmente
                            if not manual_parado:
                                cambiar_estado_cp(cp_id, 'ACTIVADO')
                    except Exception:
                        pass

                    # Reenviar actualización periódica al Driver asociado (si existe)
                    try:
                        with CP_SESION_DRIVER_ID_LOCK:
                            driver_id = CP_SESION_DRIVER_ID.get(cp_id)
                        if driver_id:
                            # Calcular importe aproximado en tiempo real
                            energia = (
                                telemetria.get('energia_total')
                                if 'energia_total' in telemetria
                                else telemetria.get('kwh', telemetria.get('kw_entregados', 0.0))
                            )
                            try:
                                energia_val = float(energia)
                            except Exception:
                                energia_val = 0.0
                            with CP_PRECIO_KWH_LOCK:
                                precio = CP_PRECIO_KWH.get(cp_id, 0.0)
                            try:
                                precio_val = float(precio)
                            except Exception:
                                precio_val = 0.0
                            importe = round(energia_val * precio_val, 2)
                            notificar_driver(driver_id, 'TELEMETRIA', {
                                'cp_id': cp_id,
                                'energia_kwh': energia_val,
                                'importe_eur': importe,
                                'estado': telemetria.get('estado') or telemetria.get('estado_carga'),
                                'potencia_kw': telemetria.get('potencia_actual'),
                                'timestamp': telemetria.get('timestamp'),
                            })
                    except Exception:
                        pass

            # Confirmar offsets tras procesar el batch para retomar desde el último confirmado
            try:
                consumer.commit()
            except Exception:
                pass
            
    except Exception as e:
        print(f"[KAFKA CONSUMER] Error crítico de consumo de Kafka: {e}")
    finally:
        if consumer:
            consumer.close()
            print("[KAFKA CONSUMER] Consumidor de telemetría cerrado.")

# =================================================================
#                    CONSUMIDOR DE DRIVER_REQUESTS
# =================================================================
            
def consumir_comandos_control_kafka(broker_list: str):
    """
    Se conecta a Kafka y consume mensajes del tópico de comandos de control (desde web dashboard).
    """
    print(f"[KAFKA CONSUMER] Iniciando consumidor para comandos de control: {CENTRAL_COMMANDS_TOPIC}")
    consumer = None
    try:
        consumer = KafkaConsumer(
            CENTRAL_COMMANDS_TOPIC,
            bootstrap_servers=[broker_list],
            security_protocol='PLAINTEXT',
            api_version=(2, 5, 0),
            auto_offset_reset='latest',
            group_id='central-control-group',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        
        print(f"[KAFKA CONSUMER] Suscrito a '{CENTRAL_COMMANDS_TOPIC}'. Esperando comandos de control...")
        
        while True:
            with SHUTDOWN_LOCK:
                if SHUTDOWN_REQUESTED:
                    print("[KAFKA CONSUMER] Apagado solicitado, cerrando consumidor de comandos de control...")
                    break
            
            records = consumer.poll(timeout_ms=1000)
            if not records:
                continue
            
            for _tp, batch in records.items():
                for message in batch:
                    comando = message.value
                    cp_id = comando.get('cp_id')
                    command = comando.get('command', '').upper()
                    source = comando.get('source', 'unknown')
                    
                    if not cp_id:
                        registrar_evento(f"[WARN] Comando sin cp_id: {comando}", "warn")
                        continue
                    
                    registrar_evento(f"[CONTROL WEB] Comando {command} para {cp_id} desde {source}")
                    print(f"[KAFKA CONSUMER] Comando recibido: {command} para {cp_id}")
                    
                    # Manejar comando especial PREPARE_SUPPLY
                    if command == 'PREPARE_SUPPLY':
                        # Obtener datos de sesión y enviar AUTH_REQ
                        with CP_SESION_DRIVER_ID_LOCK:
                            driver_id = CP_SESION_DRIVER_ID.get(cp_id)
                        with CP_SESION_OBJETIVO_KWH_LOCK:
                            kw_objetivo = CP_SESION_OBJETIVO_KWH.get(cp_id)
                        
                        if not driver_id or not kw_objetivo:
                            print(f"[CENTRAL] No hay sesión activa para {cp_id}")
                            registrar_evento(f"[ERROR] No hay sesión activa para {cp_id}", "error")
                            continue
                        
                        # Enviar AUTH_REQ al CP
                        with CONEXIONES_ACTIVAS_LOCK:
                            cp_socket = CONEXIONES_ACTIVAS.get(cp_id)
                        
                        if not cp_socket:
                            print(f"[CENTRAL] CP {cp_id} no está conectado")
                            registrar_evento(f"[ERROR] CP {cp_id} no está conectado", "error")
                            continue
                        
                        try:
                            trama_auth = construir_trama('AUTH_REQ', [driver_id, str(kw_objetivo)])
                            cp_socket.sendall(trama_auth)
                            print(f"[CENTRAL] ✓ AUTH_REQ enviado a {cp_id} (Driver: {driver_id}, kW: {kw_objetivo})")
                            registrar_evento(f"[FLUJO] AUTH_REQ enviado a {cp_id}. Esperando acción del operador del Engine.", "info")
                            
                            # Cambiar estado
                            cambiar_estado_cp(cp_id, 'ESPERANDO_OPERADOR_ENGINE')
                            
                            # Publicar telemetría actualizada
                            with TELEMETRIA_ACTUAL_LOCK:
                                telemetria_actual = TELEMETRIA_ACTUAL.get(cp_id, {})
                            telemetria_actualizada = {
                                **telemetria_actual,
                                'cp_id': cp_id,
                                'estado_carga': 'ESPERANDO_OPERADOR_ENGINE',
                                'estado': 'ESPERANDO_OPERADOR_ENGINE',
                                'timestamp': time.time(),
                                'tiene_sesion_activa': True,
                                'driver_id_sesion': driver_id
                            }
                            with TELEMETRIA_ACTUAL_LOCK:
                                TELEMETRIA_ACTUAL[cp_id] = telemetria_actualizada
                            if KAFKA_PRODUCER:
                                KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_actualizada)
                                KAFKA_PRODUCER.flush(timeout=1)
                        except Exception as e:
                            print(f"[CENTRAL] Error enviando AUTH_REQ a {cp_id}: {e}")
                            registrar_evento(f"[ERROR] Error enviando AUTH_REQ a {cp_id}: {e}", "error")
                    
                    elif command in ['START', 'STOP']:
                        # Comandos normales START/STOP
                        _enviar_comando_cp(cp_id, command)
                    else:
                        registrar_evento(f"[WARN] Comando desconocido: {command}", "warn")
            
            try:
                consumer.commit()
            except Exception:
                pass
                
    except Exception as e:
        print(f"[KAFKA CONSUMER] Error en consumidor de comandos de control: {e}")
    finally:
        if consumer:
            consumer.close()
            print("[KAFKA CONSUMER] Consumidor de comandos de control cerrado.")


def consumir_solicitudes_driver_kafka(broker_list: str, db_connection: mysql.connector.connection.MySQLConnection):
    """
    Se conecta a Kafka y consume mensajes del tópico de solicitudes de drivers.
    """
    print(f"[KAFKA CONSUMER] EV_Central iniciando consumidor para el topic: {DRIVER_REQUESTS_TOPIC}")
    consumer = None
    try:
        consumer = KafkaConsumer(
            DRIVER_REQUESTS_TOPIC,
            bootstrap_servers=[broker_list],
            security_protocol='PLAINTEXT',
            api_version=(2, 5, 0),
            auto_offset_reset='earliest',
            group_id='central_processing_group',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )

        print(f"[KAFKA CONSUMER] Suscrito a '{DRIVER_REQUESTS_TOPIC}'. Esperando solicitudes de drivers...")

        while True:
            # Verificar si se solicita el apagado
            with SHUTDOWN_LOCK:
                if SHUTDOWN_REQUESTED:
                    print("[KAFKA CONSUMER] Apagado solicitado, cerrando consumidor de driver requests...")
                    break

            records = consumer.poll(timeout_ms=1000)
            if not records:
                continue

            for _tp, batch in records.items():
                for message in batch:
                    solicitud = message.value
                    registrar_evento("Solicitud de recarga recibida")
                    print("--- NUEVA SOLICITUD RECIBIDA ---")
                    print(f"\tDriver ID: {solicitud.get('id_driver')}")
                    print(f"\tCP ID:     {solicitud.get('id_charging_point')}")
                    print(f"\tMatrícula: {solicitud.get('matricula')}")
                    print(f"\tkW Deseados: {solicitud.get('kw_deseados')} kW")
                    # Lógica de autorización: validación BD, socket al CP, notificaciones a Driver
                    try:
                        id_driver = solicitud.get('id_driver')
                        cp_id = solicitud.get('id_charging_point')
                        kw_deseados = solicitud.get('kw_deseados')

                        if not id_driver or not cp_id or kw_deseados is None:
                            print("[CENTRAL] Solicitud inválida: faltan campos obligatorios")
                            notificar_driver(id_driver or 'UNKNOWN', 'DENEGADA', {
                                'motivo': 'Solicitud inválida: faltan campos'
                            })
                            continue

                        # Paso 1: Notificar recepción
                        notificar_driver(id_driver, 'RECIBIDA', {
                            'mensaje': 'Solicitud recibida. Validando disponibilidad del CP...'
                        })

                        # Paso 2: Validar contra BD
                        if not (db_connection and db_connection.is_connected()):
                            print("[CENTRAL] BD no disponible; denegando solicitud.")
                            notificar_driver(id_driver, 'DENEGADA', {
                                'motivo': 'BD no disponible; no es posible validar CP'
                            })
                            continue

                        estado_cp = obtener_estado_cp(db_connection, cp_id)
                        if estado_cp is None:
                            print(f"[CENTRAL] CP {cp_id} no existe en BD")
                            notificar_driver(id_driver, 'DENEGADA', {
                                'motivo': f'CP {cp_id} no registrado'
                            })
                            continue

                        estado_inferior = estado_cp.strip().lower()
                        
                        # Verificar si el CP ya tiene una sesión activa
                        with CP_SESION_DRIVER_ID_LOCK:
                            tiene_sesion = cp_id in CP_SESION_DRIVER_ID and CP_SESION_DRIVER_ID[cp_id] is not None
                        
                        if tiene_sesion:
                            # CP ocupado - añadir a cola de espera
                            print(f"[CENTRAL] CP {cp_id} ocupado. Añadiendo {id_driver} a cola de espera...")
                            
                            with CP_COLA_ESPERA_LOCK:
                                if cp_id not in CP_COLA_ESPERA:
                                    from queue import Queue
                                    CP_COLA_ESPERA[cp_id] = Queue()
                                CP_COLA_ESPERA[cp_id].put((id_driver, kw_deseados, time.time()))
                            
                            # Obtener posición en la cola
                            with CP_COLA_ESPERA_LOCK:
                                posicion = CP_COLA_ESPERA[cp_id].qsize()
                            
                            notificar_driver(id_driver, 'EN_COLA', {
                                'mensaje': f'CP {cp_id} ocupado. Posición en cola: {posicion}',
                                'posicion': posicion,
                                'cp_id': cp_id
                            })
                            
                            registrar_evento(f"Driver {id_driver} en cola para {cp_id} (posición {posicion})", "info")
                            continue
                        
                        if estado_inferior in ('activado',):
                            pass
                        elif estado_inferior in ('suministrando',):
                            notificar_driver(id_driver, 'DENEGADA', {
                                'motivo': f'CP {cp_id} ocupado (Suministrando)'
                            })
                            continue
                        elif estado_inferior in ('parado', 'averiado', 'desconectado'):
                            notificar_driver(id_driver, 'DENEGADA', {
                                'motivo': f'CP {cp_id} no disponible: {estado_cp}'
                            })
                            continue
                        else:
                            notificar_driver(id_driver, 'DENEGADA', {
                                'motivo': f'Estado de CP desconocido: {estado_cp}'
                            })
                            continue

                        # Paso 3: Verificar conexión TCP con el Monitor (persistente)
                        with CONEXIONES_ACTIVAS_LOCK:
                            cp_socket = CONEXIONES_ACTIVAS.get(cp_id)

                        if not cp_socket:
                            print(f"[CENTRAL] CP {cp_id} no está conectado por socket")
                            notificar_driver(id_driver, 'DENEGADA', {
                                'motivo': f'CP {cp_id} desconectado'
                            })
                            continue

                        # Paso 4: Registrar objetivo de sesión PERO NO ENVIAR AUTH_REQ TODAVÍA
                        # Esperar a que el operador de Central de click en "Iniciar Suministro"
                        try:
                            with CP_SESION_OBJETIVO_KWH_LOCK:
                                CP_SESION_OBJETIVO_KWH[cp_id] = float(kw_deseados)
                        except Exception:
                            with CP_SESION_OBJETIVO_KWH_LOCK:
                                CP_SESION_OBJETIVO_KWH[cp_id] = kw_deseados
                        try:
                            with CP_SESION_DRIVER_ID_LOCK:
                                CP_SESION_DRIVER_ID[cp_id] = id_driver
                        except Exception:
                            pass

                        # NUEVO: Cambiar a estado PENDIENTE_CONFIRMACION_CENTRAL
                        # El operador de Central debe confirmar desde la web
                        try:
                            cambiar_estado_cp(cp_id, 'PENDIENTE_CONFIRMACION_CENTRAL', db_connection)
                        except Exception:
                            pass
                        
                        # Publicar telemetría para que aparezca botón en dashboard de Central
                        try:
                            with TELEMETRIA_ACTUAL_LOCK:
                                telemetria_actual = TELEMETRIA_ACTUAL.get(cp_id, {})
                            telemetria_actualizada = {
                                **telemetria_actual,
                                'cp_id': cp_id,
                                'estado_carga': 'PENDIENTE_CONFIRMACION_CENTRAL',
                                'estado': 'PENDIENTE_CONFIRMACION_CENTRAL',
                                'timestamp': time.time(),
                                'tiene_sesion_activa': True,
                                'driver_id_sesion': id_driver,
                                'objetivo_kwh': kw_deseados
                            }
                            with TELEMETRIA_ACTUAL_LOCK:
                                TELEMETRIA_ACTUAL[cp_id] = telemetria_actualizada
                            if KAFKA_PRODUCER:
                                KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_actualizada)
                                KAFKA_PRODUCER.flush(timeout=1)
                                print(f"[CENTRAL] Telemetría publicada para {cp_id}: PENDIENTE_CONFIRMACION_CENTRAL")
                        except Exception as e:
                            print(f"[CENTRAL] No se pudo publicar telemetría: {e}")
                        
                        # Notificar al driver que su solicitud está en espera de confirmación
                        notificar_driver(id_driver, 'EN_ESPERA_CONFIRMACION', {
                            'mensaje': f'Solicitud validada. Esperando confirmación del operador de Central.',
                            'cp_id': cp_id
                        })
                        
                        print(f"[CENTRAL] ✓ Solicitud de {id_driver} para {cp_id} registrada.")
                        print(f"[CENTRAL] ⏳ Esperando que operador de Central confirme en web dashboard...")
                        registrar_evento(f"[FLUJO] Solicitud {id_driver} → {cp_id} ({kw_deseados} kWh). Esperando confirmación de operador Central.", "info")

                    except Exception as e:
                        print(f"[CENTRAL] Error procesando solicitud del driver: {e}")
    except Exception as e:
        print(f"[KAFKA CONSUMER] ERROR al iniciar el consumidor de la Central: {e}")
        print("[KAFKA CONSUMER] Verifica la conexión a Kafka.")
    finally:
        if consumer:
            consumer.close()
            print("[KAFKA CONSUMER] Consumidor de driver requests cerrado.")

def calcular_lrc(data: bytes) -> bytes:
    """Calcula el Longitudinal Redundancy Check (XOR de todos los bytes)."""
    lrc = 0
    for byte in data:
        lrc ^= byte
    return bytes([lrc])

def construir_trama(cod_op: str, campos: list) -> bytes:
    """Construye la trama completa para enviar una respuesta (ej. AUTH)."""
    # 1. Crear el contenido DATA (Cod_Op#campo1#campo2...)
    DATA = f"{cod_op}#{DELIMITER.join(map(str, campos))}"
    
    # 2. Calcular el LRC de la DATA
    DATA_bytes = DATA.encode('utf-8')
    LRC_byte = calcular_lrc(DATA_bytes)
    
    # 3. Ensamblar la trama: STX + DATA (en bytes) + ETX + LRC
    trama = STX + DATA_bytes + ETX + LRC_byte
    return trama

def descomponer_trama(trama_bytes: bytes) -> tuple:
    """
    Descompone, valida y parsea la trama recibida del CP.
    Retorna (Cod_Op, campos) o (None, None) si falla la validación.
    """
    
    # La trama completa debe tener al menos STX (1) + DATA (mín 1) + ETX (1) + LRC (1) = 4 bytes
    if len(trama_bytes) < 4:
         print(f"[CENTRAL] Error: Trama demasiado corta ({len(trama_bytes)} bytes).")
         return None, None
    
    # El LRC es el ÚLTIMO byte de la trama
    lrc_recibido = trama_bytes[-1:] 
    
    # El cuerpo completo (DATA + ETX) está entre STX (byte 1) y el LRC (el último)
    data_con_etx = trama_bytes[1:-1]
    
    # La DATA (a la que se le calcula el LRC) es todo el cuerpo MENOS el ETX
    data_bytes = data_con_etx[:-1]
    
    # 1. Verificar formato (STX/ETX)
    # Trama debe empezar con STX y el byte ANTES del LRC debe ser ETX
    if not (trama_bytes.startswith(STX) and data_con_etx.endswith(ETX)):
        # Ahora verificamos que el byte antes del LRC es ETX
        print("[CENTRAL] Error: Formato de trama incorrecto (STX/ETX faltantes).")
        return None, None
        
    # 2. Verificar LRC
    lrc_calculado = calcular_lrc(data_bytes)
    if lrc_recibido != lrc_calculado:
        print(f"[CENTRAL] Error LRC. Recibido: {lrc_recibido.hex()}, Calculado: {lrc_calculado.hex()}. Trama descartada.")
        return None, None
        
    # 3. Decodificar y parsear DATA
    try:
        DATA = data_bytes.decode('utf-8')
        partes = DATA.split(DELIMITER)
        
        cod_op = partes[0]
        campos = partes[1:]
        
        return cod_op, campos
    except UnicodeDecodeError:
        print("[CENTRAL] Error: No se pudo decodificar la DATA.")
        return None, None

# =================================================================
#                      FUNCIONES DE BASE DE DATOS
# =================================================================

def conectar_bd(db_config: str) -> mysql.connector.connection.MySQLConnection:
    """Establece conexión con la base de datos MySQL."""
    try:
        # Parsear la configuración de BD (formato: host:port:user:password:database)
        if not db_config:
            raise ValueError("Configuración de BD no proporcionada")
        
        parts = db_config.split(':')
        if len(parts) != 5:
            raise ValueError("Formato de BD incorrecto. Use: host:port:user:password:database")
        
        host, port, user, password, database = parts
        
        connection = mysql.connector.connect(
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=database,
            autocommit=True,
            charset='utf8mb4',
            collation='utf8mb4_general_ci'
        )
        
        if connection.is_connected():
            print(f"[CENTRAL] Conectado a MySQL en {host}:{port}")
            return connection
            
    except Error as e:
        print(f"[CENTRAL] Error conectando a MySQL: {e}")
        raise
    except Exception as e:
        print(f"[CENTRAL] Error inesperado en conexión BD: {e}")
        raise

def registrar_cp_en_bd(connection: mysql.connector.connection.MySQLConnection, 
                       cp_id: str, ubicacion: str, precio_kwh: float) -> bool:
    """Registra o actualiza un CP en la base de datos y lo marca como Activado."""
    try:
        cursor = connection.cursor()
        
        # Verificar si el CP ya existe
        cursor.execute("SELECT id, estado FROM charging_points WHERE cp_id = %s", (cp_id,))
        result = cursor.fetchone()
        
        if result:
            # CP existe, actualizar estado y fecha de conexión
            cp_db_id, estado_actual = result
            cursor.execute("""
                UPDATE charging_points 
                SET estado = 'Activado', fecha_ultima_conexion = %s 
                WHERE cp_id = %s
            """, (datetime.now(), cp_id))
            print(f"[CENTRAL] CP {cp_id} actualizado en BD. Estado anterior: {estado_actual} -> Activado")
        else:
            # CP nuevo, insertar
            cursor.execute("""
                INSERT INTO charging_points (cp_id, ubicacion, precio_kwh, estado, fecha_ultima_conexion)
                VALUES (%s, %s, %s, 'Activado', %s)
            """, (cp_id, ubicacion, precio_kwh, datetime.now()))
            print(f"[CENTRAL] CP {cp_id} registrado en BD como nuevo")
        
        cursor.close()
        return True
        
    except Error as e:
        print(f"[CENTRAL] Error en BD al registrar CP {cp_id}: {e}")
        return False
    except Exception as e:
        print(f"[CENTRAL] Error inesperado al registrar CP {cp_id}: {e}")
        return False

def actualizar_estado_cp(connection: mysql.connector.connection.MySQLConnection, 
                         cp_id: str, nuevo_estado: str) -> bool:
    """Actualiza el estado de un CP en la base de datos."""
    try:
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE charging_points 
            SET estado = %s, fecha_ultima_conexion = %s 
            WHERE cp_id = %s
        """, (nuevo_estado, datetime.now(), cp_id))
        
        if cursor.rowcount > 0:
            print(f"[CENTRAL] Estado de CP {cp_id} actualizado a: {nuevo_estado}")
            cursor.close()
            return True
        else:
            print(f"[CENTRAL] CP {cp_id} no encontrado en BD para actualizar estado")
            cursor.close()
            return False
            
    except Error as e:
        print(f"[CENTRAL] Error actualizando estado de CP {cp_id}: {e}")
        return False
    except Exception as e:
        print(f"[CENTRAL] Error inesperado actualizando estado de CP {cp_id}: {e}")
        return False

def obtener_estado_cp(connection: mysql.connector.connection.MySQLConnection, cp_id: str):
    """Obtiene el estado actual del CP desde la BD. Devuelve str o None si no existe."""
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT estado FROM charging_points WHERE cp_id = %s", (cp_id,))
        result = cursor.fetchone()
        cursor.close()
        if result:
            return result[0]
        return None
    except Error as e:
        print(f"[CENTRAL] Error consultando estado de CP {cp_id}: {e}")
        return None
    except Exception as e:
        print(f"[CENTRAL] Error inesperado consultando estado de CP {cp_id}: {e}")
        return None

# =================================================================
#                      FUNCIONES DE NOTIFICACIÓN (Kafka)
# =================================================================

def inicializar_kafka_producer(broker_list: str):
    global KAFKA_PRODUCER
    with KAFKA_PRODUCER_LOCK:
        if KAFKA_PRODUCER is None:
            try:
                KAFKA_PRODUCER = KafkaProducer(
                    bootstrap_servers=[broker_list],
                    security_protocol='PLAINTEXT',
                    api_version=(2, 5, 0),
                    value_serializer=lambda v: json.dumps(v).encode('utf-8')
                )
                print("[KAFKA PRODUCER] Productor inicializado para notificaciones a drivers.")
            except Exception as e:
                print(f"[KAFKA PRODUCER] ERROR al inicializar productor: {e}")
                KAFKA_PRODUCER = None
    return KAFKA_PRODUCER

def notificar_driver(id_driver: str, evento: str, detalle=None):
    """Envía un mensaje al tópico específico del driver: driver_status_<ID>."""
    if not id_driver:
        return
    try:
        payload = {
            'driver_id': id_driver,
            'evento': evento,
            'detalle': detalle,
            'timestamp': datetime.now().isoformat()
        }
        topic = f"driver_status_{id_driver}"
        if KAFKA_PRODUCER is None:
            print("[KAFKA PRODUCER] No disponible. No se puede notificar al driver.")
            return
        KAFKA_PRODUCER.send(topic, value=payload)
        # Se puede forzar flush si se requiere entrega inmediata
        KAFKA_PRODUCER.flush(timeout=2)
        print(f"[CENTRAL] Notificación enviada a {topic}: {evento}")
    except Exception as e:
        print(f"[CENTRAL] Error notificando al driver {id_driver}: {e}")

# =================================================================
#                       LÓGICA DEL SERVIDOR CENTRAL
# =================================================================

def monitorizar_actividad_cps(db_connection):
    """Monitoriza la actividad de los CPs y publica heartbeats periódicos."""
    contador_heartbeat = 0
    while not SHUTDOWN_REQUESTED:
        ahora = time.time()
        try:
            # Verificar CPs sin actividad
            with TELEMETRIA_ACTUAL_LOCK:
                for cp_id, data in list(TELEMETRIA_ACTUAL.items()):
                    ultima = data.get("timestamp", 0)
                    if ahora - ultima > 15:
                        # No desconectar si está en avería activa
                        with CP_ALERTA_LOCK:
                            alerta = CP_ALERTA.get(cp_id, False)
                        if alerta:
                            continue
                        if CP_ESTADO.get(cp_id) != "DESCONECTADO":
                            registrar_evento(f"[⚠️] CP {cp_id} sin actividad → DESCONECTADO", "warn")
                            cambiar_estado_cp(cp_id, "DESCONECTADO", db_connection)
            
            # Publicar heartbeat cada 10 segundos (cada 2 ciclos de 5s)
            contador_heartbeat += 1
            if contador_heartbeat >= 2:
                contador_heartbeat = 0
                publicar_heartbeat_cps()
                
        except Exception as e:
            registrar_evento(f"[WARN] Monitor error: {e}", "warn")
        time.sleep(5)


def publicar_heartbeat_cps():
    """Publica el estado actual de todos los CPs conectados para que el dashboard lo detecte."""
    try:
        with CONEXIONES_ACTIVAS_LOCK:
            cps_conectados = list(CONEXIONES_ACTIVAS.keys())
        
        if not cps_conectados:
            return
        
        print(f"[CENTRAL] 💓 Publicando heartbeat para {len(cps_conectados)} CP(s) conectados...")
        
        for cp_id in cps_conectados:
            try:
                # Obtener telemetría actual o crear una básica
                with TELEMETRIA_ACTUAL_LOCK:
                    telemetria = TELEMETRIA_ACTUAL.get(cp_id, {})
                
                # Asegurar que tenga los campos mínimos
                if not telemetria or 'timestamp' not in telemetria:
                    with CP_ESTADO_LOCK:
                        estado = CP_ESTADO.get(cp_id, 'ACTIVADO')
                    with CP_PRECIO_KWH_LOCK:
                        precio = CP_PRECIO_KWH.get(cp_id, 0.0)
                    
                    telemetria = {
                        'cp_id': cp_id,
                        'estado_carga': estado,
                        'estado': estado,
                        'potencia_actual': 0.0,
                        'energia_total': 0.0,
                        'kw_entregados': 0.0,
                        'tiempo_carga_s': 0,
                        'timestamp': time.time(),
                        'precio_kwh': precio,
                        'tiene_sesion_activa': False,
                        'driver_id_sesion': None
                    }
                else:
                    # Actualizar timestamp del heartbeat
                    telemetria = {**telemetria, 'timestamp': time.time()}
                
                # Enriquecer con información de sesión
                with CP_SESION_DRIVER_ID_LOCK:
                    telemetria['tiene_sesion_activa'] = cp_id in CP_SESION_DRIVER_ID
                    telemetria['driver_id_sesion'] = CP_SESION_DRIVER_ID.get(cp_id, None)
                
                # Publicar en Kafka
                if KAFKA_PRODUCER:
                    KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria)
                    print(f"[CENTRAL]   → {cp_id}: {telemetria.get('estado', 'N/D')}")
                
            except Exception as e:
                print(f"[CENTRAL] ✗ Error publicando heartbeat de {cp_id}: {e}")
        
        # Flush para asegurar envío
        if KAFKA_PRODUCER:
            KAFKA_PRODUCER.flush(timeout=1)
            print(f"[CENTRAL] ✓ Heartbeat enviado correctamente a Kafka")
            
    except Exception as e:
        print(f"[CENTRAL] ✗ Error en publicar_heartbeat_cps: {e}")
        import traceback
        traceback.print_exc()
def mostrar_estado_red():
    """Compat: imprime estado (modo no-TUI); preservado por si se usa sin Rich."""
    print("\n" + "="*60)
    print(f"| ESTADO DE LA RED DE CARGA (Total: {len(CONEXIONES_ACTIVAS)} CP(s) Activos) |")
    print("="*60)
    if not CONEXIONES_ACTIVAS:
        print(">> No hay Puntos de Carga conectados actualmente.")
        print("="*60)
        return
    for cp_id, socket_obj in CONEXIONES_ACTIVAS.items():
        print(f"| CP ID: {cp_id}")
        print(f"|   Socket: Conectado en {socket_obj.getsockname()[1]}")
        # Mostrar estado consolidado conocido por la Central
        with CP_ESTADO_LOCK:
            estado_central = CP_ESTADO.get(cp_id, 'DESCONOCIDO')
        if estado_central == 'PARADO':
            print(f"|   Estado: PARADO  (Out of Order)")
        with TELEMETRIA_ACTUAL_LOCK:
            telemetria = TELEMETRIA_ACTUAL.get(cp_id)
        if telemetria:
            estado = telemetria.get('estado', 'DESCONOCIDO')
            potencia_actual = telemetria.get('potencia_actual', 'N/A')
            energia_total = telemetria.get('energia_total', 'N/A')
            timestamp = telemetria.get('timestamp', 'N/A')
            print(f"|   Estado: {estado}")
            print(f"|   Potencia Actual: {potencia_actual} kW")
            print(f"|   Energía Total: {energia_total} kWh")
            print(f"|   Última Actualización: {timestamp}")
            try:
                with CP_SESION_OBJETIVO_KWH_LOCK:
                    obj = CP_SESION_OBJETIVO_KWH.get(cp_id)
                if obj is not None:
                    print(f"|   Objetivo: {float(obj):.2f} kWh")
            except Exception:
                pass
        else:
            print(f"|   Estado: Sin telemetría disponible")
            print(f"|   (Conectado pero sin datos de Kafka)")
        print("-"*60)

def interfaz_consola_central():
    """Deprecado por TUI Rich. Mantener por compatibilidad si TUI no está disponible."""
    registrar_evento("Modo consola simple activado")
    while True:
        comando = input("\n[CENTRAL CMD] (ej.: 2 START CP001 | 3=salir) > ").strip()
        if not comando:
            continue
        COMMAND_QUEUE.put(comando)
        time.sleep(0.1)

def render_panel():
    table = Table(title="🚗 ESTADO CENTRAL DE CARGA", box=box.ROUNDED)
    table.add_column("CP ID", justify="center", style="bold white")
    table.add_column("Estado", justify="center")
    table.add_column("Energía (kWh)", justify="center")
    table.add_column("Última actualización", justify="center")

    with TELEMETRIA_ACTUAL_LOCK:
        for cp_id, data in TELEMETRIA_ACTUAL.items():
            estado = CP_ESTADO.get(cp_id, "N/D")
            energia = data.get("kw_entregados") or data.get("energia_total") or 0.0
            t_ago = round(time.time() - data.get("timestamp", 0), 1)
            color = {
                "ACTIVADO": "green",
                "SUMINISTRANDO": "cyan",
                "DESCONECTADO": "red",
                "AVERÍA": "magenta"
            }.get(str(estado).upper(), "white")
            table.add_row(cp_id, f"[{color}]{estado}[/{color}]", f"{float(energia):.2f}", f"{t_ago}s")
    return table

def iniciar_interfaz_visual():
    with Live(render_panel(), refresh_per_second=1, console=console) as live:
        while not SHUTDOWN_REQUESTED:
            live.update(render_panel())
            time.sleep(2)
            
def manejar_cliente(conn: socket.socket, addr: tuple, db_connection: mysql.connector.connection.MySQLConnection):
    """Función ejecutada por un hilo para manejar la conexión de un CP."""
    
    print(f"[CENTRAL] Conexión establecida con {addr[0]}:{addr[1]}")
    cp_id = "Desconocido"
    
    try:
        # Establecer timeout para permitir cierre limpio
        conn.settimeout(1.0)

        # --- 1. REGISTRO Y AUTENTICACIÓN (Primer intercambio) ---
        trama_bytes = b''
        while True:
            # Verificar si se solicita el apagado antes de bloquear
            with SHUTDOWN_LOCK:
                if SHUTDOWN_REQUESTED:
                    print(f"[CENTRAL] Apagado solicitado antes de registro, cerrando conexión con {addr[0]}:{addr[1]}...")
                    return
            try:
                trama_bytes = conn.recv(1024)
            except socket.timeout:
                continue
            if not trama_bytes:
                raise ConnectionResetError("Conexión cerrada por el cliente antes del registro.")
            break

        cod_op, campos = descomponer_trama(trama_bytes)

        if cod_op == 'REG' and len(campos) >= 3:
            cp_id = campos[0]
            ubicacion = campos[1]
            precio_kwh = float(campos[2])

            # ====== NUEVO BLOQUE AÑADIDO: DETECCIÓN DE RECONEXIÓN ======
            with CONEXIONES_ACTIVAS_LOCK:
                ya_conectado = cp_id in CONEXIONES_ACTIVAS

            if ya_conectado:
                registrar_evento(f"[RECONEXIÓN] CP {cp_id} se ha reconectado correctamente.")
                try:
                    cambiar_estado_cp(cp_id, 'ACTIVADO', db_connection)
                except Exception:
                    pass
            else:
                registrar_evento(f"[NUEVO CP] Registro inicial de {cp_id}.")
            registrar_evento(f"CP registrado y conectado: {cp_id} ({ubicacion})")
            # Estado: ACTIVADO tras registro exitoso
            try:
                cambiar_estado_cp(cp_id, 'ACTIVADO', db_connection)
            except Exception:
                pass
            # Guardar el precio comunicado por el CP para cálculos de importe en tiempo real
            try:
                with CP_PRECIO_KWH_LOCK:
                    CP_PRECIO_KWH[cp_id] = precio_kwh
            except Exception:
                pass
            
            # --- PUBLICAR ESTADO INICIAL EN KAFKA PARA QUE EL DASHBOARD LO DETECTE ---
            try:
                telemetria_inicial = {
                    'cp_id': cp_id,
                    'estado_carga': 'ACTIVADO',
                    'estado': 'ACTIVADO',
                    'potencia_actual': 0.0,
                    'energia_total': 0.0,
                    'kw_entregados': 0.0,
                    'tiempo_carga_s': 0,
                    'timestamp': time.time(),
                    'ubicacion': ubicacion,
                    'precio_kwh': precio_kwh,
                    'tiene_sesion_activa': False,
                    'driver_id_sesion': None
                }
                with TELEMETRIA_ACTUAL_LOCK:
                    TELEMETRIA_ACTUAL[cp_id] = telemetria_inicial
                
                if KAFKA_PRODUCER is None:
                    print(f"[CENTRAL] ✗ ADVERTENCIA: Productor Kafka no disponible, no se puede publicar telemetría de {cp_id}")
                else:
                    print(f"[CENTRAL] → Publicando telemetría inicial de {cp_id} en topic '{TELEMETRIA_TOPIC}'...")
                    future = KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_inicial)
                    KAFKA_PRODUCER.flush(timeout=2)
                    print(f"[CENTRAL] ✓ Telemetría inicial de {cp_id} publicada correctamente en Kafka")
                    registrar_evento(f"Telemetría inicial publicada para {cp_id}", "ok")
            except Exception as e:
                print(f"[CENTRAL] ✗ ERROR publicando telemetría inicial de {cp_id}: {e}")
                import traceback
                traceback.print_exc()
            
            # --- LÓGICA BD: Insertar/Actualizar CP y marcar como ACTIVADO ---
            if db_connection and db_connection.is_connected():
                if registrar_cp_en_bd(db_connection, cp_id, ubicacion, precio_kwh):
                    respuesta_trama = construir_trama('AUTH', ['OK', 'Autenticacion exitosa'])
                    conn.sendall(respuesta_trama)
                    print(f"[CENTRAL] <- Enviada respuesta AUTH: OK a {cp_id}")
                    registrar_evento(f"AUTH OK enviado a {cp_id}")
                else:
                    # Error en BD, rechazar conexión
                    respuesta_trama = construir_trama('AUTH', ['FAIL', 'Error en base de datos'])
                    conn.sendall(respuesta_trama)
                    print(f"[CENTRAL] <- Enviada respuesta AUTH: FAIL a {cp_id} (Error BD)")
                    return
            else:
                # Sin BD, aceptar conexión pero advertir
                print(f"[CENTRAL] ADVERTENCIA: Sin conexión a BD, aceptando {cp_id} sin persistencia")
                respuesta_trama = construir_trama('AUTH', ['OK', 'Autenticacion exitosa (sin BD)'])
                conn.sendall(respuesta_trama)
                print(f"[CENTRAL] <- Enviada respuesta AUTH: OK a {cp_id} (sin BD)")
                registrar_evento(f"AUTH OK enviado a {cp_id} (sin BD)")
            
            # --- ALMACENAR CONEXIÓN SOLO DESPUÉS DE COMPLETAR AUTENTICACIÓN ---
            with CONEXIONES_ACTIVAS_LOCK:
                CONEXIONES_ACTIVAS[cp_id] = conn
                print(f"[CENTRAL] Socket de {cp_id} guardado. Total: {len(CONEXIONES_ACTIVAS)}")

        else:
            print(f"[CENTRAL] Error: Mensaje inicial no válido ({cod_op}). Cerrando conexión.")
            return # Sale de la función y va al finally

        # --- 2. BUCLE DE COMUNICACIÓN PERMANENTE ---
        print(f"[CENTRAL] Hilo {cp_id} iniciando bucle de escucha permanente.")
        while True:
            # Verificar si se solicita el apagado
            with SHUTDOWN_LOCK:
                if SHUTDOWN_REQUESTED:
                    print(f"[CENTRAL] Apagado solicitado, cerrando conexión con {cp_id}...")
                    break
            
            # Ahora el hilo espera por comandos síncronos (AVR, telemetría síncrona, etc.)
            try:
                trama_bytes = conn.recv(1024)
            except socket.timeout:
                continue
            if not trama_bytes:
                # El CP cerró la conexión
                print(f"[CENTRAL] Conexión con CP {cp_id} cerrada por el cliente.")
                break 
                
            cod_op, campos = descomponer_trama(trama_bytes)
            
            if cod_op:
                print(f"[CENTRAL] Recibida trama de {cp_id}: Cod={cod_op}, Campos={campos}")
                # Manejo de tramas específicas desde el CP
                if cod_op == 'AUTH_RESP' and len(campos) >= 2:
                    # Esperado: AUTH_RESP#<driver_id>#<OK|KO>#<mensaje?>
                    try:
                        driver_id = campos[0]
                        resultado = campos[1].upper()
                        mensaje = campos[2] if len(campos) >= 3 else ''
                        if resultado == 'OK':
                            registrar_evento(f"[CONTROL] Confirmación síncrona de {cp_id}: AUTH_ACK#OK.")
                            # DEPRECADO: NO notificar "AUTORIZADO" aquí - se notificará tras confirmar inicio
                            # El driver debe esperar a que el operador del Engine inicie el suministro
                            print(f"[CENTRAL] {cp_id} confirmó AUTH_REQ. Esperando acción del operador del Engine...")
                            # NO cambiar estado aquí - mantener ESPERANDO_OPERADOR_ENGINE que se puso al enviar AUTH_REQ
                        else:
                            registrar_evento(f"[CONTROL] Confirmación síncrona de {cp_id}: AUTH_ACK#KO ({mensaje}).")
                            notificar_driver(driver_id, 'DENEGADO', {
                                'cp_id': cp_id,
                                'motivo': mensaje or 'CP denegó la autorización'
                            })
                            # Volver a ACTIVADO si denegado
                            try:
                                cambiar_estado_cp(cp_id, 'ACTIVADO', db_connection)
                            except Exception:
                                pass
                    except Exception as e:
                        print(f"[CENTRAL] Error procesando AUTH_RESP: {e}")
                
                # ====== NUEVO BLOQUE AÑADIDO: MANEJO DE FIN ====== 
                elif cod_op == 'FIN' and len(campos) >= 4:
                    # FIN puede traer campos extra: [cp_id, driver_id, energia, importe, dur_s?, motivo?, tx_id?]
                    cp_fin = campos[0]
                    driver_id = campos[1]
                    energia = campos[2]
                    importe = campos[3]
                    dur_s = campos[4] if len(campos) > 4 else None
                    motivo = campos[5] if len(campos) > 5 else 'Consumo completado'
                    tx_id = campos[6] if len(campos) > 6 else None

                    registrar_evento(f"[CONTROL] Fin de carga recibido de {cp_fin}: {energia} kWh, {importe} €")

                    detalle_ticket = {
                        'cp_id': cp_fin,
                        'energia_kwh': energia,
                        'importe_eur': importe,
                    }
                    if dur_s is not None:
                        detalle_ticket['duracion_seg'] = dur_s
                    if motivo is not None:
                        detalle_ticket['motivo'] = motivo
                    if tx_id is not None:
                        detalle_ticket['tx_id'] = tx_id

                    # Enviar ticket al driver ANTES de limpiar sesión
                    notificar_driver(driver_id, 'TICKET_FINAL', detalle_ticket)
                    
                    print(f"[CENTRAL] ✅ Ticket enviado a {driver_id}. CP {cp_fin} listo para nuevo servicio.")
                    registrar_evento(f"✅ Ticket enviado a {driver_id}: {energia} kWh, {importe} €", "ok")

                    # Limpiar sesión actual ANTES de procesar la cola
                    with CP_SESION_DRIVER_ID_LOCK:
                        if cp_fin in CP_SESION_DRIVER_ID:
                            del CP_SESION_DRIVER_ID[cp_fin]
                            print(f"[CENTRAL] Sesión de {driver_id} en {cp_fin} limpiada")
                    with CP_SESION_OBJETIVO_KWH_LOCK:
                        if cp_fin in CP_SESION_OBJETIVO_KWH:
                            del CP_SESION_OBJETIVO_KWH[cp_fin]
                    
                    # Procesar siguiente driver en cola si existe
                    cola_procesada = False
                    try:
                        with CP_COLA_ESPERA_LOCK:
                            if cp_fin in CP_COLA_ESPERA and not CP_COLA_ESPERA[cp_fin].empty():
                                from queue import Empty
                                try:
                                    next_driver, next_kw, timestamp_cola = CP_COLA_ESPERA[cp_fin].get_nowait()
                                    print(f"[CENTRAL] 🔄 Procesando siguiente en cola: {next_driver} para {cp_fin}")
                                    cola_procesada = True
                                    
                                    # Autorizar al siguiente driver
                                    with CP_SESION_DRIVER_ID_LOCK:
                                        CP_SESION_DRIVER_ID[cp_fin] = next_driver
                                    with CP_SESION_OBJETIVO_KWH_LOCK:
                                        CP_SESION_OBJETIVO_KWH[cp_fin] = next_kw
                                    
                                    # NO enviar AUTH_REQ aún: seguir el flujo interactivo.
                                    # Estado: PENDIENTE_CONFIRMACION_CENTRAL para que Central pulse "PREPARAR SUMINISTRO"
                                    try:
                                        cambiar_estado_cp(cp_fin, 'PENDIENTE_CONFIRMACION_CENTRAL', db_connection)
                                    except Exception:
                                        pass

                                    # Publicar telemetría para que aparezca el botón en el dashboard
                                    try:
                                        with TELEMETRIA_ACTUAL_LOCK:
                                            telemetria_actual = TELEMETRIA_ACTUAL.get(cp_fin, {})
                                        telemetria_actualizada = {
                                            **telemetria_actual,
                                            'cp_id': cp_fin,
                                            'estado_carga': 'PENDIENTE_CONFIRMACION_CENTRAL',
                                            'estado': 'PENDIENTE_CONFIRMACION_CENTRAL',
                                            'timestamp': time.time(),
                                            'tiene_sesion_activa': True,
                                            'driver_id_sesion': next_driver,
                                            'objetivo_kwh': next_kw
                                        }
                                        with TELEMETRIA_ACTUAL_LOCK:
                                            TELEMETRIA_ACTUAL[cp_fin] = telemetria_actualizada
                                        if KAFKA_PRODUCER:
                                            KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_actualizada)
                                            KAFKA_PRODUCER.flush(timeout=1)
                                    except Exception as e:
                                        print(f"[CENTRAL] No se pudo publicar telemetría (cola→pendiente): {e}")

                                    # Notificar al driver que su turno está pendiente de confirmación de Central
                                    notificar_driver(next_driver, 'EN_ESPERA_CONFIRMACION', {
                                        'mensaje': f'Solicitud en cola ahora pendiente de confirmación del operador de Central.',
                                        'cp_id': cp_fin,
                                        'kw_disponibles': next_kw
                                    })
                                    print(f"[CENTRAL] ✅ Driver {next_driver} notificado: EN_ESPERA_CONFIRMACION")

                                    registrar_evento(f"✅ Driver {next_driver} pasado de cola a pendiente de confirmación en {cp_fin}", "ok")
                                    
                                except Empty:
                                    pass
                    except Exception as e:
                        print(f"[CENTRAL] ✗ Error procesando cola de {cp_fin}: {e}")
                    
                    # Solo cambiar a ACTIVADO si NO se procesó nadie de la cola
                    if not cola_procesada:
                        cambiar_estado_cp(cp_fin, 'ACTIVADO', db_connection)
                        print(f"[CENTRAL] {cp_fin} sin cola pendiente. Estado: ACTIVADO")
                    
                    # Limpiar estado manual si estaba PARADO
                    try:
                        with CP_ESTADO_MANUAL_LOCK:
                            if cp_fin in CP_ESTADO_MANUAL:
                                del CP_ESTADO_MANUAL[cp_fin]
                    except Exception:
                        pass
                    
                    # Limpezas y publicación ACTIVADO solo si NO hay siguiente en cola
                    if not cola_procesada:
                        # Limpiar información de sesión del driver
                        try:
                            with CP_SESION_OBJETIVO_KWH_LOCK:
                                if cp_fin in CP_SESION_OBJETIVO_KWH:
                                    del CP_SESION_OBJETIVO_KWH[cp_fin]
                        except Exception:
                            pass
                        try:
                            with CP_SESION_DRIVER_ID_LOCK:
                                if cp_fin in CP_SESION_DRIVER_ID:
                                    del CP_SESION_DRIVER_ID[cp_fin]
                        except Exception:
                            pass
                        
                        # Publicar telemetría actualizada: CP en ACTIVADO, sin sesión, contadores en 0
                        try:
                            with TELEMETRIA_ACTUAL_LOCK:
                                telemetria_actual = TELEMETRIA_ACTUAL.get(cp_fin, {})
                            telemetria_actualizada = {
                                **telemetria_actual,
                                'cp_id': cp_fin,
                                'estado_carga': 'ACTIVADO',
                                'estado': 'ACTIVADO',
                                'timestamp': time.time(),
                                'tiene_sesion_activa': False,
                                'driver_id_sesion': None,
                                'kw_entregados': 0.0,
                                'potencia_actual': 0.0,
                                'tiempo_carga_s': 0
                            }
                            with TELEMETRIA_ACTUAL_LOCK:
                                TELEMETRIA_ACTUAL[cp_fin] = telemetria_actualizada
                            if KAFKA_PRODUCER:
                                KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_actualizada)
                                KAFKA_PRODUCER.flush(timeout=1)
                                print(f"[CENTRAL] CP {cp_fin} resetado y listo para nuevo servicio (ACTIVADO)")
                        except Exception as e:
                            print(f"[CENTRAL] Error publicando estado tras FIN: {e}")

                # NUEVO: Manejar READY_TO_START desde Monitor/Engine
                elif cod_op == 'READY_TO_START' and len(campos) >= 2:
                    try:
                        engine_cp_id = campos[0]
                        driver_id = campos[1]
                        print(f"[CENTRAL] 📩 READY_TO_START recibido de {engine_cp_id} (Driver: {driver_id})")
                        registrar_evento(f"[FLUJO] {engine_cp_id} listo para iniciar. Driver: {driver_id}. Esperando confirmación del operador de Central.", "info")
                        
                        # AHORA SÍ notificar al driver como AUTORIZADO (el Engine está listo)
                        notificar_driver(driver_id, 'AUTORIZADO', {
                            'cp_id': engine_cp_id,
                            'mensaje': 'CP listo para iniciar. Esperando confirmación final de Central.'
                        })
                        
                        # Marcar CP como pendiente de confirmación
                        with CP_PENDIENTE_CONFIRMACION_LOCK:
                            CP_PENDIENTE_CONFIRMACION[engine_cp_id] = 'LISTO_PARA_INICIAR'
                        
                        # Cambiar estado en BD y telemetría
                        try:
                            cambiar_estado_cp(engine_cp_id, 'LISTO_PARA_INICIAR', db_connection)
                        except Exception:
                            pass
                        
                        # Publicar telemetría actualizada
                        try:
                            with TELEMETRIA_ACTUAL_LOCK:
                                telemetria_actual = TELEMETRIA_ACTUAL.get(engine_cp_id, {})
                            telemetria_actualizada = {
                                **telemetria_actual,
                                'cp_id': engine_cp_id,
                                'estado_carga': 'LISTO_PARA_INICIAR',
                                'estado': 'LISTO_PARA_INICIAR',
                                'timestamp': time.time(),
                                'tiene_sesion_activa': True,
                                'driver_id_sesion': driver_id
                            }
                            with TELEMETRIA_ACTUAL_LOCK:
                                TELEMETRIA_ACTUAL[engine_cp_id] = telemetria_actualizada
                            if KAFKA_PRODUCER:
                                KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_actualizada)
                                KAFKA_PRODUCER.flush(timeout=1)
                        except Exception as e:
                            print(f"[CENTRAL] Error publicando telemetría: {e}")
                        
                    except Exception as e:
                        print(f"[CENTRAL] Error procesando READY_TO_START: {e}")
                
                # NUEVO: Manejar REQUEST_STOP desde Monitor/Engine
                elif cod_op == 'REQUEST_STOP' and len(campos) >= 4:
                    try:
                        engine_cp_id = campos[0]
                        driver_id = campos[1]
                        kw_actual = campos[2]
                        segundos = campos[3]
                        print(f"[CENTRAL] 📩 REQUEST_STOP recibido de {engine_cp_id} (Driver: {driver_id}, {kw_actual} kWh)")
                        registrar_evento(f"[FLUJO] {engine_cp_id} solicita fin. Driver: {driver_id}, {kw_actual} kWh. Esperando confirmación del operador de Central.", "info")
                        
                        # Marcar CP como pendiente de confirmación de fin
                        with CP_PENDIENTE_CONFIRMACION_LOCK:
                            CP_PENDIENTE_CONFIRMACION[engine_cp_id] = 'ESPERANDO_CONFIRMACION_FIN'
                        
                        # Cambiar estado en BD y telemetría
                        try:
                            cambiar_estado_cp(engine_cp_id, 'ESPERANDO_CONFIRMACION_FIN', db_connection)
                        except Exception:
                            pass
                        
                        # Publicar telemetría actualizada
                        try:
                            with TELEMETRIA_ACTUAL_LOCK:
                                telemetria_actual = TELEMETRIA_ACTUAL.get(engine_cp_id, {})
                            telemetria_actualizada = {
                                **telemetria_actual,
                                'cp_id': engine_cp_id,
                                'estado_carga': 'ESPERANDO_CONFIRMACION_FIN',
                                'estado': 'ESPERANDO_CONFIRMACION_FIN',
                                'timestamp': time.time(),
                                'kw_entregados': float(kw_actual),
                                'tiempo_carga_s': int(segundos)
                            }
                            with TELEMETRIA_ACTUAL_LOCK:
                                TELEMETRIA_ACTUAL[engine_cp_id] = telemetria_actualizada
                            if KAFKA_PRODUCER:
                                KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_actualizada)
                                KAFKA_PRODUCER.flush(timeout=1)
                        except Exception as e:
                            print(f"[CENTRAL] Error publicando telemetría: {e}")
                        
                    except Exception as e:
                        print(f"[CENTRAL] Error procesando REQUEST_STOP: {e}")
                
                # [Lógica para manejar AVR, Suministro síncrono, etc.]
                elif cod_op == 'AVR' and len(campos) >= 2:
                    try:
                        motivo = campos[0]
                        codigo = campos[1]
                        with CP_ALERTA_LOCK:
                            CP_ALERTA[cp_id] = True
                        registrar_evento(f"⚠️ Avería reportada por {cp_id}: {motivo} ({codigo})")
                        try:
                            cambiar_estado_cp(cp_id, 'AVERÍA', db_connection, motivo=f"{motivo} ({codigo})")
                        except Exception:
                            pass
                    except Exception:
                        registrar_evento(f"⚠️ Avería reportada por {cp_id}")
                
                elif cod_op == 'AVR_CLR':
                    try:
                        motivo = campos[1] if len(campos) > 1 else 'RECUPERADA'
                        with CP_ALERTA_LOCK:
                            CP_ALERTA[cp_id] = False
                        cambiar_estado_cp(cp_id, 'ACTIVADO', db_connection, motivo=motivo)
                        registrar_evento(f"✅ {cp_id} recuperado de avería: {motivo}")
                        print(f"[CENTRAL] {cp_id} marcado como ACTIVADO tras AVR_CLR")
                    except Exception as e:
                        print(f"[CENTRAL] Error procesando AVR_CLR: {e}")
                
                # ====== NUEVO BLOQUE AÑADIDO: MANEJO DE STATE ====== 
                elif cod_op == 'STATE' and len(campos) >= 2:
                    cp_state = campos[0]
                    nuevo_estado = campos[1]
                    registrar_evento(f"[CONTROL] Estado reportado por {cp_state}: {nuevo_estado}")
                    
                    try:
                        # No degradar estados interactivos por STATE "inocuos" del monitor
                        estado_actual = None
                        with CP_ESTADO_LOCK:
                            estado_actual = CP_ESTADO.get(cp_state)
                        estados_interactivos = {
                            'PENDIENTE_CONFIRMACION_CENTRAL',
                            'ESPERANDO_OPERADOR_ENGINE',
                            'LISTO_PARA_INICIAR',
                            'ESPERANDO_CONFIRMACION_FIN'
                        }
                        degradantes = {'ACTIVADO', 'PARADO', 'PRE-SUMINISTRO'}
                        if estado_actual and estado_actual.upper() in estados_interactivos and str(nuevo_estado).upper() in degradantes:
                            registrar_evento(f"[IGNORADO] STATE {cp_state}: {estado_actual} mantiene prioridad sobre {nuevo_estado}")
                        else:
                            cambiar_estado_cp(cp_state, nuevo_estado, db_connection)
                    except Exception as e:
                        registrar_evento(f"[ERROR] No se pudo actualizar el estado de {cp_state}: {e}")

            else:
                print(f"[CENTRAL] Trama inválida de {cp_id}.")

    except ConnectionResetError:
        print(f"[CENTRAL] Conexión con {cp_id} perdida inesperadamente (Reset).")
    except Exception as e:
        print(f"[CENTRAL] Error en bucle de cliente {cp_id}: {e}")
    finally:
        if cp_id != "Desconocido":
            registrar_evento(f"Monitor desconectado: {cp_id}")
        # --- LÓGICA DB: Marcar el CP como AVERÍA ante desconexión inesperada ---
        if cp_id != "Desconocido" and db_connection and db_connection.is_connected():
            actualizar_estado_cp(db_connection, cp_id, "Averiado")
        try:
            if cp_id != "Desconocido":
                cambiar_estado_cp(cp_id, 'AVERÍA', db_connection, motivo='Desconexión inesperada del CP')
        except Exception:
            pass
        
        if cp_id in CONEXIONES_ACTIVAS:
            with CONEXIONES_ACTIVAS_LOCK:
                del CONEXIONES_ACTIVAS[cp_id]
                print(f"[CENTRAL] Socket de {cp_id} eliminado. Total: {len(CONEXIONES_ACTIVAS)}")
        
        # ====== OPCIONAL: MARCAR CP PARA RECONEXIÓN ======
        if cp_id != "Desconocido":
            registrar_evento(f"[INFO] {cp_id} podrá reconectarse automáticamente al reiniciar su Monitor.")
        
        conn.close()
        print(f"[CENTRAL] Hilo de conexión con {addr[0]}:{addr[1]} finalizado.")

def cambiar_estado_cp(cp_id: str, nuevo_estado: str, db_connection: mysql.connector.connection.MySQLConnection | None = None, motivo: str | None = None) -> None:
    """Actualiza el estado interno y la BD, y registra en el log/TUI.
    Estados esperados: DESCONECTADO, ACTIVADO, PRE-SUMINISTRO, SUMINISTRANDO, PARADO, AVERÍA.
    """
    nuevo_estado_norm = nuevo_estado.strip().upper() if isinstance(nuevo_estado, str) else str(nuevo_estado)
    with CP_ESTADO_LOCK, CP_ALERTA_LOCK:
        anterior = CP_ESTADO.get(cp_id)
        # Regla: si está en AVERÍA, no permitir cambios a estados distintos de AVERÍA, salvo recuperación explícita
        if anterior and anterior.upper() in ['AVERÍA', 'AVERIA'] and nuevo_estado_norm not in ['AVERÍA', 'AVERIA']:
            # Permitir solo si la alerta ha sido limpiada (AVR_CLR ya gestionó CP_ALERTA=False)
            alerta = CP_ALERTA.get(cp_id, False)
            if alerta:
                # Ignorar cambio mientras persista avería
                registrar_evento(f"[IGNORADO] {cp_id}: en AVERÍA → se ignora cambio a {nuevo_estado_norm}")
                return
        CP_ESTADO[cp_id] = nuevo_estado_norm
    detalle = f" (antes: {anterior})" if anterior and anterior != nuevo_estado_norm else ""
    extra = f" Motivo: {motivo}" if motivo else ""
    registrar_evento(f"[ESTADO] {cp_id} -> {nuevo_estado_norm}{detalle}.{extra}")
    # Persistir en BD si está disponible
    try:
        if db_connection and db_connection.is_connected():
            # Mapear a nombres en BD (usar Title case como en funciones existentes)
            mapa_bd = {
                'DESCONECTADO': 'Desconectado',
                'ACTIVADO': 'Activado',
                'PRE-SUMINISTRO': 'Pre-Suministro',
                'PENDIENTE_CONFIRMACION_CENTRAL': 'Pendiente Confirmacion Central',
                'ESPERANDO_OPERADOR_ENGINE': 'Esperando Operador Engine',
                'LISTO_PARA_INICIAR': 'Listo Para Iniciar',
                'SUMINISTRANDO': 'Suministrando',
                'CARGANDO': 'Suministrando',
                'ESPERANDO_CONFIRMACION_FIN': 'Esperando Confirmacion Fin',
                'PARADO': 'Parado',
                'AVERÍA': 'Averiado',
                'AVERIA': 'Averiado',
            }
            estado_bd = mapa_bd.get(nuevo_estado_norm, nuevo_estado_norm.title())
            actualizar_estado_cp(db_connection, cp_id, estado_bd)
    except Exception as e:
        print(f"[CENTRAL] No se pudo persistir estado de {cp_id}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Proceso EV_Central")
    parser.add_argument("--port", type=int, required=True, help="Puerto de escucha")
    parser.add_argument("--kafka", type=str, required=True, help="Broker Kafka (IP:puerto)")
    parser.add_argument("--db", type=str, help="Ruta/URL de la base de datos")
    parser.add_argument("--no-tui", action="store_true", help="Desactiva la TUI y usa modo consola simple")
    args = parser.parse_args()

    print("="*40)
    print("[EV_Central] INICIADO")
    print(f"Puerto de escucha: {args.port}")
    print(f"Broker Kafka: {args.kafka}")
    print(f"Base de datos: {args.db if args.db else 'Ninguna'}")
    print("="*40)
    print("Comandos disponibles:")
    print("  1 -> Refrescar")
    print("  2 START CP001  o  2 STOP CP001 -> Enviar orden al CP")
    print("  3 -> Salir")

    # Inicialización de la base de datos
    db_connection = None
    if args.db:
        try:
            db_connection = conectar_bd(args.db)
        except Exception as e:
            print(f"[EV_Central] ADVERTENCIA: No se pudo conectar a BD: {e}")
            print("[EV_Central] Continuando sin persistencia de datos...")
    else:
        print("[EV_Central] ADVERTENCIA: No se proporcionó configuración de BD")
        print("[EV_Central] Continuando sin persistencia de datos...")

    # Hacer accesible la conexión BD para el consumidor de telemetría (histórico)
    globals()['_DB_CONN_FOR_CONSUMER'] = db_connection

    # Al iniciar, marcar todos los CPs en BD como Desconectado
    # Solo se marcarán como activos cuando se reconecten
    try:
        if db_connection and db_connection.is_connected():
            cursor = db_connection.cursor()
            # Marcar todos los CPs como desconectados (inicio limpio)
            cursor.execute("UPDATE charging_points SET estado = 'Desconectado'")
            db_connection.commit()
            num_cps = cursor.rowcount
            if num_cps > 0:
                registrar_evento(f"[INICIO] {num_cps} CP(s) marcados como Desconectado. Esperando conexiones...", "info")
            cursor.close()
    except Exception as e:
        registrar_evento(f"[ERROR] No se pudo inicializar estado de CPs: {e}", "error")

    # Inicialización del productor Kafka para notificaciones
    inicializar_kafka_producer(args.kafka)

    # Inicialización del servidor de Sockets
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Permite reutilizar el puerto
        
        server_socket.bind(('', args.port)) 
        server_socket.listen(5)
        # Timeout corto para aceptar conexiones y poder revisar el flag de apagado
        server_socket.settimeout(1.0)
        
        # Forzar modo consola simple siempre (compat) y lanzar TUI Rich
        console_input_thread = threading.Thread(target=interfaz_consola_central, daemon=True)
        console_input_thread.start()
        tui_thread = threading.Thread(target=iniciar_interfaz_visual, daemon=True)
        tui_thread.start()

        # Hilo de procesamiento de comandos (común a ambos modos)
        cmd_thread = threading.Thread(target=bucle_procesador_comandos, daemon=True)
        cmd_thread.start()

        # Hilo consumidor de Kafka para telemetría
        kafka_consumer_thread = threading.Thread(
            target=consumir_telemetria_kafka,
            args=(args.kafka,),
            daemon=True
        )
        kafka_consumer_thread.start()
        # Hilo consumidor de Kafka para solicitudes de drivers
        driver_requests_thread = threading.Thread(
            target=consumir_solicitudes_driver_kafka,
            args=(args.kafka, db_connection),
            daemon=True
        )
        driver_requests_thread.start()
        # Hilo consumidor de Kafka para comandos de control desde web
        control_commands_thread = threading.Thread(
            target=consumir_comandos_control_kafka,
            args=(args.kafka,),
            daemon=True
        )
        control_commands_thread.start()
        # Lanzar monitor de actividad (heartbeat)
        threading.Thread(target=monitorizar_actividad_cps, args=(db_connection,), daemon=True).start()
        print(f"[EV_Central] Servidor escuchando en TCP (:{args.port})...")

        while True:
            # Verificar si se solicita el apagado
            with SHUTDOWN_LOCK:
                if SHUTDOWN_REQUESTED:
                    print("[EV_Central] Apagado solicitado, cerrando servidor...")
                    break
            
            # Bloqueante: Espera una conexión
            try:
                conn, addr = server_socket.accept()
            except socket.timeout:
                continue
            # Iniciar un nuevo hilo para manejar la conexión de forma concurrente
            client_thread = threading.Thread(target=manejar_cliente, args=(conn, addr, db_connection))
            client_thread.start()
            with CLIENT_THREADS_LOCK:
                CLIENT_THREADS.append(client_thread)

    
    except KeyboardInterrupt:
        print("\n[EV_Central] Apagando por interrupción de usuario...")
    except Exception as e:
        print(f"[EV_Central] Error principal: {e}")
    finally:
        # Cerrar todas las conexiones activas
        print("[EV_Central] Cerrando todas las conexiones activas...")
        with CONEXIONES_ACTIVAS_LOCK:
            for cp_id, conn in CONEXIONES_ACTIVAS.items():
                try:
                    conn.close()
                    print(f"[EV_Central] Conexión con {cp_id} cerrada.")
                except:
                    pass
            CONEXIONES_ACTIVAS.clear()
        registrar_evento("Central cerrando...")
        # Esperar a que terminen los hilos de clientes (con timeout)
        with CLIENT_THREADS_LOCK:
            for t in CLIENT_THREADS:
                try:
                    t.join(timeout=2.0)
                except Exception:
                    pass
            CLIENT_THREADS.clear()
        
        # Cerrar el servidor socket
        if 'server_socket' in locals():
            server_socket.close()
            print("[EV_Central] Servidor socket cerrado.")
        
        # Cerrar conexión a BD
        if db_connection and db_connection.is_connected():
            db_connection.close()
            print("[EV_Central] Conexión a BD cerrada.")
        
        print("[EV_Central] Apagado completado.")

if __name__ == "__main__":
    main()