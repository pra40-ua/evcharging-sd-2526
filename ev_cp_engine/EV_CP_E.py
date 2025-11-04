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

# Estados del Engine
ENGINE_FAULTED = threading.Event()  # Indica si hay avería
VEHICLE_PLUGGED = threading.Event()  # Indica si vehículo está conectado físicamente
AUTHORIZED_TO_CHARGE = threading.Event()  # Indica si Central ha autorizado

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
                # Verificar si hay avería
                if ENGINE_FAULTED.is_set():
                    status = "KO"
                else:
                    status = "OK"
                
                respuesta = construir_trama('HCK_RESP', [status])
                conn.sendall(respuesta)
                
                # Mostrar solo si hay cambio de estado o avería
                if status == "KO":
                    print(f"[{cp_id}] ⚠️  HCK_RESP enviado: KO (AVERÍA ACTIVA)")
                # HCK con OK es muy frecuente, no mostrar para no saturar la pantalla
            elif cod_op == 'CMD':
                orden = (campos[0] if campos else '').upper()
                if orden == 'START':
                    # Verificar que no hay avería
                    if ENGINE_FAULTED.is_set():
                        print(f"\n[{cp_id}] ✗ No se puede iniciar suministro: CP en AVERÍA")
                        respuesta = construir_trama('ACK', ['START_FAILED_FAULT'])
                        conn.sendall(respuesta)
                        continue
                    
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
                    
                    print(f"\n{'='*70}")
                    print(f"  [{cp_id}] 📩 MENSAJE RECIBIDO: CMD START")
                    print(f"  Driver: {driver_id}")
                    print(f"  Objetivo: {kw_objetivo} kWh" if kw_objetivo else "  Objetivo: Sin límite")
                    print(f"{'='*70}\n")
                    
                    # Marcar que Central ha autorizado
                    AUTHORIZED_TO_CHARGE.set()
                    
                    # Verificar si el vehículo ya está conectado físicamente
                    if not VEHICLE_PLUGGED.is_set():
                        print(f"[{cp_id}] ⏳ CENTRAL ha AUTORIZADO la carga")
                        print(f"[{cp_id}] ⏳ ESPERANDO que el conductor conecte el vehículo...")
                        print(f"[{cp_id}] ℹ️  (Presiona '1' en el menú para simular conexión física)")
                        
                        # Guardar la sesión pero NO iniciar suministro aún
                        global CURRENT_DRIVER_ID, TARGET_KWH
                        CURRENT_DRIVER_ID = driver_id
                        TARGET_KWH = kw_objetivo
                        
                        respuesta = construir_trama('ACK', ['START_WAITING_PLUG'])
                        conn.sendall(respuesta)
                        print(f"[{cp_id}] 📤 ACK enviado: Esperando conexión física\n")
                        continue
                    
                    # Si el vehículo YA está conectado, iniciar suministro
                    print(f"[{cp_id}] ✓ Vehículo ya conectado físicamente")
                    print(f"[{cp_id}] ✓ Central ha autorizado")
                    print(f"[{cp_id}] ⚡ INICIANDO SUMINISTRO...")
                    
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
            print(f"[{cp_id}] No hay conexión con Monitor para enviar STATE.")
            return
        trama_state = construir_trama('STATE', [cp_id, estado])
        conn.sendall(trama_state)
        print(f"[{cp_id}] 📤 STATE enviado al Monitor: {estado}")
        
        # Si es PLUGGED y ya hay autorización, verificar inicio automático
        if estado == 'PLUGGED' and AUTHORIZED_TO_CHARGE.is_set():
            print(f"[{cp_id}] ✓ Condiciones cumplidas: Vehículo conectado + Autorización")
            print(f"[{cp_id}] ⚡ El Monitor iniciará el suministro...")
            
    except Exception as e:
        print(f"[{cp_id}] Error enviando STATE al Monitor: {e}")


def obtener_estado_actual() -> str:
    """Retorna el estado actual del CP como string legible."""
    try:
        # Verificar avería primero
        if ENGINE_FAULTED.is_set():
            return "AVERÍA (Faulted)"
        
        conn = globals().get('ACTIVE_MONITOR_CONN')
        if conn is None:
            return "DESCONECTADO (Sin Monitor)"
        
        with STATE_LOCK:
            if CHARGING_FLAG.is_set():
                return f"CARGANDO ({kw_acumulados_global:.2f} kWh, {segundos_global}s)"
            elif AUTHORIZED_TO_CHARGE.is_set() and not VEHICLE_PLUGGED.is_set():
                return "AUTORIZADO (Esperando conexión física del vehículo)"
            elif VEHICLE_PLUGGED.is_set() and not AUTHORIZED_TO_CHARGE.is_set():
                return "VEHÍCULO CONECTADO (Esperando autorización de Central)"
            elif CURRENT_DRIVER_ID and CURRENT_DRIVER_ID != 'UNKNOWN':
                return "PRE-SUMINISTRO (Sesión activa)"
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
    print("\n  ACCIONES DISPONIBLES:")
    print("    [1] Conectar vehículo físicamente (PLUG)")
    print("    [2] Reportar AVERÍA (Fault)")
    print("    [3] Desconectar vehículo (UNPLUG)")
    print("    [9] Mostrar estado actual")
    print("    [0] Ayuda")
    print("="*70)

def reportar_averia_al_monitor() -> None:
    """Reporta avería al Monitor mediante mensaje HCK_RESP con KO."""
    try:
        conn = globals().get('ACTIVE_MONITOR_CONN')
        cp_id = globals().get('ENGINE_CP_ID') or 'CP_UNKNOWN'
        
        if conn is None:
            print(f"[{cp_id}] ✗ No hay conexión con Monitor para reportar avería.")
            return
        
        # Detener cualquier carga en curso
        with STATE_LOCK:
            if TELEMETRY_STOP_EVENT:
                TELEMETRY_STOP_EVENT.set()
            CHARGING_FLAG.clear()
        
        # Marcar estado de avería
        ENGINE_FAULTED.set()
        AUTHORIZED_TO_CHARGE.clear()
        VEHICLE_PLUGGED.clear()
        
        print(f"\n{'='*70}")
        print(f"  [{cp_id}] ⚠️  AVERÍA REPORTADA")
        print(f"{'='*70}")
        print(f"  Estado: FAULTED")
        print(f"  Suministro: DETENIDO")
        print(f"  Notificando a Monitor...")
        print(f"{'='*70}\n")
        
        # El Monitor detectará KO en el siguiente HCK y notificará a Central
        # No necesitamos enviar mensaje especial, el HCK_RESP con KO lo hará
        
    except Exception as e:
        print(f"[ENGINE] ✗ Error reportando avería: {e}")


def menu_interactivo_engine() -> None:
    """Menú interactivo limitado para simular acciones físicas del CP."""
    cp_id = globals().get('ENGINE_CP_ID') or 'CP_UNKNOWN'
    mostrar_interfaz_cp(cp_id)
    
    while True:
        try:
            cmd = input(f"\n[{cp_id}] Acción: ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n[{cp_id}] Saliendo del menú...")
            break
        except Exception:
            time.sleep(0.5)
            continue
            
        if not cmd:
            continue
            
        if cmd == '0':
            mostrar_interfaz_cp(cp_id)
            continue
            
        if cmd == '9':
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
            print(f"  Vehículo enchufado: {'Sí' if VEHICLE_PLUGGED.is_set() else 'No'}")
            print(f"  Autorizado por Central: {'Sí' if AUTHORIZED_TO_CHARGE.is_set() else 'No'}")
            print(f"  En avería: {'Sí' if ENGINE_FAULTED.is_set() else 'No'}")
            print(f"{'='*70}")
            continue
            
        if cmd == '1':
            if ENGINE_FAULTED.is_set():
                print(f"\n[{cp_id}] ✗ No se puede conectar vehículo: CP en AVERÍA")
                print(f"[{cp_id}] Primero debe resolverse la avería")
                continue
                
            print(f"\n[{cp_id}] 🔌 Conductor CONECTA vehículo físicamente...")
            VEHICLE_PLUGGED.set()
            
            # Verificar si ya hay autorización de Central
            if AUTHORIZED_TO_CHARGE.is_set():
                print(f"[{cp_id}] ✓ Vehículo conectado + Autorización previa detectada")
                print(f"[{cp_id}] ⚡ INICIANDO SUMINISTRO automáticamente...")
                # El suministro real se inicia cuando el Monitor envíe START
                enviar_estado_al_monitor('PLUGGED')
            else:
                print(f"[{cp_id}] ✓ Vehículo conectado físicamente")
                print(f"[{cp_id}] ⏳ Esperando autorización de la CENTRAL...")
                enviar_estado_al_monitor('PLUGGED')
            continue
            
        if cmd == '2':
            print(f"\n[{cp_id}] ⚠️  REPORTANDO AVERÍA...")
            reportar_averia_al_monitor()
            print(f"[{cp_id}] ✓ Avería reportada. Monitor notificará a la Central.")
            continue
            
        if cmd == '3':
            if ENGINE_FAULTED.is_set():
                print(f"\n[{cp_id}] ℹ️  CP en AVERÍA. Desconexión de vehículo registrada.")
                VEHICLE_PLUGGED.clear()
                continue
                
            print(f"\n[{cp_id}] 🔓 Conductor DESCONECTA vehículo físicamente...")
            VEHICLE_PLUGGED.clear()
            
            # Detener carga si estaba activa
            try:
                with STATE_LOCK:
                    if TELEMETRY_STOP_EVENT:
                        TELEMETRY_STOP_EVENT.set()
                    CHARGING_FLAG.clear()
                AUTHORIZED_TO_CHARGE.clear()
                enviar_estado_al_monitor('UNPLUGGED')
                print(f"[{cp_id}] ✓ Vehículo desconectado. Carga detenida.")
            except Exception as e:
                print(f"[{cp_id}] ✗ Error al desconectar: {e}")
            continue
            
        print(f"[{cp_id}] ✗ Opción no válida: '{cmd}'. Usa '0' para ver el menú.")

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