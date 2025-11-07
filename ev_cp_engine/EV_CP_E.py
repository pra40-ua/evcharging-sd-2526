import socket
import argparse
import sys
import threading
import time

# =================================================================
#                         FUNCIONES DE PROTOCOLO
# (COPIADAS DEL MONITOR PARA LA COMUNICACIÓN HCK)
# =================================================================

# Constantes de Protocolo
STX = b'\x02'
ETX = b'\x03'
DELIMITER = '#'

import json
import time
from kafka import KafkaProducer, KafkaConsumer
import threading # Necesario si el Engine está corriendo en un bucle principal
import os
import subprocess
import platform
import urllib.request
import urllib.error
import webbrowser

# Importaciones para la interfaz web
from flask import Flask, render_template, jsonify, request, make_response, redirect
from flask_cors import CORS

# --- CONFIGURACIÓN ---
KAFKA_SERVER = os.getenv('KAFKA_SERVER', '127.0.0.1:9092')
TOPIC_TELEMETRY = 'telemetria_cp'

# Definición del Productor de Kafka (inicialización perezosa)
TELEMETRY_PRODUCER = None

def initialize_producer(broker: str):
    global TELEMETRY_PRODUCER
    if TELEMETRY_PRODUCER is not None:
        return TELEMETRY_PRODUCER
    try:
        TELEMETRY_PRODUCER = KafkaProducer(
            bootstrap_servers=[broker],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        print(f"[KAFKA PRODUCER] Productor de Telemetría inicializado en {broker}.")
    except Exception as e:
        print(f"[KAFKA PRODUCER] ERROR al inicializar el Productor de Telemetría: {e}")
        TELEMETRY_PRODUCER = None
    return TELEMETRY_PRODUCER

# --- FUNCIÓN DE TELEMETRÍA ---
def generar_y_enviar_telemetria(cp_id: str, estado_carga: str, kw_entregados: float, tiempo_carga_s: int, potencia_kw: float = 0.0):
    """
    Crea el mensaje de telemetría y lo envía al topic 'cp_telemetry'.
    """
    if TELEMETRY_PRODUCER is None:
        return

    # Verificar si está cargando - si CHARGING_FLAG está activo, el estado debe ser SUMINISTRANDO
    # Esto asegura que incluso si el estado del flujo no está sincronizado, el estado correcto se reporte
    estado_final = estado_carga
    try:
        with STATE_LOCK:
            cargando = CHARGING_FLAG.is_set()
        # Si está cargando, el estado debe ser SUMINISTRANDO (a menos que haya avería)
        if cargando and estado_carga != 'ESPERANDO_CONFIRMACION_FIN':
            estado_final = 'SUMINISTRANDO'
    except:
        pass

    # Verificar si hay avería simulada y sobrescribir estado si es necesario
    averia_activa = False
    try:
        with SIMULAR_AVERIA_LOCK:
            if SIMULAR_AVERIA:
                # Si hay avería, el estado debe ser AVERIADO
                estado_final = 'AVERIADO'
                averia_activa = True
    except:
        pass

    # Obtener información de sesión activa (según flujo)
    try:
        driver_id_sesion = globals().get('CURRENT_DRIVER_ID', 'UNKNOWN')
        with ESTADO_FLUJO_LOCK:
            estado_flujo_actual = ESTADO_FLUJO
        # Considerar sesión activa mientras esté en cualquiera de estas fases
        fases_con_sesion = ['ESPERANDO_DRIVER', 'LISTO_PARA_INICIAR', 'CARGANDO', 'ESPERANDO_CONFIRMACION_FIN']
        tiene_sesion = (driver_id_sesion is not None and driver_id_sesion != 'UNKNOWN' and estado_flujo_actual in fases_con_sesion)
    except Exception:
        driver_id_sesion = None
        tiene_sesion = False

    telemetria_msg = {
        'cp_id': cp_id,
        'timestamp': time.time(),
        'estado_carga': estado_final,
        'estado': estado_final,  # Agregar campo 'estado' también para compatibilidad
        'kw_entregados': kw_entregados,
        'energia_total': kw_entregados,  # Compatibilidad con diferentes lectores
        'potencia_actual': potencia_kw,
        'tiempo_carga_s': tiempo_carga_s,
        'tiene_sesion_activa': tiene_sesion,
        'driver_id_sesion': driver_id_sesion if tiene_sesion else None,
        'averia_activa': averia_activa  # Nuevo campo para indicar avería
    }

    try:
        # Envía el mensaje de forma asíncrona
        future = TELEMETRY_PRODUCER.send(TOPIC_TELEMETRY, value=telemetria_msg)
        # Opcional: Para verificar el envío (bloqueante, no recomendado en bucle rápido)
        # record_metadata = future.get(timeout=1) 
        # print(f"[{cp_id}] Telemetría enviada. Offset: {record_metadata.offset}")

    except Exception as e:
        print(f"[{cp_id}] ERROR al enviar telemetría a Kafka: {e}")

def consumir_mensajes_driver(driver_id: str, broker: str, cp_id: str, stop_event: threading.Event):
    """Consume mensajes del tópico driver_status_<driver_id> y los imprime en la terminal del engine."""
    topic = f"driver_status_{driver_id}"
    consumer = None
    try:
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=[broker],
            auto_offset_reset='latest',
            enable_auto_commit=True,
            group_id=f'engine-{cp_id}-driver-{driver_id}',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            api_version=(2, 8, 0)
        )
        print(f"[{cp_id}] 📡 Engine escuchando mensajes del driver {driver_id} en '{topic}'...")
        
        for msg in consumer:
            if stop_event.is_set():
                break
                
            payload = msg.value
            evento = payload.get('evento')
            detalle = payload.get('detalle')
            ts = payload.get('timestamp')
            
            # Imprimir mensaje en la terminal del engine
            print(f"[{cp_id}] 📨 [DRIVER {driver_id}] Evento={evento} @ {ts} -> {detalle}")
            
            # Mensajes específicos con formato mejorado
            if evento == 'RECIBIDA':
                print(f"[{cp_id}] 📨 [DRIVER {driver_id}] Solicitud recibida por Central. Validando CP...")
            elif evento == 'EN_COLA':
                posicion = detalle.get('posicion', '?') if isinstance(detalle, dict) else '?'
                cp_id_detalle = detalle.get('cp_id', '?') if isinstance(detalle, dict) else '?'
                print(f"[{cp_id}] 📨 [DRIVER {driver_id}] 🕐 CP {cp_id_detalle} ocupado. En cola de espera (posición {posicion})...")
            elif evento == 'AUTORIZADO':
                cp_id_detalle = detalle.get('cp_id', '?') if isinstance(detalle, dict) else '?'
                print(f"[{cp_id}] 📨 [DRIVER {driver_id}] ✅ Autorizado por Central para {cp_id_detalle}!")
            elif evento == 'AUTORIZACION_EN_PROCESO':
                mensaje = detalle.get('mensaje', '') if isinstance(detalle, dict) else ''
                print(f"[{cp_id}] 📨 [DRIVER {driver_id}] ⏳ Autorizando... {mensaje}")
            elif evento == 'DENEGADA':
                print(f"[{cp_id}] 📨 [DRIVER {driver_id}] ❌ Solicitud denegada: {detalle}")
            elif evento == 'TICKET_FINAL':
                if isinstance(detalle, dict):
                    cp_ticket = detalle.get('cp_id', '?')
                    energia = detalle.get('energia_kwh', '?')
                    importe = detalle.get('importe_eur', '?')
                    duracion = detalle.get('duracion_seg', 'N/D')
                    tx_id = detalle.get('tx_id', 'N/D')
                    print(f"\n[{cp_id}] 📨 [DRIVER {driver_id}] 🧾 TICKET FINAL RECIBIDO:")
                    print(f"[{cp_id}] 📨   Punto de Carga:  {cp_ticket}")
                    print(f"[{cp_id}] 📨   Energía:         {energia} kWh")
                    print(f"[{cp_id}] 📨   Importe:         {importe} €")
                    print(f"[{cp_id}] 📨   Duración:        {duracion} segundos")
                    print(f"[{cp_id}] 📨   ID Transacción:  {tx_id}")
                else:
                    print(f"[{cp_id}] 📨 [DRIVER {driver_id}] ✅ Ticket recibido: {detalle}")
                    
    except Exception as e:
        print(f"[{cp_id}] ❌ Error consumiendo mensajes del driver {driver_id}: {e}")
    finally:
        if consumer:
            consumer.close()
        print(f"[{cp_id}] 📡 Engine dejó de escuchar mensajes del driver {driver_id}")

def iniciar_consumidor_driver(driver_id: str, cp_id: str, broker: str):
    """Inicia el consumidor de mensajes del driver en un hilo separado."""
    global DRIVER_MESSAGES_CONSUMER, DRIVER_MESSAGES_THREAD, DRIVER_MESSAGES_STOP_EVENT
    
    with DRIVER_MESSAGES_LOCK:
        # Detener consumidor anterior si existe
        if DRIVER_MESSAGES_THREAD and DRIVER_MESSAGES_THREAD.is_alive():
            DRIVER_MESSAGES_STOP_EVENT.set()
            DRIVER_MESSAGES_THREAD.join(timeout=2)
        
        # Crear nuevo evento de parada
        DRIVER_MESSAGES_STOP_EVENT = threading.Event()
        
        # Iniciar nuevo consumidor
        DRIVER_MESSAGES_THREAD = threading.Thread(
            target=consumir_mensajes_driver,
            args=(driver_id, broker, cp_id, DRIVER_MESSAGES_STOP_EVENT),
            daemon=True
        )
        DRIVER_MESSAGES_THREAD.start()

def detener_consumidor_driver():
    """Detiene el consumidor de mensajes del driver."""
    global DRIVER_MESSAGES_CONSUMER, DRIVER_MESSAGES_THREAD, DRIVER_MESSAGES_STOP_EVENT
    
    with DRIVER_MESSAGES_LOCK:
        if DRIVER_MESSAGES_THREAD and DRIVER_MESSAGES_THREAD.is_alive():
            DRIVER_MESSAGES_STOP_EVENT.set()
            DRIVER_MESSAGES_THREAD.join(timeout=2)

# --- ESTADO DE CARGA ---
CHARGING_FLAG = threading.Event()  # START activa, STOP desactiva
STATE_LOCK = threading.Lock()
kw_acumulados_global = 0.0
segundos_global = 0

# Objetivo y sesión (con lock para sincronización)
TARGET_KWH = None
CURRENT_DRIVER_ID = 'UNKNOWN'
SESSION_START_TS = None
CURRENT_TX_ID = None
SESSION_LOCK = threading.Lock()

# Consumidor de Kafka para mensajes del driver
DRIVER_MESSAGES_CONSUMER = None
DRIVER_MESSAGES_THREAD = None
DRIVER_MESSAGES_STOP_EVENT = threading.Event()
DRIVER_MESSAGES_LOCK = threading.Lock()

# Estados del flujo interactivo
# REPOSO -> ESPERANDO_DRIVER -> LISTO_PARA_INICIAR -> CARGANDO -> ESPERANDO_CONFIRMACION_FIN -> REPOSO
ESTADO_FLUJO = 'REPOSO'  # REPOSO, ESPERANDO_DRIVER, LISTO_PARA_INICIAR, CARGANDO, ESPERANDO_CONFIRMACION_FIN
ESTADO_FLUJO_LOCK = threading.Lock()

# Conexión activa con Monitor (para poder enviar FIN desde el hilo de telemetría)
ACTIVE_MONITOR_CONN: socket.socket | None = None
ENGINE_CP_ID = None

# Estado de avería simulada (para responder KO en HCK)
SIMULAR_AVERIA = False
SIMULAR_AVERIA_LOCK = threading.Lock()

# Flask app para interfaz web (configurar rutas absolutas para templates)
import os as os_flask
_current_dir = os_flask.path.dirname(os_flask.path.abspath(__file__))
_template_dir = os_flask.path.join(_current_dir, 'templates')
_static_dir = os_flask.path.join(_current_dir, 'static')

app = Flask(__name__, template_folder=_template_dir, static_folder=_static_dir)
CORS(app)
WEB_PORT = 9000  # Puerto por defecto, se configurará según el CP

def bucle_telemetria_periodica(cp_id: str, stop_event: threading.Event):
    """Emite telemetría periódica del estado del CP (incluyendo avería) incluso cuando no hay carga."""
    print(f"[{cp_id}] Bucle de telemetría periódica iniciado (estado general).")
    while not stop_event.is_set():
        time.sleep(10)  # Enviar cada 10 segundos
        
        # Determinar el estado actual
        with ESTADO_FLUJO_LOCK:
            estado_flujo = ESTADO_FLUJO
        
        with STATE_LOCK:
            kw = round(kw_acumulados_global, 2)
            secs = segundos_global
            cargando = CHARGING_FLAG.is_set()
        
        # Si está cargando, el bucle de telemetría de carga ya está enviando, no duplicar
        if cargando:
            continue
        
        # Verificar estado de avería
        with SIMULAR_AVERIA_LOCK:
            averia_activa = SIMULAR_AVERIA
        
        # Determinar estado a reportar
        # NOTA: Si está cargando, el bucle_telemetria ya está enviando con estado SUMINISTRANDO
        # Aquí solo manejamos estados cuando NO está cargando
        if averia_activa:
            estado = 'AVERIADO'
        elif estado_flujo == 'CARGANDO':
            # Si el flujo dice CARGANDO pero no está cargando (caso raro), reportar como ACTIVADO
            estado = 'ACTIVADO'
        elif estado_flujo == 'ESPERANDO_DRIVER':
            estado = 'ESPERANDO_DRIVER'
        elif estado_flujo == 'LISTO_PARA_INICIAR':
            estado = 'LISTO_PARA_INICIAR'
        elif estado_flujo == 'ESPERANDO_CONFIRMACION_FIN':
            estado = 'ESPERANDO_CONFIRMACION_FIN'
        else:
            # Estado por defecto visible en Central: ACTIVADO (evitar marcar REPOSO automáticamente)
            estado = 'ACTIVADO'
        
        # Enviar telemetría con estado actual (la función ya maneja la avería)
        generar_y_enviar_telemetria(
            cp_id=cp_id,
            estado_carga=estado,
            kw_entregados=kw,
            tiempo_carga_s=secs,
            potencia_kw=0.0
        )


def bucle_telemetria(cp_id: str, stop_event: threading.Event):
    """Emite telemetría de SUMINISTRANDO únicamente mientras dure la sesión (START..STOP)."""
    global kw_acumulados_global, segundos_global
    print(f"[{cp_id}] Bucle de telemetría de SUMINISTRANDO iniciado.")
    while not stop_event.is_set():
        time.sleep(1)
        with STATE_LOCK:
            segundos_global += 1
            kw_acumulados_global += 0.05
            # Determinar el estado a reportar en telemetría respetando el flujo interactivo
            # Cuando se está cargando (CHARGING_FLAG activo), el estado debe ser SUMINISTRANDO
            estado = 'SUMINISTRANDO'
            try:
                with ESTADO_FLUJO_LOCK:
                    if ESTADO_FLUJO == 'ESPERANDO_CONFIRMACION_FIN':
                        estado = 'ESPERANDO_CONFIRMACION_FIN'
            except Exception:
                pass
            kw = round(kw_acumulados_global, 2)
            secs = segundos_global
            potencia = 3.0  # Potencia constante simulada en kW
        generar_y_enviar_telemetria(
            cp_id=cp_id,
            estado_carga=estado,
            kw_entregados=kw,
            tiempo_carga_s=secs,
            potencia_kw=potencia
        )
        # Auto-stop cuando se alcance el objetivo
        try:
            objetivo = globals()['TARGET_KWH']
            if objetivo is not None and kw >= float(objetivo):
                print(f"[{cp_id}] Objetivo de {objetivo} kWh alcanzado. Deteniendo suministro.")
                stop_event.set()
                CHARGING_FLAG.clear()
        except Exception:
            pass
    # Al salir del bucle por STOP, verificar si fue por objetivo alcanzado
    with STATE_LOCK:
        estado_final = 'REPOSO'
        kw_final = round(kw_acumulados_global, 2)
        secs_final = segundos_global
        objetivo = globals().get('TARGET_KWH')
        objetivo_alcanzado = objetivo is not None and kw_final >= float(objetivo)
    
    # Publicar telemetría final en REPOSO
    generar_y_enviar_telemetria(
        cp_id=cp_id,
        estado_carga=estado_final,
        kw_entregados=kw_final,
        tiempo_carga_s=secs_final,
        potencia_kw=0.0
    )
    
    # Solo enviar FIN si fue por objetivo alcanzado (no por STOP manual)
    if objetivo_alcanzado:
        try:
            conn = globals()['ACTIVE_MONITOR_CONN']
            if conn is not None:
                precio_kwh = 0.48
                importe = round(kw_final * precio_kwh, 2)
                driver_id = globals()['CURRENT_DRIVER_ID']
                tx_id = globals()['CURRENT_TX_ID'] or f"TX-{cp_id}-{int(time.time())}"
                motivo = 'Objetivo alcanzado'
                
                trama_fin = construir_trama('FIN', [
                    cp_id, 
                    driver_id, 
                    f"{kw_final:.2f}", 
                    f"{importe:.2f}", 
                    str(secs_final), 
                    motivo, 
                    tx_id
                ])
                conn.sendall(trama_fin)
                print(f"[{cp_id}] FIN enviado a Monitor (objetivo alcanzado). kWh={kw_final}, €={importe}, dur_s={secs_final}, tx={tx_id}")
                
                # Resetear contadores para la próxima sesión
                print(f"[{cp_id}] Contadores reseteados. Listo para nuevo servicio.")
        except Exception as e:
            print(f"[{cp_id}] No se pudo enviar FIN a Monitor: {e}")
        

def calcular_lrc(data_bytes: bytes) -> bytes:
    """Calcula el Longitudinal Redundancy Check (XOR de todos los bytes)."""
    lrc = 0
    for byte in data_bytes:
        lrc ^= byte
    return bytes([lrc])


def descomponer_trama(trama_bytes: bytes) -> tuple:
    """
    Descompone, valida y parsea la trama recibida (usada para HCK).
    Retorna (Cod_Op, campos) o (None, None) si falla la validación.
    """
    if len(trama_bytes) < 4:
         return None, None
    
    lrc_recibido = trama_bytes[-1:] 
    data_con_etx = trama_bytes[1:-1]
    data_bytes = data_con_etx[:-1]
    
    if not (trama_bytes.startswith(STX) and data_con_etx.endswith(ETX)):
        return None, None
        
    lrc_calculado = calcular_lrc(data_bytes)
    if lrc_recibido != lrc_calculado:
        # print(f"[ENGINE] Error LRC. Recibido: {lrc_recibido.hex()}, Calculado: {lrc_calculado.hex()}.")
        return None, None
        
    try:
        DATA = data_bytes.decode('utf-8')
        partes = DATA.split(DELIMITER)
        return partes[0], partes[1:]
    except UnicodeDecodeError:
        return None, None


def construir_trama(cod_op: str, campos: list) -> bytes:
    """Construye la trama completa para enviar una respuesta (HCK_RESP)."""
    DATA = f"{cod_op}#{DELIMITER.join(map(str, campos))}"
    DATA_bytes = DATA.encode('utf-8')
    LRC_byte = calcular_lrc(DATA_bytes)
    trama = STX + DATA_bytes + ETX + LRC_byte
    return trama

# =================================================================
#                       LÓGICA DEL ENGINE
# =================================================================

# Gestión del hilo de telemetría bajo demanda (arranca con START, se detiene con STOP)
TELEMETRY_THREAD = None
TELEMETRY_STOP_EVENT = threading.Event()

def handle_monitor_connection(conn: socket.socket, addr: tuple, cp_id: str):
    """Maneja el chequeo de salud HCK del Monitor."""
    # Declarar TODAS las variables globales al inicio para evitar errores de ámbito
    global kw_acumulados_global, segundos_global, TELEMETRY_THREAD, TELEMETRY_STOP_EVENT
    global TARGET_KWH, CURRENT_DRIVER_ID, ESTADO_FLUJO
    global SESSION_START_TS, CURRENT_TX_ID, ACTIVE_MONITOR_CONN
    print(f"\n{'='*70}")
    print(f"  [{cp_id}] 🔗 MONITOR CONECTADO desde {addr[0]}:{addr[1]}")
    print(f"{'='*70}\n")
    # Guardar conexión activa para permitir al menú enviar señales de 'enchufado'
    try:
        globals()['ACTIVE_MONITOR_CONN'] = conn
    except Exception:
        pass
    try:
        while True:
            # Esperar la trama HCK
            trama_bytes = conn.recv(1024)
            if not trama_bytes:
                break
            
            cod_op, campos = descomponer_trama(trama_bytes)

            if cod_op == 'HCK':
                # --- Lógica de Simulación de Estado ---
                # Verificar si hay avería simulada desde la web
                with SIMULAR_AVERIA_LOCK:
                    if SIMULAR_AVERIA:
                        status = "KO"
                    else:
                        status = "OK"
                
                respuesta = construir_trama('HCK_RESP', [status])
                conn.sendall(respuesta)
                # HCK es muy frecuente, no mostrar para no saturar la pantalla
            elif cod_op == 'AUTH_REQ':
                # Nuevo mensaje: Central autorizó un driver, pero NO inicia automáticamente
                # AUTH_REQ#<driver_id>#<kw_objetivo>
                global TARGET_KWH, CURRENT_DRIVER_ID, ESTADO_FLUJO
                try:
                    driver_id = campos[0] if len(campos) > 0 else 'UNKNOWN'
                    kw_objetivo = campos[1] if len(campos) > 1 else '0'
                    
                    print(f"\n{'='*70}")
                    print(f"  [{cp_id}] 📩 MENSAJE RECIBIDO: AUTH_REQ")
                    print(f"  Driver: {driver_id}")
                    print(f"  Objetivo: {kw_objetivo} kWh")
                    print(f"{'='*70}\n")
                    
                    # Guardar datos de sesión usando lock para thread-safety
                    try:
                        kw_float = float(kw_objetivo) if kw_objetivo else None
                    except:
                        kw_float = None
                    
                    # Usar SESSION_LOCK para garantizar sincronización entre hilos
                    with SESSION_LOCK:
                        TARGET_KWH = kw_float
                    CURRENT_DRIVER_ID = driver_id

                    # Iniciar consumidor de mensajes del driver
                    try:
                        iniciar_consumidor_driver(driver_id, cp_id, KAFKA_SERVER)
                    except Exception as e:
                        print(f"[{cp_id}] ⚠️ No se pudo iniciar consumidor de mensajes del driver: {e}")

                    # Actualizar caché de AUTH para UI robusta
                    with AUTH_CACHE_LOCK:
                        globals()['LAST_AUTH_DRIVER_ID'] = driver_id
                        globals()['LAST_AUTH_OBJ_KWH'] = kw_float
                        globals()['LAST_AUTH_TS'] = time.time()
                    
                    # Cambiar estado del flujo
                    with ESTADO_FLUJO_LOCK:
                        ESTADO_FLUJO = 'ESPERANDO_DRIVER'
                    
                    print(f"[{cp_id}] ⏳ Estado: REPOSO → ESPERANDO_DRIVER")
                    print(f"[{cp_id}] 👤 Driver autorizado: {driver_id} (kWh objetivo: {kw_float})")
                    print(f"[{cp_id}] 🌐 Web: Botón 'Iniciar Suministro' ahora disponible")
                    
                    # Debug: verificar valores
                    with SESSION_LOCK:
                        print(f"[{cp_id}] DEBUG: TARGET_KWH={TARGET_KWH}, CURRENT_DRIVER_ID={CURRENT_DRIVER_ID}")

                    # Lanzar prompt de operador por consola (si es posible)
                    try:
                        lanzar_prompt_operador(cp_id)
                    except Exception as e:
                        print(f"[{cp_id}] Aviso: no se pudo lanzar el prompt de operador: {e}")
                    
                    # Responder OK
                    respuesta = construir_trama('ACK', ['AUTH_OK'])
                    conn.sendall(respuesta)
                    
                except Exception as e:
                    print(f"[{cp_id}] Error procesando AUTH_REQ: {e}")
                    import traceback
                    traceback.print_exc()
                continue
                
            elif cod_op == 'CMD':
                orden = (campos[0] if campos else '').upper()
                if orden == 'START':
                    # START confirmado por Central tras READY_TO_START
                    # Campos opcionales: kw_objetivo, driver_id
                    kw_objetivo = None
                    driver_id = 'UNKNOWN'
                    try:
                        if len(campos) > 1 and campos[1] != '':
                            kw_objetivo = float(campos[1])
                        if len(campos) > 2 and campos[2] != '':
                            driver_id = str(campos[2])
                    except Exception:
                        pass
                    
                    # Si no vienen parámetros, usar los guardados de AUTH_REQ
                    if kw_objetivo is None:
                        kw_objetivo = TARGET_KWH
                    if driver_id == 'UNKNOWN':
                        driver_id = CURRENT_DRIVER_ID
                    
                    print(f"\n{'='*70}")
                    print(f"  [{cp_id}] 📩 MENSAJE RECIBIDO: CMD START (Confirmado por Central)")
                    print(f"  Driver: {driver_id}")
                    print(f"  Objetivo: {kw_objetivo} kWh" if kw_objetivo else "  Objetivo: Sin límite")
                    print(f"{'='*70}\n")
                    
                    with STATE_LOCK:
                        # Reinicia contadores al iniciar nueva sesión de carga
                        kw_acumulados_global = 0.0
                        segundos_global = 0
                        CHARGING_FLAG.set()
                        TARGET_KWH = kw_objetivo
                        CURRENT_DRIVER_ID = driver_id
                        SESSION_START_TS = time.time()
                        CURRENT_TX_ID = f"TX-{cp_id}-{int(SESSION_START_TS)}"
                        ACTIVE_MONITOR_CONN = conn
                        # Lanzar hilo de telemetría solo si no está ya activo
                        if TELEMETRY_THREAD is None or not TELEMETRY_THREAD.is_alive():
                            TELEMETRY_STOP_EVENT = threading.Event()
                            TELEMETRY_THREAD = threading.Thread(
                                target=bucle_telemetria,
                                args=(cp_id, TELEMETRY_STOP_EVENT),
                                daemon=True
                            )
                            TELEMETRY_THREAD.start()
                    
                    # Cambiar estado del flujo
                    with ESTADO_FLUJO_LOCK:
                        ESTADO_FLUJO = 'CARGANDO'
                    
                    print(f"[{cp_id}] ⚡ CARGA INICIADA - Estado: LISTO_PARA_INICIAR → CARGANDO")
                    info_ack = 'START_OK'
                    if kw_objetivo is not None:
                        info_ack = f"START_OK {kw_objetivo}kWh"
                    respuesta = construir_trama('ACK', [info_ack])
                    conn.sendall(respuesta)
                    print(f"\n{'='*70}")
                    print(f"  [{cp_id}] 📤 MENSAJE ENVIADO: ACK {info_ack}")
                    print(f"{'='*70}\n")
                elif orden == 'STOP':
                    # STOP confirmado por Central tras REQUEST_STOP
                    print(f"\n{'='*70}")
                    print(f"  [{cp_id}] 📩 MENSAJE RECIBIDO: CMD STOP (Confirmado por Central)")
                    print(f"{'='*70}\n")
                    
                    with STATE_LOCK:
                        CHARGING_FLAG.clear()
                        # Capturar valores finales antes de detener
                        kw_final = round(kw_acumulados_global, 2)
                        secs_final = segundos_global
                        # Señal de parada al hilo de telemetría (si estaba en marcha)
                        try:
                            TELEMETRY_STOP_EVENT.set()
                        except Exception:
                            pass
                    
                    # Cambiar estado del flujo
                    with ESTADO_FLUJO_LOCK:
                        ESTADO_FLUJO = 'REPOSO'
                    
                    print(f"[{cp_id}] 🛑 CARGA DETENIDA - Estado: ESPERANDO_CONFIRMACION_FIN → REPOSO")
                    
                    # Enviar telemetría final en REPOSO
                    generar_y_enviar_telemetria(
                        cp_id=cp_id,
                        estado_carga='REPOSO',
                        kw_entregados=kw_final,
                        tiempo_carga_s=secs_final,
                        potencia_kw=0.0
                    )
                    
                    # Enviar FIN al Monitor con los datos de la sesión
                    try:
                        precio_kwh = 0.48
                        importe = round(kw_final * precio_kwh, 2)
                        driver_id = globals().get('CURRENT_DRIVER_ID', 'UNKNOWN')
                        tx_id = globals().get('CURRENT_TX_ID') or f"TX-{cp_id}-{int(time.time())}"
                        motivo = 'Confirmado por Central'
                        
                        trama_fin = construir_trama('FIN', [
                            cp_id, 
                            driver_id, 
                            f"{kw_final:.2f}", 
                            f"{importe:.2f}", 
                            str(secs_final), 
                            motivo, 
                            tx_id
                        ])
                        conn.sendall(trama_fin)
                        
                        print(f"\n{'='*70}")
                        print(f"  [{cp_id}] 📤 MENSAJE ENVIADO: FIN")
                        print(f"  Energía entregada: {kw_final} kWh")
                        print(f"  Importe: €{importe}")
                        print(f"  Duración: {secs_final}s")
                        print(f"  Transacción: {tx_id}")
                        print(f"{'='*70}\n")
                        
                        print(f"[{cp_id}] ✓ Sesión finalizada. Listo para nuevo servicio.")
                        
                        # Detener consumidor de mensajes del driver
                        try:
                            detener_consumidor_driver()
                        except Exception as e:
                            print(f"[{cp_id}] ⚠️ Error deteniendo consumidor de mensajes del driver: {e}")
                        
                        # Resetear variables de sesión
                        TARGET_KWH = None
                        CURRENT_DRIVER_ID = 'UNKNOWN'
                        
                    except Exception as e:
                        print(f"[{cp_id}] ✗ Error enviando FIN tras STOP: {e}")
                    
                    respuesta = construir_trama('ACK', ['STOP_OK'])
                    conn.sendall(respuesta)
                    print(f"[{cp_id}] 📤 ACK enviado: STOP_OK\n")
                else:
                    print(f"[ENGINE] === ORDEN DESCONOCIDA: {orden} ===")
                    respuesta = construir_trama('ACK', [f'{orden}_IGN'])
                    conn.sendall(respuesta)
                
            else:
                 print(f"[ENGINE] Recibido mensaje desconocido: {cod_op}")
            
    except ConnectionResetError:
        print(f"[ENGINE] Conexión con Monitor ({addr[0]}) perdida inesperadamente.")
    except Exception as e:
        print(f"[ENGINE] Error en bucle de conexión con Monitor: {e}")
    finally:
        conn.close()
        print("[ENGINE] Conexión con Monitor cerrada.")


def enviar_estado_al_monitor(estado: str) -> None:
    """Envía un mensaje STATE al Monitor si hay conexión."""
    try:
        conn = globals().get('ACTIVE_MONITOR_CONN')
        cp_id = globals().get('ENGINE_CP_ID') or 'CP_UNKNOWN'
        if conn is None:
            print("[ENGINE] No hay conexión con Monitor para enviar STATE.")
            return
        trama_state = construir_trama('STATE', [cp_id, estado])
        conn.sendall(trama_state)
        print(f"[ENGINE] STATE enviado al Monitor: {estado}")
    except Exception as e:
        print(f"[ENGINE] Error enviando STATE al Monitor: {e}")


def obtener_estado_actual() -> str:
    """Retorna el estado actual del CP como string legible."""
    try:
        conn = globals().get('ACTIVE_MONITOR_CONN')
        if conn is None:
            return "DESCONECTADO (Sin Monitor)"
        
        with STATE_LOCK:
            if CHARGING_FLAG.is_set():
                return f"CARGANDO ({kw_acumulados_global:.2f} kWh, {segundos_global}s)"
            elif globals().get('SESION_DRIVER_ID') and globals().get('SESION_DRIVER_ID') != 'UNKNOWN':
                return "PRE-SUMINISTRO (Autorizado, esperando enchufar)"
            else:
                return "DISPONIBLE (Available)"
    except Exception:
        return "DISPONIBLE (Available)"

def mostrar_interfaz_cp(cp_id: str):
    """Muestra el banner y estado del CP."""
    print("\n" + "="*70)
    print(f"  CHARGING POINT: {cp_id}")
    print("="*70)
    print(f"  Estado: {obtener_estado_actual()}")
    print("="*70)
    print("\n  MENÚ DE SIMULACIÓN DEL CONDUCTOR:")
    print("    [p] Enchufar vehículo (Plug)")
    print("    [d] Desenchufar vehículo (Unplug)")
    print("    [r] Simular RFID / Iniciar sesión")
    print("    [s] Mostrar estado actual")
    print("    [h] Ayuda")
    print("    [q] Salir")
    print("="*70)

def menu_interactivo_engine() -> None:
    """Menú interactivo mejorado para simular acciones físicas en el CP."""
    cp_id = globals().get('ENGINE_CP_ID') or 'CP_UNKNOWN'
    mostrar_interfaz_cp(cp_id)
    
    while True:
        try:
            cmd = input(f"\n[{cp_id}] Acción: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print(f"\n[{cp_id}] Saliendo del menú...")
            break
        except Exception:
            time.sleep(0.5)
            continue
            
        if not cmd:
            continue
            
        if cmd == 'h':
            mostrar_interfaz_cp(cp_id)
            continue
            
        if cmd == 's':
            print(f"\n{'='*70}")
            print(f"  ESTADO ACTUAL DE {cp_id}")
            print(f"{'='*70}")
            print(f"  Estado: {obtener_estado_actual()}")
            with STATE_LOCK:
                print(f"  Energía acumulada: {kw_acumulados_global:.2f} kWh")
                print(f"  Tiempo de carga: {segundos_global} segundos")
            driver_id = globals().get('CURRENT_DRIVER_ID', 'UNKNOWN')
            print(f"  Driver actual: {driver_id}")
            print(f"  Monitor conectado: {'Sí' if globals().get('ACTIVE_MONITOR_CONN') else 'No'}")
            print(f"{'='*70}")
            continue
            
        if cmd == 'p':
            print(f"\n[{cp_id}] 🔌 Simulando ENCHUFAR vehículo...")
            enviar_estado_al_monitor('PLUGGED')
            print(f"[{cp_id}] ✓ Vehículo enchufado. Estado enviado al Monitor.")
            continue
            
        if cmd == 'd':
            print(f"\n[{cp_id}] 🔓 Simulando DESENCHUFAR vehículo...")
            try:
                with STATE_LOCK:
                    if 'TELEMETRY_STOP_EVENT' in globals() and TELEMETRY_STOP_EVENT:
                        TELEMETRY_STOP_EVENT.set()
                        CHARGING_FLAG.clear()
                enviar_estado_al_monitor('UNPLUGGED')
                print(f"[{cp_id}] ✓ Vehículo desenchufado. Carga detenida.")
            except Exception as e:
                print(f"[{cp_id}] ✗ Error al desenchufar: {e}")
            continue
            
        if cmd == 'r':
            print(f"\n[{cp_id}] 📱 Simulando lectura de RFID...")
            print(f"[{cp_id}] (Esta acción normalmente se hace desde la web/driver)")
            print(f"[{cp_id}] Estado actual: {obtener_estado_actual()}")
            continue
            
        if cmd == 'q':
            print(f"\n[{cp_id}] Saliendo del menú interactivo...")
            break
            
        print(f"[{cp_id}] ✗ Comando desconocido: '{cmd}'. Usa 'h' para ayuda.")

# =================================================================
#                    INTERFAZ WEB DEL ENGINE
# =================================================================

# Caché de última AUTH_REQ para robustez en la UI
LAST_AUTH_DRIVER_ID = None
LAST_AUTH_OBJ_KWH = None
LAST_AUTH_TS = 0.0
AUTH_CACHE_LOCK = threading.Lock()

# HTML embebido para evitar problemas con rutas de templates
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Control Engine - __CP_ID__</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: #333;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 900px; margin: 0 auto; }
        header {
            background: white;
            padding: 20px 30px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        h1 { color: #1e3c72; display: flex; align-items: center; gap: 10px; }
        .status-panel {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }
        .status-item {
            padding: 10px;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 4px solid #1e3c72;
        }
        .status-label {
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 5px;
        }
        .status-value {
            font-size: 20px;
            font-weight: bold;
            color: #1e3c72;
        }
        .control-panel {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        h2 {
            color: #1e3c72;
            margin-bottom: 15px;
            border-bottom: 2px solid #1e3c72;
            padding-bottom: 10px;
        }
        .button-group {
            margin-bottom: 30px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        .button-group h3 {
            margin-bottom: 15px;
            color: #555;
            font-size: 22px;
            font-weight: 700;
        }
        .button-group p {
            color: #666;
            font-size: 16px;
            margin-bottom: 15px;
            line-height: 1.6;
        }
        .btn {
            padding: 20px 40px;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            font-size: 18px;
            font-weight: 700;
            margin: 10px;
            transition: all 0.3s;
            display: inline-flex;
            align-items: center;
            gap: 12px;
            min-width: 250px;
            justify-content: center;
        }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
        .btn:active { transform: translateY(0); }
        .btn-danger { background: #dc3545; color: white; }
        .btn-danger:hover { background: #c82333; }
        .btn-success { background: #28a745; color: white; }
        .btn-success:hover { background: #218838; }
        .btn-warning { background: #ffc107; color: #333; }
        .btn-warning:hover { background: #e0a800; }
        .btn-secondary { background: #6c757d; color: white; }
        .btn-secondary:hover { background: #5a6268; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none !important; }
        .alert {
            padding: 15px 20px;
            border-radius: 6px;
            margin-bottom: 15px;
            display: none;
        }
        .alert.show { display: block; animation: slideIn 0.3s ease; }
        .alert-success { background: #d4edda; border-left: 4px solid #28a745; color: #155724; }
        .alert-danger { background: #f8d7da; border-left: 4px solid #dc3545; color: #721c24; }
        .alert-warning { background: #fff3cd; border-left: 4px solid #ffc107; color: #856404; }
        @keyframes slideIn {
            from { transform: translateX(-20px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        .refresh-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #28a745;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }
        .badge-ok { background: #28a745; color: white; }
        .badge-ko { background: #dc3545; color: white; }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>
                <span>⚙️</span>
                Panel de Control - <span id="cp-id-header">__CP_ID__</span>
                <span class="refresh-indicator"></span>
            </h1>
            <div style="font-size: 12px; color: #666; margin-top: 5px;">Engine Control Interface</div>
        </header>
        
        <div id="alert-container"></div>
        
        <div class="status-panel">
            <h2>📊 Estado Actual</h2>
            <div class="status-grid">
                <div class="status-item">
                    <div class="status-label">Estado</div>
                    <div class="status-value" id="status-estado">Cargando...</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Monitor</div>
                    <div class="status-value" id="status-monitor">-</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Energía (kWh)</div>
                    <div class="status-value" id="status-kwh">0.00</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Tiempo (s)</div>
                    <div class="status-value" id="status-tiempo">0</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Driver Actual</div>
                    <div class="status-value" id="status-driver" style="font-size: 14px;">-</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Objetivo (kWh)</div>
                    <div class="status-value" id="status-objetivo">-</div>
                </div>
            </div>
        </div>
        
        <div class="control-panel">
            <h2>🎮 Control de Suministro</h2>
            
            <!-- Contenedor dinámico para botones según estado -->
            <div id="flujo-container">
                <div class="button-group">
                    <p style="text-align: center; color: #999;">Cargando estado...</p>
                </div>
            </div>
            
            <!-- Sección de avería (siempre visible) -->
            <div style="margin-top: 20px; padding-top: 20px; border-top: 2px solid #dee2e6;">
                <h2>⚙️ Diagnóstico</h2>
                <div class="button-group">
                    <h3>Simular Avería</h3>
                    <p>Simula una avería en el punto de carga. El engine responderá KO al monitor.</p>
                    <button class="btn btn-danger" id="btn-activar-averia" onclick="simularAveria(true)">
                        <span>⚠️</span> Activar Avería
                    </button>
                    <button class="btn btn-success" id="btn-desactivar-averia" onclick="simularAveria(false)" style="display: none;">
                        <span>✓</span> Desactivar Avería
                    </button>
                    <div id="averia-status" style="margin-top: 10px;"></div>
                </div>
                <div class="button-group" style="margin-top: 20px; background: #f8f9fa; padding: 20px; border-radius: 8px;">
                    <h3>💻 Comandos PowerShell</h3>
                    <p style="color: #666; font-size: 13px; margin-bottom: 15px;">Comandos para ejecutar desde PowerShell:</p>
                    <div style="margin: 0 0 16px; color: #636e72; font-size: 13px;">
                        <p style="margin-bottom: 8px;"><strong>Para iniciar suministro:</strong></p>
                        <pre style="white-space: pre-wrap; background: #fff; padding: 10px; border-radius: 6px; border: 1px solid #dee2e6; font-size: 12px; margin-bottom: 15px;">Invoke-WebRequest -Method POST -Uri http://127.0.0.1:<span id="web-port-display">9000</span>/api/iniciar_suministro</pre>
                        <p style="margin-bottom: 8px;"><strong>Para solicitar fin del suministro:</strong></p>
                        <pre style="white-space: pre-wrap; background: #fff; padding: 10px; border-radius: 6px; border: 1px solid #dee2e6; font-size: 12px; margin-bottom: 15px;">Invoke-WebRequest -Method POST -Uri http://127.0.0.1:<span id="web-port-display-2">9000</span>/api/solicitar_fin</pre>
                        <p style="margin-bottom: 8px;"><strong>Para simular una avería:</strong></p>
                        <pre style="white-space: pre-wrap; background: #fff; padding: 10px; border-radius: 6px; border: 1px solid #dee2e6; font-size: 12px; margin-bottom: 15px;">$body = @{activar=$true;motivo="Avería simulada"} | ConvertTo-Json; Invoke-WebRequest -Method POST -Uri http://127.0.0.1:<span id="web-port-display-3">9000</span>/api/simular_averia -ContentType "application/json" -Body $body</pre>
                        <p style="margin-bottom: 8px;"><strong>Para recuperar de avería:</strong></p>
                        <pre style="white-space: pre-wrap; background: #fff; padding: 10px; border-radius: 6px; border: 1px solid #dee2e6; font-size: 12px;">Invoke-WebRequest -Method POST -Uri http://127.0.0.1:<span id="web-port-display-4">9000</span>/api/recuperar_averia</pre>
                    </div>
                </div>
            </div>
        </div>
        
        <div style="background: white; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; color: #666; font-size: 12px;">
            <strong>Última actualización:</strong> <span id="last-update">-</span>
        </div>
    </div>
    
    <script>
        console.log('[WEB] ✅ Script cargado correctamente');
        var updateInterval;
        var estadoAveria = false;
        
        function actualizarEstado() {
            console.log('[WEB] Llamando a /api/status...');
            var url = '/api/status?t=' + Date.now();
            fetch(url, { cache: 'no-store' })
                .then(function(response) {
                    console.log('[WEB] Respuesta recibida:', response.status);
                    if (!response.ok) {
                        throw new Error('HTTP error! status: ' + response.status);
                    }
                    return response.json();
                })
                .then(function(data) {
                    console.log('[WEB] Datos recibidos:', data);
                    console.log('[WEB] Estado flujo:', data.estado_flujo);
                    console.log('[WEB] Driver actual:', data.driver_actual);
                    console.log('[WEB] Objetivo kWh:', data.objetivo_kwh);
                    
                    try {
                    // Actualizar estado del flujo
                        console.log('[WEB] Actualizando elementos DOM...');
                        // Fuente de verdad: estado de flujo que envía el backend
                        var estadoParaBotones = data.estado_flujo;
                        // Salvaguarda: si el flujo es REPOSO pero hay sesión activa, derivar a ESPERANDO_DRIVER
                        if (estadoParaBotones === 'REPOSO' && (data.driver_actual && data.driver_actual !== 'UNKNOWN') && (data.objetivo_kwh !== null && data.objetivo_kwh !== undefined)) {
                            console.log('[WEB] 🛡️ Derivando estado a ESPERANDO_DRIVER por sesión activa');
                            estadoParaBotones = 'ESPERANDO_DRIVER';
                        }
                        document.getElementById('status-estado').textContent = estadoParaBotones || data.estado || '-';
                    document.getElementById('status-monitor').innerHTML = data.monitor_conectado 
                        ? '<span class="badge badge-ok">Conectado</span>' 
                        : '<span class="badge badge-ko">Desconectado</span>';
                    document.getElementById('status-kwh').textContent = data.kw_acumulados.toFixed(2);
                    document.getElementById('status-tiempo').textContent = data.segundos;
                    document.getElementById('status-driver').textContent = data.driver_actual || '-';
                    document.getElementById('status-objetivo').textContent = data.objetivo_kwh ? data.objetivo_kwh + ' kWh' : '-';
                    
                    // Actualizar botones según estado del flujo
                        console.log('[WEB] Llamando a actualizarBotonesFlujo con estado:', estadoParaBotones);
                        actualizarBotonesFlujo(estadoParaBotones, data);
                        console.log('[WEB] ✓ Botones actualizados');
                    } catch (e) {
                        console.error('[WEB] ❌ Error actualizando DOM:', e);
                        throw e;
                    }
                    
                    // Estado de avería
                    estadoAveria = data.averia_simulada;
                    if (estadoAveria) {
                        document.getElementById('btn-activar-averia').style.display = 'none';
                        document.getElementById('btn-desactivar-averia').style.display = 'inline-flex';
                        document.getElementById('averia-status').innerHTML = 
                            '<span class="badge badge-ko">AVERÍA ACTIVA</span> - Respondiendo KO al monitor';
                    } else {
                        document.getElementById('btn-activar-averia').style.display = 'inline-flex';
                        document.getElementById('btn-desactivar-averia').style.display = 'none';
                        document.getElementById('averia-status').innerHTML = 
                            '<span class="badge badge-ok">NORMAL</span> - Respondiendo OK al monitor';
                    }
                    
                    var now = new Date();
                    document.getElementById('last-update').textContent = now.toLocaleTimeString('es-ES');
                })
                .catch(function(error) {
                    console.error('[WEB] ❌ Error actualizando estado:', error);
                    console.error('[WEB] Error details:', error.message, error.stack);
                });
        }
        
        function mostrarAlerta(mensaje, tipo) {
            var container = document.getElementById('alert-container');
            var alert = document.createElement('div');
            alert.className = 'alert alert-' + tipo + ' show';
            alert.textContent = mensaje;
            container.appendChild(alert);
            setTimeout(function() {
                alert.classList.remove('show');
                setTimeout(function() { alert.remove(); }, 300);
            }, 5000);
        }
        
        function actualizarBotonesFlujo(estadoFlujo, data) {
            console.log('[WEB] 🎨 actualizarBotonesFlujo llamada con:', estadoFlujo);
            var contenedor = document.getElementById('flujo-container');
            if (!contenedor) {
                console.error('[WEB] ❌ No se encontró elemento flujo-container');
                return;
            }
            var html = '';
            
            if (estadoFlujo === 'ESPERANDO_DRIVER') {
                console.log('[WEB] 🔵 Generando HTML para ESPERANDO_DRIVER');
                var objetivo = data.objetivo_kwh || '?';
                html = '<div class="button-group" style="background: #e8f5e9;">' +
                    '<h3>✅ Driver Autorizado</h3>' +
                    '<p><strong>Driver:</strong> ' + data.driver_actual + '<br>' +
                    '<strong>Objetivo:</strong> ' + objetivo + ' kWh</p>' +
                    '<p>La Central ha autorizado este driver. Pulsa el botón cuando el vehículo esté listo para iniciar la carga.</p>' +
                    '<button class="btn btn-success" onclick="iniciarSuministro()">' +
                    '<span>🔌</span> Iniciar Suministro' +
                    '</button>' +
                    '</div>';
            }
            // Si hay sesión activa (driver/objetivo) pero el estado no es ESPERANDO_DRIVER, mostrar opciones de sincronización
            else if ((data.driver_actual && data.driver_actual !== 'UNKNOWN') && (data.objetivo_kwh !== null && data.objetivo_kwh !== undefined)) {
                console.log('[WEB] 🧭 Sesión detectada pero estado no sincronizado, mostrando controles');
                var objetivo2 = data.objetivo_kwh || '?';
                html = '<div class="button-group" style="background: #e8f5e9;">' +
                    '<h3>✅ Driver Autorizado (pendiente de sincronización)</h3>' +
                    '<p><strong>Driver:</strong> ' + data.driver_actual + '<br>' +
                    '<strong>Objetivo:</strong> ' + objetivo2 + ' kWh</p>' +
                    '<p>El estado local no está sincronizado. Puedes iniciar o forzar la sincronización.</p>' +
                    '<div>' +
                    '<button class="btn btn-success" onclick="iniciarSuministro()"><span>🔌</span> Iniciar Suministro</button>' +
                    '<button class="btn btn-warning" onclick="forzarEsperando()"><span>🛠️</span> Sincronizar Estado</button>' +
                    '</div>' +
                    '</div>';
            }
            else if (estadoFlujo === 'LISTO_PARA_INICIAR') {
                console.log('[WEB] 🟡 Generando HTML para LISTO_PARA_INICIAR');
                html = '<div class="button-group" style="background: #fff3cd;">' +
                    '<h3>⏳ Esperando Confirmación de Central</h3>' +
                    '<p>Señal enviada a la Central. El operador de Central debe confirmar el inicio del suministro.</p>' +
                    '<div style="text-align: center; padding: 20px;">' +
                    '<div class="spinner"></div>' +
                    '<p style="margin-top: 10px; color: #856404;">Aguardando confirmación...</p>' +
                    '</div>' +
                    '</div>';
            }
            else if (estadoFlujo === 'CARGANDO') {
                console.log('[WEB] 🟢 Generando HTML para CARGANDO');
                var progreso = data.objetivo_kwh ? ((data.kw_acumulados / data.objetivo_kwh) * 100).toFixed(1) : 0;
                var objetivo_texto = data.objetivo_kwh || '∞';
                html = '<div class="button-group" style="background: #d1ecf1;">' +
                    '<h3>⚡ Suministro en Progreso</h3>' +
                    '<p><strong>Driver:</strong> ' + data.driver_actual + '<br>' +
                    '<strong>Energía:</strong> ' + data.kw_acumulados.toFixed(2) + ' / ' + objetivo_texto + ' kWh (' + progreso + '%)<br>' +
                    '<strong>Tiempo:</strong> ' + data.segundos + 's</p>' +
                    '<button class="btn btn-danger" onclick="solicitarFin()">' +
                    '<span>🛑</span> Solicitar Fin de Suministro' +
                    '</button>' +
                    '</div>';
            }
            else if (estadoFlujo === 'ESPERANDO_CONFIRMACION_FIN') {
                console.log('[WEB] 🔴 Generando HTML para ESPERANDO_CONFIRMACION_FIN');
                html = '<div class="button-group" style="background: #f8d7da;">' +
                    '<h3>⏳ Esperando Confirmación de Fin</h3>' +
                    '<p>Solicitud de fin enviada a la Central. El operador de Central debe confirmar el cierre del suministro.</p>' +
                    '<p><strong>Energía actual:</strong> ' + data.kw_acumulados.toFixed(2) + ' kWh<br>' +
                    '<strong>Tiempo:</strong> ' + data.segundos + 's</p>' +
                    '<div style="text-align: center; padding: 20px;">' +
                    '<div class="spinner"></div>' +
                    '<p style="margin-top: 10px; color: #721c24;">Aguardando confirmación de fin...</p>' +
                    '</div>' +
                    '</div>';
            }
            else {
                console.log('[WEB] ⚪ Generando HTML para estado desconocido o REPOSO:', estadoFlujo);
                html = '<div class="button-group" style="text-align: center; padding: 40px 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">' +
                    '<h3 style="color: white; font-size: 32px; margin-bottom: 20px;">💤 Punto de Carga en Reposo</h3>' +
                    '<p style="font-size: 20px; color: rgba(255,255,255,0.95); margin-bottom: 30px;">' +
                    'El punto de carga está <strong>DISPONIBLE</strong> y funcionando correctamente.' +
                    '</p>' +
                    '<div style="background: rgba(255,255,255,0.2); padding: 25px; border-radius: 10px; margin-top: 20px;">' +
                    '<p style="font-size: 18px; color: rgba(255,255,255,0.9);">⏳ Esperando solicitud de un driver desde la Central</p>' +
                    '<p style="color: rgba(255,255,255,0.7); font-size: 15px; margin-top: 15px;">' +
                    'Los drivers solicitan carga a través de su aplicación móvil' +
                    '</p>' +
                    '</div>' +
                    '</div>';
            }
            
            console.log('[WEB] 📝 Estableciendo innerHTML (longitud:', html.length, ')');
            contenedor.innerHTML = html;
            console.log('[WEB] ✅ innerHTML establecido correctamente');
        }
        
        function iniciarSuministro() {
            if (!confirm('¿Iniciar el suministro? Se enviará señal a Central para confirmación.')) return;
            
            fetch('/api/iniciar_suministro', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            })
            .then(function(response) { return response.json(); })
            .then(function(data) {
                var mensaje = data.status === 'ok' ? data.mensaje : 'Error: ' + data.mensaje;
                var tipo = data.status === 'ok' ? 'success' : 'danger';
                mostrarAlerta(mensaje, tipo);
                actualizarEstado();
            })
            .catch(function(error) { mostrarAlerta('Error: ' + error, 'danger'); });
        }
        
        function solicitarFin() {
            if (!confirm('¿Solicitar fin del suministro? Se enviará señal a Central para confirmación.')) return;
            
            fetch('/api/solicitar_fin', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            })
            .then(function(response) { return response.json(); })
            .then(function(data) {
                if (data.status === 'ok') {
                    var msg = data.mensaje + ' (' + data.kw_actual + ' kWh, ' + data.segundos + 's)';
                    mostrarAlerta(msg, 'warning');
                } else {
                    mostrarAlerta('Error: ' + data.mensaje, 'danger');
                }
                actualizarEstado();
            })
            .catch(function(error) { mostrarAlerta('Error: ' + error, 'danger'); });
        }
        
        function forzarEsperando() {
            fetch('/api/forzar_esperando', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            })
            .then(function(response) { return response.json(); })
            .then(function(data) {
                var tipo = data.status === 'ok' ? 'success' : 'danger';
                var mensaje = data.mensaje || (data.status === 'ok' ? 'Estado sincronizado' : 'No se pudo sincronizar');
                mostrarAlerta(mensaje, tipo);
                actualizarEstado();
            })
            .catch(function(error) { mostrarAlerta('Error: ' + error, 'danger'); });
        }
        
        function simularAveria(activar) {
            var motivo = activar ? prompt('Motivo de la avería:', 'Fallo simulado') : '';
            if (activar && !motivo) return;
            
            var motivoFinal = motivo || 'Avería simulada';
            var payload = {'activar': activar, 'motivo': motivoFinal};
            
            fetch('/api/simular_averia', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            })
            .then(function(response) { return response.json(); })
            .then(function(data) {
                if (data.status === 'ok') {
                    var tipo = activar ? 'danger' : 'success';
                    mostrarAlerta(data.mensaje, tipo);
                    actualizarEstado();
                } else {
                    mostrarAlerta('Error: ' + data.mensaje, 'danger');
                }
            })
            .catch(function(error) { mostrarAlerta('Error: ' + error, 'danger'); });
        }
        
        
        function conectarDriver() {
            var driverId = prompt('ID del Driver (opcional):', 'DRIVER_WEB') || 'DRIVER_WEB';
            var payload = {'driver_id': driverId};
            
            fetch('/api/conectar_driver', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            })
            .then(function(response) { return response.json(); })
            .then(function(data) {
                var mensaje = data.status === 'ok' ? data.mensaje : 'Error: ' + data.mensaje;
                var tipo = data.status === 'ok' ? 'success' : 'danger';
                mostrarAlerta(mensaje, tipo);
                actualizarEstado();
            })
            .catch(function(error) { mostrarAlerta('Error: ' + error, 'danger'); });
        }
        
        function desconectarDriver() {
            if (!confirm('¿Desconectar el driver actual?')) return;
            fetch('/api/desconectar_driver', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            })
            .then(function(response) { return response.json(); })
            .then(function(data) {
                var mensaje = data.status === 'ok' ? data.mensaje : 'Error: ' + data.mensaje;
                var tipo = data.status === 'ok' ? 'warning' : 'danger';
                mostrarAlerta(mensaje, tipo);
                actualizarEstado();
            })
            .catch(function(error) { mostrarAlerta('Error: ' + error, 'danger'); });
        }
        
        function cerrarSuministro() {
            if (!confirm('¿Cerrar el suministro actual?')) return;
            fetch('/api/solicitar_cierre_suministro', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            })
            .then(function(response) { return response.json(); })
            .then(function(data) {
                if (data.status === 'ok') {
                    var mensaje = 'Suministro cerrado: ' + data.kw_final + ' kWh, €' + data.importe + ', ' + data.duracion_s + 's';
                    mostrarAlerta(mensaje, 'success');
                    actualizarEstado();
                } else {
                    mostrarAlerta('Error: ' + data.mensaje, 'danger');
                }
            })
            .catch(function(error) { mostrarAlerta('Error: ' + error, 'danger'); });
        }
        
        // Actualizar puertos dinámicamente en los comandos PowerShell
        function actualizarPuertosComandos() {
            var port = window.location.port || '9000';
            var elements = ['web-port-display', 'web-port-display-2', 'web-port-display-3', 'web-port-display-4'];
            elements.forEach(function(id) {
                var el = document.getElementById(id);
                if (el) el.textContent = port;
            });
        }
        
        console.log('[WEB] 🚀 Iniciando actualización automática...');
        actualizarEstado();
        actualizarPuertosComandos();
        updateInterval = setInterval(actualizarEstado, 2000);
        console.log('[WEB] ✅ Intervalo configurado (cada 2 segundos)');
    </script>
</body>
</html>"""

# =================================================================
#             CONFIRMACIÓN POR CONSOLA DEL OPERADOR
# =================================================================

def _enviar_ready_to_start_interno() -> tuple[bool, str]:
    """Replica la lógica de /api/iniciar_suministro para confirmar inicio por consola."""
    global ESTADO_FLUJO, ENGINE_CP_ID, ACTIVE_MONITOR_CONN, CURRENT_DRIVER_ID
    cp_id = globals().get('ENGINE_CP_ID') or 'CP_UNKNOWN'
    # Validación/Transición de estado
    with ESTADO_FLUJO_LOCK:
        if ESTADO_FLUJO != 'ESPERANDO_DRIVER':
            with SESSION_LOCK:
                driver_tmp = CURRENT_DRIVER_ID
                objetivo_tmp = TARGET_KWH
            if not (driver_tmp and driver_tmp != 'UNKNOWN' and objetivo_tmp is not None):
                return False, f'No se puede iniciar. Estado actual: {ESTADO_FLUJO}'
        ESTADO_FLUJO = 'LISTO_PARA_INICIAR'
    # Conexión con monitor
    if globals().get('ACTIVE_MONITOR_CONN') is None:
        with ESTADO_FLUJO_LOCK:
            ESTADO_FLUJO = 'ESPERANDO_DRIVER'
        return False, 'No hay conexión con el Monitor'
    # Enviar READY_TO_START
    with SESSION_LOCK:
        driver_id = globals().get('CURRENT_DRIVER_ID', 'UNKNOWN')
    try:
        trama = construir_trama('READY_TO_START', [cp_id, driver_id])
        globals()['ACTIVE_MONITOR_CONN'].sendall(trama)
        print(f"[{cp_id}] 📤 READY_TO_START enviado a Monitor (Driver: {driver_id}) [CLI]")
        return True, 'Señal enviada a Central. Esperando confirmación...'
    except Exception as e:
        with ESTADO_FLUJO_LOCK:
            ESTADO_FLUJO = 'ESPERANDO_DRIVER'
        return False, f'Error enviando señal: {str(e)}'


def _thread_prompt_operador(cp_id: str, web_port: int | None) -> None:
    """Hilo simple que pide por stdin pulsar 1 para confirmar inicio."""
    print("\n" + "="*70)
    print(f"  [{cp_id}] OPERADOR: Solicitud de inicio recibida")
    print("  Pulse '1' y Enter para confirmar el inicio del suministro")
    print("  (o 'q' y Enter para cancelar)")
    print("="*70 + "\n")
    try:
        if sys.stdin and sys.stdin.isatty():
            while True:
                try:
                    elec = input("[OPERADOR] Confirmar inicio (1=Sí, q=Cancelar): ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    return
                if elec == '1':
                    ok, msg = _enviar_ready_to_start_interno()
                    print(f"[OPERADOR] {'OK' if ok else 'ERROR'}: {msg}")
                    return
                if elec == 'q':
                    print("[OPERADOR] Cancelado por el operador")
                    return
        else:
            # Sin TTY: indicar alternativa
            if web_port:
                print(f"[OPERADOR] No hay TTY. Puede confirmar ejecutando: curl -s -X POST http://127.0.0.1:{web_port}/api/iniciar_suministro")
            else:
                print("[OPERADOR] No hay TTY. No se puede capturar tecla; use la Central para confirmar.")
    except Exception as e:
        print(f"[OPERADOR] Error en prompt: {e}")


def lanzar_prompt_operador(cp_id: str) -> None:
    """Intenta abrir una nueva consola en Windows; si no, usa hilo en el mismo proceso."""
    web_port = globals().get('WEB_PORT')
    try:
        if platform.system().lower().startswith('win'):
            # Intentar abrir una nueva consola que, al pulsar 1, haga POST al endpoint
            if web_port:
                cmd_code = (
                    "import sys,urllib.request;\n"
                    "input('Pulse 1 y Enter para confirmar (cierra con Ctrl+C para cancelar): ');\n"
                    f"urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:{web_port}/api/iniciar_suministro', method='POST'))\n"
                    "print('Confirmado. Puede cerrar esta ventana.')\n"
                )
                try:
                    creation = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
                    subprocess.Popen([
                        sys.executable, '-c', cmd_code
                    ], creationflags=creation)
                    print(f"[{cp_id}] Ventana de confirmación abierta (Windows).")
                    return
                except Exception as e:
                    print(f"[{cp_id}] No se pudo abrir consola separada: {e}")
        # Fallback: hilo en el mismo proceso
        t = threading.Thread(target=_thread_prompt_operador, args=(cp_id, web_port), daemon=True)
        t.start()
    except Exception as e:
        print(f"[{cp_id}] Error lanzando prompt de operador: {e}")

@app.route('/')
def index():
    """Redirige al panel local del Engine."""
    return redirect('/panel_local', code=302)


@app.route('/panel_local')
def panel_local():
    """Panel mínimo con botones para operar contra la API local."""
    cp_id = globals().get('ENGINE_CP_ID') or 'CP_UNKNOWN'
    web_port = globals().get('WEB_PORT') or 9000
    html = f"""
<!DOCTYPE html>
<html lang=\"es\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Panel Local Engine - {cp_id}</title>
  <style>
    body {{ font-family: Segoe UI, Roboto, Arial, sans-serif; padding: 20px; background: #f5f6fa; }}
    h1 {{ margin: 0 0 10px; color: #2d3436; }}
    .row {{ display: flex; gap: 10px; flex-wrap: wrap; margin: 10px 0 20px; }}
    button {{ padding: 12px 18px; border: 0; border-radius: 6px; cursor: pointer; font-weight: 700; }}
    .ok {{ background: #2ecc71; color: #fff; }}
    .warn {{ background: #f1c40f; color: #2d3436; }}
    .danger {{ background: #e74c3c; color: #fff; }}
    .muted {{ background: #95a5a6; color: #fff; }}
    pre {{ background: #fff; padding: 12px; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,.08); max-height: 320px; overflow: auto; }}
  </style>
  <script>
    let estadoActual = null;
    async function post(url) {{
      const r = await fetch(url, {{ method: 'POST' }});
      const j = await r.json().catch(() => ({{ status: 'error', mensaje: 'Respuesta no JSON' }}));
      log('POST ' + url + ' -> ' + JSON.stringify(j));
      await estado();
    }}
    async function simularAveria() {{
      const motivo = prompt('Motivo de la avería (opcional):', 'Avería simulada desde web') || 'Avería simulada desde web';
      const r = await fetch('/api/simular_averia', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ activar: true, motivo: motivo }})
      }});
      const j = await r.json().catch(() => ({{ status: 'error', mensaje: 'Respuesta no JSON' }}));
      log('POST /api/simular_averia -> ' + JSON.stringify(j));
      await estado();
    }}
    async function estado() {{
      const r = await fetch('/api/status?t=' + Date.now(), {{ cache: 'no-store' }});
      const j = await r.json();
      document.getElementById('estado').textContent = JSON.stringify(j, null, 2);
      estadoActual = j;
      // Mostrar/ocultar botones según estado_flujo
      const flujo = j.estado_flujo;
      const haySesion = (j.driver_actual && j.driver_actual !== 'UNKNOWN') && (j.objetivo_kwh !== null && j.objetivo_kwh !== undefined);
      const btnStart = document.getElementById('btn-start');
      const btnStop = document.getElementById('btn-stop');
      const btnSync = document.getElementById('btn-sync');
      const info = document.getElementById('info-flujo');
      if (btnStart) btnStart.style.display = (flujo === 'ESPERANDO_DRIVER') ? 'inline-block' : 'none';
      if (btnStop) btnStop.style.display = ((flujo === 'CARGANDO') || (j.cargando === true)) ? 'inline-block' : 'none';
      if (btnSync) btnSync.style.display = (haySesion && flujo !== 'ESPERANDO_DRIVER') ? 'inline-block' : 'none';
      if (info) {{
        if (flujo === 'ESPERANDO_CONFIRMACION_FIN') {{
          info.style.display = 'block';
          info.innerHTML = '⏳ Esperando confirmación de Central para finalizar...';
        }} else if (flujo === 'LISTO_PARA_INICIAR') {{
          info.style.display = 'block';
          info.innerHTML = '⏳ Señal enviada. Esperando confirmación de Central...';
        }} else {{
          info.style.display = 'none';
          info.textContent = '';
        }}
      }}
    }}
    function log(m) {{
      const el = document.getElementById('log');
      el.textContent += (new Date()).toLocaleTimeString('es-ES') + ' - ' + m + "\n";
      el.scrollTop = el.scrollHeight;
    }}
    window.addEventListener('load', estado);
    // Refresco automático cada 2 segundos
    setInterval(estado, 2000);
    // Atajos de teclado: '1' para confirmar inicio, 'q' para cancelar
    window.addEventListener('keydown', function(e) {{
      // Evitar interferir con inputs (no hay en este panel, pero por si acaso)
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
      const key = (e.key || '').toLowerCase();
      if (key === '1') {{
        if (!estadoActual || estadoActual.estado_flujo !== 'ESPERANDO_DRIVER') {{
          log("No se puede confirmar: estado actual = " + (estadoActual ? estadoActual.estado_flujo : 'desconocido'));
          return;
        }}
        log("Tecla '1' pulsada -> confirmando inicio...");
        post('/api/iniciar_suministro');
      }} else if (key === 'q') {{
        log("Tecla 'q' pulsada → cancelado por operador");
      }}
    }});
  </script>
  <meta http-equiv=\"Cache-Control\" content=\"no-store, no-cache, must-revalidate, max-age=0\" />
  <meta http-equiv=\"Pragma\" content=\"no-cache\" />
  <meta http-equiv=\"Expires\" content=\"0\" />
  <meta http-equiv=\"X-UA-Compatible\" content=\"IE=edge\" />
  <meta http-equiv=\"Referrer-Policy\" content=\"no-referrer\" />
  <meta http-equiv=\"Permissions-Policy\" content=\"interest-cohort=()\" />
  <meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'self'; connect-src 'self'; style-src 'unsafe-inline' 'self'; script-src 'self' 'unsafe-inline'\" />
  <meta http-equiv=\"Cross-Origin-Opener-Policy\" content=\"same-origin\" />
  <meta http-equiv=\"Cross-Origin-Resource-Policy\" content=\"same-origin\" />
  <meta http-equiv=\"Cross-Origin-Embedder-Policy\" content=\"require-corp\" />
</head>
<body>
  <h1>Panel Local Engine - {cp_id}</h1>
  <div style="margin:6px 0 14px; color:#636e72; font-size:14px;">
    Atajo: pulsa <strong>1</strong> para confirmar el inicio (si está disponible). Pulsa <strong>Q</strong> para cancelar.
  </div>
  <div class=\"row\">
    <button id=\"btn-start\" class=\"ok\" style=\"display:none\" onclick=\"post('/api/iniciar_suministro')\">🔌 Confirmar Inicio (Invoke-WebRequest)</button>
    <button id=\"btn-stop\" class=\"danger\" style=\"display:none\" onclick=\"post('/api/solicitar_fin')\">🛑 Solicitar Fin</button>
    <button id=\"btn-sync\" class=\"warn\" style=\"display:none\" onclick=\"post('/api/forzar_esperando')\">🛠️ Sincronizar ESPERANDO_DRIVER</button>
    <button id=\"btn-averia\" class=\"danger\" onclick=\"simularAveria()\">⚠️ Simular Avería</button>
    <button id=\"btn-refresh\" class=\"muted\" onclick=\"estado()\">🔄 Actualizar Estado</button>
  </div>
  <div id=\"info-flujo\" style=\"margin:8px 0 16px; color:#2d3436; font-weight:600; display:none;\"></div>
  <div style=\"margin: 0 0 16px; color:#636e72; font-size:13px;\">
    Este botón simula ejecutar en PowerShell:
    <pre style=\"white-space: pre-wrap; background:#fff; padding:10px; border-radius:6px;\">Invoke-WebRequest -Method POST -Uri http://127.0.0.1:{web_port}/api/iniciar_suministro</pre>
    Para solicitar fin del suministro:
    <pre style=\"white-space: pre-wrap; background:#fff; padding:10px; border-radius:6px;\">Invoke-WebRequest -Method POST -Uri http://127.0.0.1:{web_port}/api/solicitar_fin</pre>
    Para simular una avería:
    <pre style=\"white-space: pre-wrap; background:#fff; padding:10px; border-radius:6px;\">$body = @{{activar=$true;motivo=\"Avería simulada\"}} | ConvertTo-Json; Invoke-WebRequest -Method POST -Uri http://127.0.0.1:{web_port}/api/simular_averia -ContentType \"application/json\" -Body $body</pre>
    Para recuperar el CP de una avería:
    <pre style=\"white-space: pre-wrap; background:#fff; padding:10px; border-radius:6px;\">Invoke-WebRequest -Method POST -Uri http://127.0.0.1:{web_port}/api/recuperar_averia</pre>
  </div>
  <h3>Estado</h3>
  <pre id=\"estado\">Cargando...</pre>
  <h3>Log</h3>
  <pre id=\"log\"></pre>
</body>
</html>
    """
    resp = make_response(html)
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/api/status')
def api_status():
    """Devuelve el estado actual del engine."""
    global TARGET_KWH, CURRENT_DRIVER_ID, ENGINE_CP_ID, ACTIVE_MONITOR_CONN, ESTADO_FLUJO
    
    print(f"[WEB API] ⭐ /api/status llamado")
    
    # Leer variables de sesión con lock
    with SESSION_LOCK:
        driver_actual = CURRENT_DRIVER_ID
        objetivo_kwh = TARGET_KWH
        print(f"[WEB API] 🔒 Dentro de SESSION_LOCK: driver={driver_actual}, objetivo={objetivo_kwh}")
    
    cp_id = ENGINE_CP_ID or 'CP_UNKNOWN'
    
    print(f"[WEB API] 📊 Valores leídos: driver={driver_actual}, objetivo={objetivo_kwh}")
    
    with STATE_LOCK:
        estado = {
            'cp_id': cp_id,
            'estado': obtener_estado_actual(),
            'cargando': CHARGING_FLAG.is_set(),
            'kw_acumulados': round(kw_acumulados_global, 2),
            'segundos': segundos_global,
            'driver_actual': driver_actual,
            'objetivo_kwh': objetivo_kwh,
            'monitor_conectado': ACTIVE_MONITOR_CONN is not None
        }
    
    with SIMULAR_AVERIA_LOCK:
        estado['averia_simulada'] = SIMULAR_AVERIA
    
    # Agregar estado del flujo interactivo
    with ESTADO_FLUJO_LOCK:
        estado_flujo_actual = ESTADO_FLUJO
        print(f"[WEB API] 🔒 Dentro de ESTADO_FLUJO_LOCK: estado_flujo={estado_flujo_actual}")

    # Salvaguarda: si hay driver y objetivo pero el flujo figura en REPOSO, forzar ESPERANDO_DRIVER
    try:
        if (not estado_flujo_actual or estado_flujo_actual == 'REPOSO') \
           and (driver_actual is not None and driver_actual != 'UNKNOWN') \
           and (objetivo_kwh is not None):
            print("[WEB API] 🛡️ Salvaguarda activada: derivando estado_flujo=ESPERANDO_DRIVER por sesión activa")
            estado_flujo_actual = 'ESPERANDO_DRIVER'
    except Exception:
        pass

    # Salvaguarda 2: si aún no hay driver/objetivo visibles pero existe AUTH reciente, exponerlos
    try:
        ahora = time.time()
        with AUTH_CACHE_LOCK:
            last_ts = globals().get('LAST_AUTH_TS', 0.0)
            last_driver = globals().get('LAST_AUTH_DRIVER_ID')
            last_obj = globals().get('LAST_AUTH_OBJ_KWH')
        if (driver_actual == 'UNKNOWN' or driver_actual is None or objetivo_kwh is None) and (ahora - last_ts <= 20.0):
            if last_driver:
                driver_actual = last_driver
            if last_obj is not None:
                objetivo_kwh = last_obj
            estado_flujo_actual = 'ESPERANDO_DRIVER'
            print(f"[WEB API] 🧭 Usando caché AUTH reciente para UI: driver={driver_actual}, objetivo={objetivo_kwh}")
    except Exception:
        pass

    # Actualizar campos con posibles derivaciones
    estado['driver_actual'] = driver_actual
    estado['objetivo_kwh'] = objetivo_kwh
    estado['estado_flujo'] = estado_flujo_actual
    
    # Debug: imprimir valores finales que se van a enviar
    print(f"[WEB API] ✅ Enviando respuesta JSON: estado_flujo={estado_flujo_actual}, driver={driver_actual}, objetivo={objetivo_kwh}")
    
    resp = jsonify(estado)
    # Evitar cacheo del JSON de estado
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/api/simular_averia', methods=['POST'])
def api_simular_averia():
    """Activa/desactiva la simulación de avería."""
    global SIMULAR_AVERIA
    
    data = request.get_json(silent=True)
    if not data:
        # Si no hay JSON, intentar leer como form data o usar valores por defecto
        activar = request.form.get('activar', 'true').lower() == 'true'
        motivo = request.form.get('motivo', 'Avería simulada desde web')
    else:
        activar = data.get('activar', True)
        motivo = data.get('motivo', 'Avería simulada desde web')
    
    with SIMULAR_AVERIA_LOCK:
        SIMULAR_AVERIA = activar
    
    cp_id = globals().get('ENGINE_CP_ID') or 'CP_UNKNOWN'
    
    if activar:
        print(f"\n{'='*70}")
        print(f"  [{cp_id}] ⚠️  AVERÍA SIMULADA ACTIVADA")
        print(f"  Motivo: {motivo}")
        print(f"{'='*70}\n")
        mensaje = f"Avería simulada activada: {motivo}"
    else:
        print(f"\n{'='*70}")
        print(f"  [{cp_id}] ✓ AVERÍA SIMULADA DESACTIVADA")
        print(f"{'='*70}\n")
        mensaje = "Avería simulada desactivada"
    
    return jsonify({
        'status': 'ok',
        'averia_activa': SIMULAR_AVERIA,
        'mensaje': mensaje
    })

@app.route('/api/recuperar_averia', methods=['POST'])
def api_recuperar_averia():
    """Recupera el CP de una avería: desactiva avería local y notifica a Central via Monitor."""
    global SIMULAR_AVERIA, ACTIVE_MONITOR_CONN, ENGINE_CP_ID
    cp_id = globals().get('ENGINE_CP_ID') or 'CP_UNKNOWN'
    
    print(f"\n{'='*70}")
    print(f"  [{cp_id}] 🔧 RECUPERACIÓN DE AVERÍA SOLICITADA")
    print(f"{'='*70}\n")
    
    # Verificar estado actual de avería
    averia_anterior = False
    with SIMULAR_AVERIA_LOCK:
        averia_anterior = SIMULAR_AVERIA
        SIMULAR_AVERIA = False
        print(f"[{cp_id}] ✓ Avería desactivada localmente (estado anterior: {averia_anterior})")
    
    # Notificar a Central a través del Monitor
    notificacion_enviada = False
    try:
        if ACTIVE_MONITOR_CONN is None:
            print(f"[{cp_id}] ⚠️ No hay conexión con el Monitor para notificar la recuperación")
            print(f"[{cp_id}] ✅ Avería desactivada localmente. El CP volverá a responder OK a los chequeos de salud")
            print(f"{'='*70}\n")
            # Aunque no haya conexión con el Monitor, la avería se desactivó correctamente
            respuesta = jsonify({
                'status': 'ok',
                'mensaje': 'Recuperación completada. Avería desactivada localmente. No se pudo notificar a Central (sin conexión con Monitor)',
                'averia_anterior': averia_anterior,
                'averia_actual': False,
                'notificacion_central': False
            })
        else:
            # AVR_CLR#<cp_id>#<motivo>#<codigo>
            trama = construir_trama('AVR_CLR', [cp_id, 'RECUPERADA', 'OK'])
            ACTIVE_MONITOR_CONN.sendall(trama)
            print(f"[{cp_id}] 📤 AVR_CLR enviado a Central a través del Monitor")
            print(f"[{cp_id}] ✅ Recuperación completada. El CP volverá a estado ACTIVADO")
            print(f"{'='*70}\n")
            notificacion_enviada = True
            respuesta = jsonify({
                'status': 'ok',
                'mensaje': 'Recuperación completada. Avería desactivada y notificada a Central. Estado volverá a ACTIVADO',
                'averia_anterior': averia_anterior,
                'averia_actual': False,
                'notificacion_central': True
            })
        
        # Evitar cacheo de la respuesta
        respuesta.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        respuesta.headers['Pragma'] = 'no-cache'
        respuesta.headers['Expires'] = '0'
        return respuesta
    except Exception as e:
        print(f"[{cp_id}] ❌ Error notificando recuperación: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'mensaje': f'Error notificando recuperación: {str(e)}'
        }), 500

@app.route('/api/iniciar_suministro', methods=['POST'])
def api_iniciar_suministro():
    """Operador del Engine inicia el suministro (envía READY_TO_START a Central)."""
    global ESTADO_FLUJO, ENGINE_CP_ID, ACTIVE_MONITOR_CONN, CURRENT_DRIVER_ID
    
    cp_id = ENGINE_CP_ID or 'CP_UNKNOWN'
    
    with ESTADO_FLUJO_LOCK:
        if ESTADO_FLUJO != 'ESPERANDO_DRIVER':
            # Permitir inicio si existe sesión activa aunque el estado no esté sincronizado
            with SESSION_LOCK:
                driver_tmp = CURRENT_DRIVER_ID
                objetivo_tmp = TARGET_KWH
            if not (driver_tmp and driver_tmp != 'UNKNOWN' and objetivo_tmp is not None):
                return jsonify({
                    'status': 'error',
                    'mensaje': f'No se puede iniciar. Estado actual: {ESTADO_FLUJO}'
                }), 400
            # Forzar transición para continuar
            ESTADO_FLUJO = 'LISTO_PARA_INICIAR'
        else:
            # Cambiar estado normal
            ESTADO_FLUJO = 'LISTO_PARA_INICIAR'
    
    print(f"\n{'='*70}")
    print(f"  [{cp_id}] 🔌 OPERADOR: Iniciando suministro")
    print(f"  Estado: ESPERANDO_DRIVER → LISTO_PARA_INICIAR")
    print(f"{'='*70}\n")
    
    # Enviar mensaje READY_TO_START al monitor
    try:
        if ACTIVE_MONITOR_CONN is None:
            with ESTADO_FLUJO_LOCK:
                ESTADO_FLUJO = 'ESPERANDO_DRIVER'
            return jsonify({
                'status': 'error',
                'mensaje': 'No hay conexión con el Monitor'
            }), 400
        
        with SESSION_LOCK:
            driver_id = CURRENT_DRIVER_ID
        
        trama = construir_trama('READY_TO_START', [cp_id, driver_id])
        ACTIVE_MONITOR_CONN.sendall(trama)
        
        print(f"[{cp_id}] 📤 READY_TO_START enviado a Monitor (Driver: {driver_id})")
        
        return jsonify({
            'status': 'ok',
            'mensaje': 'Señal enviada a Central. Esperando confirmación...',
            'nuevo_estado': 'LISTO_PARA_INICIAR'
        })
    except Exception as e:
        with ESTADO_FLUJO_LOCK:
            ESTADO_FLUJO = 'ESPERANDO_DRIVER'
        return jsonify({
            'status': 'error',
            'mensaje': f'Error enviando señal: {str(e)}'
        }), 500

@app.route('/api/solicitar_fin', methods=['POST'])
def api_solicitar_fin():
    """Operador del Engine solicita fin de suministro (envía REQUEST_STOP a Central)."""
    global ESTADO_FLUJO, ENGINE_CP_ID, ACTIVE_MONITOR_CONN, CURRENT_DRIVER_ID
    
    cp_id = ENGINE_CP_ID or 'CP_UNKNOWN'
    
    with ESTADO_FLUJO_LOCK:
        if ESTADO_FLUJO != 'CARGANDO':
            return jsonify({
                'status': 'error',
                'mensaje': f'No se puede solicitar fin. Estado actual: {ESTADO_FLUJO}'
            }), 400
        
        # Cambiar estado
        ESTADO_FLUJO = 'ESPERANDO_CONFIRMACION_FIN'
    
    with STATE_LOCK:
        kw_actual = round(kw_acumulados_global, 2)
        segundos = segundos_global
    
    print(f"\n{'='*70}")
    print(f"  [{cp_id}] 🛑 OPERADOR: Solicitando fin de suministro")
    print(f"  Estado: CARGANDO → ESPERANDO_CONFIRMACION_FIN")
    print(f"  kWh actual: {kw_actual}, Tiempo: {segundos}s")
    print(f"{'='*70}\n")
    
    # Enviar mensaje REQUEST_STOP al monitor
    try:
        if ACTIVE_MONITOR_CONN is None:
            with ESTADO_FLUJO_LOCK:
                ESTADO_FLUJO = 'CARGANDO'
            return jsonify({
                'status': 'error',
                'mensaje': 'No hay conexión con el Monitor'
            }), 400
        
        with SESSION_LOCK:
            driver_id = CURRENT_DRIVER_ID
        
        trama = construir_trama('REQUEST_STOP', [cp_id, driver_id, str(kw_actual), str(segundos)])
        ACTIVE_MONITOR_CONN.sendall(trama)
        
        print(f"[{cp_id}] 📤 REQUEST_STOP enviado a Monitor")
        
        return jsonify({
            'status': 'ok',
            'mensaje': 'Solicitud de fin enviada a Central. Esperando confirmación...',
            'nuevo_estado': 'ESPERANDO_CONFIRMACION_FIN',
            'kw_actual': kw_actual,
            'segundos': segundos
        })
    except Exception as e:
        with ESTADO_FLUJO_LOCK:
            ESTADO_FLUJO = 'CARGANDO'
        return jsonify({
            'status': 'error',
            'mensaje': f'Error enviando solicitud: {str(e)}'
        }), 500

@app.route('/api/forzar_esperando', methods=['POST'])
def api_forzar_esperando():
    """Sincroniza el estado a ESPERANDO_DRIVER si hay sesión activa (uso operador)."""
    global ESTADO_FLUJO
    try:
        with SESSION_LOCK:
            driver_tmp = CURRENT_DRIVER_ID
            objetivo_tmp = TARGET_KWH
        if not (driver_tmp and driver_tmp != 'UNKNOWN' and objetivo_tmp is not None):
            return jsonify({
                'status': 'error',
                'mensaje': 'No hay sesión activa para sincronizar'
            }), 400
        with ESTADO_FLUJO_LOCK:
            ESTADO_FLUJO = 'ESPERANDO_DRIVER'
        return jsonify({
            'status': 'ok',
            'mensaje': 'Estado forzado a ESPERANDO_DRIVER'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'mensaje': str(e)
        }), 500

@app.route('/api/conectar_driver', methods=['POST'])
def api_conectar_driver():
    """Simula la conexión física de un driver (enchufar) - DEPRECADO en nuevo flujo."""
    cp_id = globals().get('ENGINE_CP_ID') or 'CP_UNKNOWN'
    
    data = request.get_json()
    driver_id = data.get('driver_id', 'DRIVER_WEB')
    
    print(f"\n{'='*70}")
    print(f"  [{cp_id}] 🔌 SIMULACIÓN: Driver conectado desde web")
    print(f"  Driver ID: {driver_id}")
    print(f"{'='*70}\n")
    
    # Enviar estado PLUGGED al monitor
    enviar_estado_al_monitor('PLUGGED')
    
    return jsonify({
        'status': 'ok',
        'mensaje': f'Conexión de driver {driver_id} simulada. Estado PLUGGED enviado al monitor.'
    })

@app.route('/api/desconectar_driver', methods=['POST'])
def api_desconectar_driver():
    """Simula la desconexión física de un driver (desenchufar)."""
    cp_id = globals().get('ENGINE_CP_ID') or 'CP_UNKNOWN'
    
    print(f"\n{'='*70}")
    print(f"  [{cp_id}] 🔓 SIMULACIÓN: Driver desconectado desde web")
    print(f"{'='*70}\n")
    
    try:
        # Detener carga si está activa
        with STATE_LOCK:
            if 'TELEMETRY_STOP_EVENT' in globals() and TELEMETRY_STOP_EVENT:
                TELEMETRY_STOP_EVENT.set()
                CHARGING_FLAG.clear()
        
        # Enviar estado UNPLUGGED al monitor
        enviar_estado_al_monitor('UNPLUGGED')
        
        return jsonify({
            'status': 'ok',
            'mensaje': 'Desconexión simulada. Estado UNPLUGGED enviado al monitor.'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'mensaje': str(e)
        }), 500

@app.route('/api/solicitar_cierre_suministro', methods=['POST'])
def api_solicitar_cierre_suministro():
    """DEPRECADO - Usar /api/solicitar_fin en su lugar."""
    # Redirigir al nuevo endpoint
    return api_solicitar_fin()

def iniciar_servidor_web(puerto: int):
    """Inicia el servidor Flask en un hilo separado."""
    print(f"[WEB] Iniciando servidor (solo endpoints) en puerto {puerto}...")
    app.run(host='0.0.0.0', port=puerto, debug=False, threaded=True, use_reloader=False)

def main():
    parser = argparse.ArgumentParser(description="Proceso EV_CP_E (Charging Point Engine)")
    parser.add_argument("--port", type=int, required=True, help="Puerto de escucha local")
    parser.add_argument("--cp-id", type=str, default="CP001", help="ID del Charging Point")
    parser.add_argument("--kafka", type=str, default=os.getenv('KAFKA_SERVER', '127.0.0.1:9092'), help="Broker Kafka (IP:puerto)")
    parser.add_argument("--web-port", type=int, help="Puerto para la interfaz web (default: 9000 + número del CP)")
    args = parser.parse_args()
    
    # Configurar broker Kafka efectivo y productor
    global KAFKA_SERVER, WEB_PORT
    KAFKA_SERVER = args.kafka
    initialize_producer(KAFKA_SERVER)
    
    # Determinar puerto web
    if args.web_port:
        WEB_PORT = args.web_port
    else:
        # Extraer número del CP_ID (ej: CP001 -> 1, CP002 -> 2)
        try:
            cp_num = int(''.join(filter(str.isdigit, args.cp_id)))
            WEB_PORT = 9000 + cp_num
        except:
            WEB_PORT = 9000
    
    print("="*40)
    print("[EV_CP_E] INICIADO")
    print(f"Puerto de escucha: {args.port}")
    print(f"CP ID: {args.cp_id}")
    print(f"Kafka: {KAFKA_SERVER}")
    print(f"Puerto Web: {WEB_PORT}")
    print("="*40)

    # El hilo de telemetría NO se inicia en arranque; solo tras recibir START
    print(f"[EV_CP_E] Telemetría en reposo. A la espera de START para {args.cp_id}")
    
    # Iniciar hilo de telemetría periódica para reportar estado (incluyendo avería) incluso sin carga
    TELEMETRY_PERIODIC_STOP_EVENT = threading.Event()
    telemetry_periodic_thread = threading.Thread(
        target=bucle_telemetria_periodica,
        args=(args.cp_id, TELEMETRY_PERIODIC_STOP_EVENT),
        daemon=True
    )
    telemetry_periodic_thread.start()
    print(f"[EV_CP_E] Hilo de telemetría periódica iniciado (reporta estado cada 10s)")

    try:
        # Guardar CP_ID global para el menú/estado
        globals()['ENGINE_CP_ID'] = args.cp_id
        
        # Iniciar servidor web en hilo separado
        web_thread = threading.Thread(target=iniciar_servidor_web, args=(WEB_PORT,), daemon=True)
        web_thread.start()
        print(f"[ENGINE] Interfaz web disponible en http://localhost:{WEB_PORT}")
        # Abrir automáticamente el panel local de este Engine
        try:
            webbrowser.open_new_tab(f"http://localhost:{WEB_PORT}/panel_local")
        except Exception:
            pass
        
        # Lanzar menú interactivo solo si hay TTY; si no, evitar bucle de prompts
        if sys.stdin and sys.stdin.isatty():
            menu_thread = threading.Thread(target=menu_interactivo_engine, daemon=True)
            menu_thread.start()
        else:
            print("[ENGINE] Menú deshabilitado (STDIN no interactivo). Use el Monitor para PLUG/STOP.")
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('', args.port))
        server_socket.listen(1)
        # Configurar timeout para no bloquear indefinidamente
        server_socket.settimeout(5.0)
        
        print(f"[EV_CP_E] Servidor escuchando en TCP (:{args.port}). Esperando Monitor...")
        
        # Bucle para aceptar conexiones (reconexión automática)
        while True:
            try:
                conn, addr = server_socket.accept()
                # Una vez conectado, quitar timeout para la comunicación
                conn.settimeout(None)
                print(f"[EV_CP_E] Monitor conectado desde {addr[0]}:{addr[1]}")
                handle_monitor_connection(conn, addr, args.cp_id)
                # Si la conexión se cierra, volver a esperar
                print(f"[EV_CP_E] Conexión cerrada. Esperando nueva conexión del Monitor...")
            except socket.timeout:
                # Timeout de accept(), seguir esperando
                continue
            except KeyboardInterrupt:
                raise
        
    except KeyboardInterrupt:
        print("\n[EV_CP_E] Apagando...")
    except Exception as e:
        print(f"[EV_CP_E] Error principal: {e}")
    finally:
        if 'server_socket' in locals():
            server_socket.close()

if __name__ == "__main__":
    main()