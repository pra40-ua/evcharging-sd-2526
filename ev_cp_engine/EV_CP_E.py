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
            elif cod_op == 'AUTH_REQ':
                # Nuevo mensaje: Central autorizó un driver, pero NO inicia automáticamente
                # AUTH_REQ#<driver_id>#<kw_objetivo>
                try:
                    driver_id = campos[0] if len(campos) > 0 else 'UNKNOWN'
                    kw_objetivo = campos[1] if len(campos) > 1 else '0'
                    
                    print(f"\n{'='*70}")
                    print(f"  [{cp_id}] 📩 MENSAJE RECIBIDO: AUTH_REQ")
                    print(f"  Driver: {driver_id}")
                    print(f"  Objetivo: {kw_objetivo} kWh")
                    print(f"{'='*70}\n")
                    
                    # Guardar datos de sesión
                    global TARGET_KWH, CURRENT_DRIVER_ID, ESTADO_FLUJO
                    TARGET_KWH = float(kw_objetivo) if kw_objetivo else None
                    CURRENT_DRIVER_ID = driver_id
                    
                    # Cambiar estado del flujo
                    with ESTADO_FLUJO_LOCK:
                        ESTADO_FLUJO = 'ESPERANDO_DRIVER'
                    
                    print(f"[{cp_id}] ⏳ Estado: REPOSO → ESPERANDO_DRIVER")
                    print(f"[{cp_id}] 👤 Driver autorizado: {driver_id}")
                    print(f"[{cp_id}] 🌐 Web: Botón 'Iniciar Suministro' ahora disponible")
                    
                    # Responder OK
                    respuesta = construir_trama('ACK', ['AUTH_OK'])
                    conn.sendall(respuesta)
                    
                except Exception as e:
                    print(f"[{cp_id}] Error procesando AUTH_REQ: {e}")
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
                        kw_objetivo = globals().get('TARGET_KWH')
                    if driver_id == 'UNKNOWN':
                        driver_id = globals().get('CURRENT_DRIVER_ID', 'UNKNOWN')
                    
                    # Inicializar sesión
                    global kw_acumulados_global, segundos_global, TARGET_KWH, CURRENT_DRIVER_ID
                    global SESSION_START_TS, CURRENT_TX_ID, ACTIVE_MONITOR_CONN
                    global TELEMETRY_STOP_EVENT, TELEMETRY_THREAD, ESTADO_FLUJO
                    
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
                    
                    global ESTADO_FLUJO
                    
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
            font-size: 16px;
        }
        .button-group p {
            color: #666;
            font-size: 13px;
            margin-bottom: 15px;
            line-height: 1.5;
        }
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            margin: 5px;
            transition: all 0.3s;
            display: inline-flex;
            align-items: center;
            gap: 8px;
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
            </div>
        </div>
        
        <div style="background: white; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; color: #666; font-size: 12px;">
            <strong>Última actualización:</strong> <span id="last-update">-</span>
        </div>
    </div>
    
    <script>
        let updateInterval;
        let estadoAveria = false;
        
        function actualizarEstado() {{
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {{
                    // Actualizar estado del flujo
                    document.getElementById('status-estado').textContent = data.estado_flujo || data.estado || '-';
                    document.getElementById('status-monitor').innerHTML = data.monitor_conectado 
                        ? '<span class="badge badge-ok">Conectado</span>' 
                        : '<span class="badge badge-ko">Desconectado</span>';
                    document.getElementById('status-kwh').textContent = data.kw_acumulados.toFixed(2);
                    document.getElementById('status-tiempo').textContent = data.segundos;
                    document.getElementById('status-driver').textContent = data.driver_actual || '-';
                    document.getElementById('status-objetivo').textContent = data.objetivo_kwh ? data.objetivo_kwh + ' kWh' : '-';
                    
                    // Actualizar botones según estado del flujo
                    actualizarBotonesFlujo(data.estado_flujo, data);
                    
                    // Estado de avería
                    estadoAveria = data.averia_simulada;
                    if (estadoAveria) {{
                        document.getElementById('btn-activar-averia').style.display = 'none';
                        document.getElementById('btn-desactivar-averia').style.display = 'inline-flex';
                        document.getElementById('averia-status').innerHTML = 
                            '<span class="badge badge-ko">AVERÍA ACTIVA</span> - Respondiendo KO al monitor';
                    }} else {{
                        document.getElementById('btn-activar-averia').style.display = 'inline-flex';
                        document.getElementById('btn-desactivar-averia').style.display = 'none';
                        document.getElementById('averia-status').innerHTML = 
                            '<span class="badge badge-ok">NORMAL</span> - Respondiendo OK al monitor';
                    }}
                    
                    const now = new Date();
                    document.getElementById('last-update').textContent = now.toLocaleTimeString('es-ES');
                }})
                .catch(error => console.error('Error:', error));
        }}
        
        function mostrarAlerta(mensaje, tipo) {{
            const container = document.getElementById('alert-container');
            const alert = document.createElement('div');
            alert.className = `alert alert-${{tipo}} show`;
            alert.textContent = mensaje;
            container.appendChild(alert);
            setTimeout(() => {{
                alert.classList.remove('show');
                setTimeout(() => alert.remove(), 300);
            }}, 5000);
        }}
        
        function actualizarBotonesFlujo(estadoFlujo, data) {{
            const contenedor = document.getElementById('flujo-container');
            let html = '';
            
            if (estadoFlujo === 'ESPERANDO_DRIVER') {{
                html = `
                    <div class="button-group" style="background: #e8f5e9;">
                        <h3>✅ Driver Autorizado</h3>
                        <p><strong>Driver:</strong> ${{data.driver_actual}}<br>
                           <strong>Objetivo:</strong> ${{data.objetivo_kwh || '?'}} kWh</p>
                        <p>La Central ha autorizado este driver. Pulsa el botón cuando el vehículo esté listo para iniciar la carga.</p>
                        <button class="btn btn-success" onclick="iniciarSuministro()">
                            <span>🔌</span> Iniciar Suministro
                        </button>
                    </div>`;
            }}
            else if (estadoFlujo === 'LISTO_PARA_INICIAR') {{
                html = `
                    <div class="button-group" style="background: #fff3cd;">
                        <h3>⏳ Esperando Confirmación de Central</h3>
                        <p>Señal enviada a la Central. El operador de Central debe confirmar el inicio del suministro.</p>
                        <div style="text-align: center; padding: 20px;">
                            <div class="spinner"></div>
                            <p style="margin-top: 10px; color: #856404;">Aguardando confirmación...</p>
                        </div>
                    </div>`;
            }}
            else if (estadoFlujo === 'CARGANDO') {{
                const progreso = data.objetivo_kwh ? ((data.kw_acumulados / data.objetivo_kwh) * 100).toFixed(1) : 0;
                html = `
                    <div class="button-group" style="background: #d1ecf1;">
                        <h3>⚡ Suministro en Progreso</h3>
                        <p><strong>Driver:</strong> ${{data.driver_actual}}<br>
                           <strong>Energía:</strong> ${{data.kw_acumulados.toFixed(2)}} / ${{data.objetivo_kwh || '∞'}} kWh (${{progreso}}%)<br>
                           <strong>Tiempo:</strong> ${{data.segundos}}s</p>
                        <button class="btn btn-danger" onclick="solicitarFin()">
                            <span>🛑</span> Solicitar Fin de Suministro
                        </button>
                    </div>`;
            }}
            else if (estadoFlujo === 'ESPERANDO_CONFIRMACION_FIN') {{
                html = `
                    <div class="button-group" style="background: #f8d7da;">
                        <h3>⏳ Esperando Confirmación de Fin</h3>
                        <p>Solicitud de fin enviada a la Central. El operador de Central debe confirmar el cierre del suministro.</p>
                        <p><strong>Energía actual:</strong> ${{data.kw_acumulados.toFixed(2)}} kWh<br>
                           <strong>Tiempo:</strong> ${{data.segundos}}s</p>
                        <div style="text-align: center; padding: 20px;">
                            <div class="spinner"></div>
                            <p style="margin-top: 10px; color: #721c24;">Aguardando confirmación de fin...</p>
                        </div>
                    </div>`;
            }}
            else {{
                html = `
                    <div class="button-group">
                        <h3>💤 En Reposo</h3>
                        <p>El punto de carga está disponible. Esperando solicitud de un driver desde la Central.</p>
                        <p style="color: #999; font-size: 12px; margin-top: 10px;">
                            Los drivers deben solicitar carga a través de su aplicación móvil.
                        </p>
                    </div>`;
            }}
            
            contenedor.innerHTML = html;
        }}
        
        function iniciarSuministro() {{
            if (!confirm('¿Iniciar el suministro? Se enviará señal a Central para confirmación.')) return;
            
            fetch('/api/iniciar_suministro', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }}
            }})
            .then(response => response.json())
            .then(data => {{
                mostrarAlerta(data.status === 'ok' ? data.mensaje : 'Error: ' + data.mensaje,
                             data.status === 'ok' ? 'success' : 'danger');
                actualizarEstado();
            }})
            .catch(error => mostrarAlerta('Error: ' + error, 'danger'));
        }}
        
        function solicitarFin() {{
            if (!confirm('¿Solicitar fin del suministro? Se enviará señal a Central para confirmación.')) return;
            
            fetch('/api/solicitar_fin', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }}
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.status === 'ok') {{
                    const msg = `${{data.mensaje}} (${{data.kw_actual}} kWh, ${{data.segundos}}s)`;
                    mostrarAlerta(msg, 'warning');
                }} else {{
                    mostrarAlerta('Error: ' + data.mensaje, 'danger');
                }}
                actualizarEstado();
            }})
            .catch(error => mostrarAlerta('Error: ' + error, 'danger'));
        }}
        
        function simularAveria(activar) {{
            const motivo = activar ? prompt('Motivo de la avería:', 'Fallo simulado') : '';
            if (activar && !motivo) return;
            
            fetch('/api/simular_averia', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ activar: activar, motivo: motivo || 'Avería simulada' }})
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.status === 'ok') {{
                    mostrarAlerta(data.mensaje, activar ? 'danger' : 'success');
                    actualizarEstado();
                }} else {{
                    mostrarAlerta('Error: ' + data.mensaje, 'danger');
                }}
            }})
            .catch(error => mostrarAlerta('Error: ' + error, 'danger'));
        }}
        
        function conectarDriver() {{
            const driverId = prompt('ID del Driver (opcional):', 'DRIVER_WEB') || 'DRIVER_WEB';
            fetch('/api/conectar_driver', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ driver_id: driverId }})
            }})
            .then(response => response.json())
            .then(data => {{
                mostrarAlerta(data.status === 'ok' ? data.mensaje : 'Error: ' + data.mensaje, 
                             data.status === 'ok' ? 'success' : 'danger');
                actualizarEstado();
            }})
            .catch(error => mostrarAlerta('Error: ' + error, 'danger'));
        }}
        
        function desconectarDriver() {{
            if (!confirm('¿Desconectar el driver actual?')) return;
            fetch('/api/desconectar_driver', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }}
            }})
            .then(response => response.json())
            .then(data => {{
                mostrarAlerta(data.status === 'ok' ? data.mensaje : 'Error: ' + data.mensaje,
                             data.status === 'ok' ? 'warning' : 'danger');
                actualizarEstado();
            }})
            .catch(error => mostrarAlerta('Error: ' + error, 'danger'));
        }}
        
        function cerrarSuministro() {{
            if (!confirm('¿Cerrar el suministro actual?')) return;
            fetch('/api/solicitar_cierre_suministro', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }}
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.status === 'ok') {{
                    const mensaje = `Suministro cerrado: ${{data.kw_final}} kWh, €${{data.importe}}, ${{data.duracion_s}}s`;
                    mostrarAlerta(mensaje, 'success');
                    actualizarEstado();
                }} else {{
                    mostrarAlerta('Error: ' + data.mensaje, 'danger');
                }}
            }})
            .catch(error => mostrarAlerta('Error: ' + error, 'danger'));
        }}
        
        actualizarEstado();
        updateInterval = setInterval(actualizarEstado, 2000);
    </script>
</body>
</html>"""

@app.route('/')
def index():
    """Página principal de control del engine."""
    cp_id = globals().get('ENGINE_CP_ID') or 'CP_UNKNOWN'
    print(f"[WEB] Acceso a interfaz web desde navegador para {cp_id}")
    try:
        # Usar replace en lugar de format para evitar problemas con las llaves de CSS/JS
        html = HTML_TEMPLATE.replace('__CP_ID__', cp_id)
        return html
    except Exception as e:
        print(f"[WEB] Error generando HTML: {e}")
        import traceback
        traceback.print_exc()
        return f"<html><body><h1>Error</h1><pre>{traceback.format_exc()}</pre></body></html>", 500

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
    
    # Agregar estado del flujo interactivo
    with ESTADO_FLUJO_LOCK:
        estado['estado_flujo'] = ESTADO_FLUJO
    
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

@app.route('/api/iniciar_suministro', methods=['POST'])
def api_iniciar_suministro():
    """Operador del Engine inicia el suministro (envía READY_TO_START a Central)."""
    global ESTADO_FLUJO
    cp_id = globals().get('ENGINE_CP_ID') or 'CP_UNKNOWN'
    
    with ESTADO_FLUJO_LOCK:
        if ESTADO_FLUJO != 'ESPERANDO_DRIVER':
            return jsonify({
                'status': 'error',
                'mensaje': f'No se puede iniciar. Estado actual: {ESTADO_FLUJO}'
            }), 400
        
        # Cambiar estado
        ESTADO_FLUJO = 'LISTO_PARA_INICIAR'
    
    print(f"\n{'='*70}")
    print(f"  [{cp_id}] 🔌 OPERADOR: Iniciando suministro")
    print(f"  Estado: ESPERANDO_DRIVER → LISTO_PARA_INICIAR")
    print(f"{'='*70}\n")
    
    # Enviar mensaje READY_TO_START al monitor
    try:
        conn = globals().get('ACTIVE_MONITOR_CONN')
        if conn is None:
            with ESTADO_FLUJO_LOCK:
                ESTADO_FLUJO = 'ESPERANDO_DRIVER'
            return jsonify({
                'status': 'error',
                'mensaje': 'No hay conexión con el Monitor'
            }), 400
        
        driver_id = globals().get('CURRENT_DRIVER_ID', 'UNKNOWN')
        trama = construir_trama('READY_TO_START', [cp_id, driver_id])
        conn.sendall(trama)
        
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
    global ESTADO_FLUJO
    cp_id = globals().get('ENGINE_CP_ID') or 'CP_UNKNOWN'
    
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
        conn = globals().get('ACTIVE_MONITOR_CONN')
        if conn is None:
            with ESTADO_FLUJO_LOCK:
                ESTADO_FLUJO = 'CARGANDO'
            return jsonify({
                'status': 'error',
                'mensaje': 'No hay conexión con el Monitor'
            }), 400
        
        driver_id = globals().get('CURRENT_DRIVER_ID', 'UNKNOWN')
        trama = construir_trama('REQUEST_STOP', [cp_id, driver_id, str(kw_actual), str(segundos)])
        conn.sendall(trama)
        
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