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
from kafka import KafkaProducer
import threading # Necesario si el Engine está corriendo en un bucle principal
import os

# Importaciones para la interfaz web
from flask import Flask, render_template, jsonify, request
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

    # Obtener información de sesión activa
    try:
        driver_id_sesion = globals().get('CURRENT_DRIVER_ID', 'UNKNOWN')
        tiene_sesion = driver_id_sesion != 'UNKNOWN' and estado_carga in ['CARGANDO', 'PRE-SUMINISTRO']
    except:
        driver_id_sesion = None
        tiene_sesion = False

    telemetria_msg = {
        'cp_id': cp_id,
        'timestamp': time.time(),
        'estado_carga': estado_carga,
        'estado': estado_carga,  # Agregar campo 'estado' también para compatibilidad
        'kw_entregados': kw_entregados,
        'energia_total': kw_entregados,  # Compatibilidad con diferentes lectores
        'potencia_actual': potencia_kw,
        'tiempo_carga_s': tiempo_carga_s,
        'tiene_sesion_activa': tiene_sesion,
        'driver_id_sesion': driver_id_sesion if tiene_sesion else None
    }

    try:
        # Envía el mensaje de forma asíncrona
        future = TELEMETRY_PRODUCER.send(TOPIC_TELEMETRY, value=telemetria_msg)
        # Opcional: Para verificar el envío (bloqueante, no recomendado en bucle rápido)
        # record_metadata = future.get(timeout=1) 
        # print(f"[{cp_id}] Telemetría enviada. Offset: {record_metadata.offset}")

    except Exception as e:
        print(f"[{cp_id}] ERROR al enviar telemetría a Kafka: {e}")

# --- ESTADO DE CARGA ---
CHARGING_FLAG = threading.Event()  # START activa, STOP desactiva
STATE_LOCK = threading.Lock()
kw_acumulados_global = 0.0
segundos_global = 0

# Objetivo y sesión
TARGET_KWH = None
CURRENT_DRIVER_ID = 'UNKNOWN'
SESSION_START_TS = None
CURRENT_TX_ID = None

# Conexión activa con Monitor (para poder enviar FIN desde el hilo de telemetría)
ACTIVE_MONITOR_CONN: socket.socket | None = None
ENGINE_CP_ID = None

# Estado de avería simulada (para responder KO en HCK)
SIMULAR_AVERIA = False
SIMULAR_AVERIA_LOCK = threading.Lock()

# Flask app para interfaz web
app = Flask(__name__)
CORS(app)
WEB_PORT = 9000  # Puerto por defecto, se configurará según el CP

def bucle_telemetria(cp_id: str, stop_event: threading.Event):
    """Emite telemetría de CARGANDO únicamente mientras dure la sesión (START..STOP)."""
    global kw_acumulados_global, segundos_global
    print(f"[{cp_id}] Bucle de telemetría de CARGANDO iniciado.")
    while not stop_event.is_set():
        time.sleep(1)
        with STATE_LOCK:
            segundos_global += 1
            kw_acumulados_global += 0.05
            estado = 'CARGANDO'
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
    # Declarar variables globales al inicio para evitar errores de ámbito
    global kw_acumulados_global, segundos_global, TELEMETRY_THREAD, TELEMETRY_STOP_EVENT
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
            elif cod_op == 'CMD':
                orden = (campos[0] if campos else '').upper()
                if orden == 'START':
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
                    # Inicializar sesión
                    global kw_acumulados_global, segundos_global, TARGET_KWH, CURRENT_DRIVER_ID
                    global SESSION_START_TS, CURRENT_TX_ID, ACTIVE_MONITOR_CONN
                    global TELEMETRY_STOP_EVENT, TELEMETRY_THREAD
                    
                    print(f"\n{'='*70}")
                    print(f"  [{cp_id}] 📩 MENSAJE RECIBIDO: CMD START")
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
                    
                    print(f"[{cp_id}] ⚡ CARGA INICIADA - Estado: CARGANDO")
                    info_ack = 'START_OK'
                    if kw_objetivo is not None:
                        info_ack = f"START_OK {kw_objetivo}kWh"
                    respuesta = construir_trama('ACK', [info_ack])
                    conn.sendall(respuesta)
                    print(f"\n{'='*70}")
                    print(f"  [{cp_id}] 📤 MENSAJE ENVIADO: ACK {info_ack}")
                    print(f"{'='*70}\n")
                elif orden == 'STOP':
                    print(f"\n{'='*70}")
                    print(f"  [{cp_id}] 📩 MENSAJE RECIBIDO: CMD STOP")
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
                    
                    print(f"[{cp_id}] 🛑 CARGA DETENIDA - Estado: REPOSO")
                    
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
                        motivo = 'Detenido manualmente'
                        
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

@app.route('/')
def index():
    """Página principal de control del engine."""
    cp_id = globals().get('ENGINE_CP_ID') or 'CP_UNKNOWN'
    return render_template('engine_control.html', cp_id=cp_id)

@app.route('/api/status')
def api_status():
    """Devuelve el estado actual del engine."""
    cp_id = globals().get('ENGINE_CP_ID') or 'CP_UNKNOWN'
    
    with STATE_LOCK:
        estado = {
            'cp_id': cp_id,
            'estado': obtener_estado_actual(),
            'cargando': CHARGING_FLAG.is_set(),
            'kw_acumulados': round(kw_acumulados_global, 2),
            'segundos': segundos_global,
            'driver_actual': globals().get('CURRENT_DRIVER_ID', 'UNKNOWN'),
            'objetivo_kwh': globals().get('TARGET_KWH'),
            'monitor_conectado': globals().get('ACTIVE_MONITOR_CONN') is not None
        }
    
    with SIMULAR_AVERIA_LOCK:
        estado['averia_simulada'] = SIMULAR_AVERIA
    
    return jsonify(estado)

@app.route('/api/simular_averia', methods=['POST'])
def api_simular_averia():
    """Activa/desactiva la simulación de avería."""
    global SIMULAR_AVERIA
    
    data = request.get_json()
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

@app.route('/api/conectar_driver', methods=['POST'])
def api_conectar_driver():
    """Simula la conexión física de un driver (enchufar)."""
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
    """Solicita el cierre del suministro actual."""
    cp_id = globals().get('ENGINE_CP_ID') or 'CP_UNKNOWN'
    
    print(f"\n{'='*70}")
    print(f"  [{cp_id}] 🛑 SOLICITUD: Cierre de suministro desde web")
    print(f"{'='*70}\n")
    
    try:
        # Obtener conexión con monitor
        conn = globals().get('ACTIVE_MONITOR_CONN')
        if conn is None:
            return jsonify({
                'status': 'error',
                'mensaje': 'No hay conexión con el Monitor'
            }), 400
        
        # Detener telemetría
        with STATE_LOCK:
            CHARGING_FLAG.clear()
            kw_final = round(kw_acumulados_global, 2)
            secs_final = segundos_global
            if 'TELEMETRY_STOP_EVENT' in globals() and TELEMETRY_STOP_EVENT:
                TELEMETRY_STOP_EVENT.set()
        
        # Enviar telemetría final
        generar_y_enviar_telemetria(
            cp_id=cp_id,
            estado_carga='REPOSO',
            kw_entregados=kw_final,
            tiempo_carga_s=secs_final,
            potencia_kw=0.0
        )
        
        # Enviar FIN al Monitor
        precio_kwh = 0.48
        importe = round(kw_final * precio_kwh, 2)
        driver_id = globals().get('CURRENT_DRIVER_ID', 'UNKNOWN')
        tx_id = globals().get('CURRENT_TX_ID') or f"TX-{cp_id}-{int(time.time())}"
        motivo = 'Cierre solicitado desde web'
        
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
        print(f"  [{cp_id}] 📤 FIN enviado al Monitor")
        print(f"  Energía: {kw_final} kWh")
        print(f"  Importe: €{importe}")
        print(f"  Duración: {secs_final}s")
        print(f"{'='*70}\n")
        
        return jsonify({
            'status': 'ok',
            'mensaje': 'Cierre de suministro solicitado',
            'kw_final': kw_final,
            'importe': importe,
            'duracion_s': secs_final
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'mensaje': str(e)
        }), 500

def iniciar_servidor_web(puerto: int):
    """Inicia el servidor Flask en un hilo separado."""
    print(f"[WEB] Iniciando servidor web del engine en puerto {puerto}...")
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

    try:
        # Guardar CP_ID global para el menú/estado
        globals()['ENGINE_CP_ID'] = args.cp_id
        
        # Iniciar servidor web en hilo separado
        web_thread = threading.Thread(target=iniciar_servidor_web, args=(WEB_PORT,), daemon=True)
        web_thread.start()
        print(f"[ENGINE] Interfaz web disponible en http://localhost:{WEB_PORT}")
        
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