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
    print(f"[ENGINE] Monitor conectado desde {addr[0]}:{addr[1]}")
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
                # **Aquí puedes añadir lógica para simular un fallo (KO).**
                # Ejemplo: status = "KO" si una bandera interna lo indica.
                status = "OK" 
                
                respuesta = construir_trama('HCK_RESP', [status])
                conn.sendall(respuesta)
                # print(f"[ENGINE] Recibido HCK, Enviado: {status}") # (Opcional, si quieres ver el tráfico HCK)
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
                    print("[ENGINE] === START recibido: iniciando carga (telemetría activa) ===")
                    info_ack = 'START_OK'
                    if kw_objetivo is not None:
                        info_ack = f"START_OK {kw_objetivo}kWh"
                    respuesta = construir_trama('ACK', [info_ack])
                    conn.sendall(respuesta)
                elif orden == 'STOP':
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
                    
                    print("[ENGINE] === STOP recibido: deteniendo carga (telemetría detenida) ===")
                    
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
                        print(f"[{cp_id}] FIN enviado a Monitor (STOP manual). kWh={kw_final}, €={importe}, dur_s={secs_final}, tx={tx_id}")
                        
                        # Resetear contadores para la próxima sesión
                        print(f"[{cp_id}] Contadores reseteados. Listo para nuevo servicio.")
                    except Exception as e:
                        print(f"[{cp_id}] Error enviando FIN tras STOP: {e}")
                    
                    respuesta = construir_trama('ACK', ['STOP_OK'])
                    conn.sendall(respuesta)
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


def menu_interactivo_engine() -> None:
    """Menú simple para simular acciones físicas en el CP."""
    print("\n[ENGINE] Menú CP: 'p' Enchufar (Plug) | 'x' Detener (Stop) | 'h' Ayuda")
    while True:
        try:
            cmd = input("[ENGINE] Acción (p/x/h): ").strip().lower()
        except Exception:
            time.sleep(1)
            continue
        if not cmd:
            continue
        if cmd == 'h':
            print("[ENGINE] Opciones: p=Enchufar (avisar Monitor), x=Detener carga si activa")
            continue
        if cmd == 'p':
            enviar_estado_al_monitor('PLUGGED')
            continue
        if cmd == 'x':
            try:
                # Señal de stop local; el Monitor también puede ordenar STOP
                with STATE_LOCK:
                    if 'TELEMETRY_STOP_EVENT' in globals() and TELEMETRY_STOP_EVENT:
                        TELEMETRY_STOP_EVENT.set()
                        CHARGING_FLAG.clear()
                enviar_estado_al_monitor('UNPLUGGED')
            except Exception:
                pass
            continue
        print(f"[ENGINE] Comando desconocido: {cmd}")

def main():
    parser = argparse.ArgumentParser(description="Proceso EV_CP_E (Charging Point Engine)")
    parser.add_argument("--port", type=int, required=True, help="Puerto de escucha local")
    parser.add_argument("--cp-id", type=str, default="CP001", help="ID del Charging Point")
    parser.add_argument("--kafka", type=str, default=os.getenv('KAFKA_SERVER', '127.0.0.1:9092'), help="Broker Kafka (IP:puerto)")
    args = parser.parse_args()
    
    # Configurar broker Kafka efectivo y productor
    global KAFKA_SERVER
    KAFKA_SERVER = args.kafka
    initialize_producer(KAFKA_SERVER)
    
    print("="*40)
    print("[EV_CP_E] INICIADO")
    print(f"Puerto de escucha: {args.port}")
    print(f"CP ID: {args.cp_id}")
    print(f"Kafka: {KAFKA_SERVER}")
    print("="*40)

    # El hilo de telemetría NO se inicia en arranque; solo tras recibir START
    print(f"[EV_CP_E] Telemetría en reposo. A la espera de START para {args.cp_id}")

    try:
        # Guardar CP_ID global para el menú/estado
        globals()['ENGINE_CP_ID'] = args.cp_id
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