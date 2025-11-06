import time
import argparse
import socket
import sys
import threading
from queue import Queue, Empty

# =================================================================
#                         FUNCIONES DE PROTOCOLO
# =================================================================
# Constantes de Protocolo
STX = b'\x02'
ETX = b'\x03'
DELIMITER = '#'
HCK_INTERVAL = 1 # Segundos entre cada HCK

def calcular_lrc(data_bytes: bytes) -> bytes:
    """Calcula el Longitudinal Redundancy Check (XOR de todos los bytes)."""
    lrc = 0
    for byte in data_bytes:
        lrc ^= byte
    return bytes([lrc])

def descomponer_trama(trama_bytes: bytes) -> tuple:
    # ... [Tu lógica robusta de descomponer_trama] ...
    if len(trama_bytes) < 4:
         return None, None
    
    lrc_recibido = trama_bytes[-1:] 
    data_con_etx = trama_bytes[1:-1]
    data_bytes = data_con_etx[:-1]
    
    if not (trama_bytes.startswith(STX) and data_con_etx.endswith(ETX)):
        return None, None
        
    lrc_calculado = calcular_lrc(data_bytes)
    if lrc_recibido != lrc_calculado:
        # Solo para depuración: print(f"Error LRC. Recibido: {lrc_recibido.hex()}, Calculado: {lrc_calculado.hex()}.")
        return None, None
        
    try:
        DATA = data_bytes.decode('utf-8')
        partes = DATA.split(DELIMITER)
        return partes[0], partes[1:]
    except UnicodeDecodeError:
        return None, None

def construir_trama(cod_op: str, campos: list) -> bytes:
    """Construye la trama completa del protocolo EV_CP_M."""
    DATA = f"{cod_op}#{DELIMITER.join(map(str, campos))}"
    DATA_bytes = DATA.encode('utf-8')
    LRC_byte = calcular_lrc(DATA_bytes)
    trama = STX + DATA_bytes + ETX + LRC_byte
    return trama

# =================================================================
#                     COLA DE ORDENES (STOP/START)
# =================================================================

# Cola compartida entre el hilo de escucha de la Central y el hilo HCK
COMMAND_QUEUE: Queue = Queue()

# Sesión actual (se establece al recibir AUTH_REQ de Central)
SESION_DRIVER_ID = None
SESION_KW_SOLICITADOS = None
WAITING_FOR_PLUG = False

# =================================================================
#                       LÓGICA DE COMUNICACIÓN CENTRAL
# =================================================================

def notificar_averia_central(central_socket: socket.socket, cp_id: str, motivo: str):
    """Envía un mensaje AVR (Avería/Estado ROJO) a la Central."""
    try:
        # Enviar el estado de AVERÍA
        trama_averia = construir_trama('AVR', [cp_id, motivo])
        central_socket.sendall(trama_averia)
        print(f"[{cp_id}] -> ENVIADO AVR a Central. Motivo: {motivo}")

    except Exception as e:
        print(f"[{cp_id}] ERROR al notificar avería a la Central: {e}. Conexión perdida.")
        # La conexión con Central está caída. El hilo de escucha ya debería manejar esto.


def enviar_orden_a_engine(engine_ip: str, engine_port: int, orden: str, cp_id: str) -> None:
    """Abre una conexión corta con el Engine para enviar una orden (CMD) y esperar ACK."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect((engine_ip, engine_port))
            trama_cmd = construir_trama('CMD', [orden])
            s.sendall(trama_cmd)

            resp = s.recv(1024)
            if not resp:
                print(f"[{cp_id}] Engine no respondió al comando {orden}.")
                return

            cod_op, campos = descomponer_trama(resp)
            if cod_op == 'ACK':
                detalle = campos[0] if campos else ''
                print(f"[{cp_id}] ACK del Engine recibido: {detalle}")
            else:
                print(f"[{cp_id}] Respuesta inesperada del Engine: {cod_op}")
    except Exception as e:
        print(f"[{cp_id}] Error enviando orden '{orden}' al Engine: {e}")

def conectar_y_registrar(central_ip: str, central_port: int, cp_id: str) -> socket.socket:
    """Conecta al EV_Central y realiza el registro. Retorna el socket conectado."""
    
    ubicacion_cp = "C/Mayor, 45"
    precio_kwh = "0.48"
    client_socket = None

    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Timeout de conexión para evitar bloqueos indefinidos
        client_socket.settimeout(10)
        
        print(f"[CP_M] Intentando conectar a EV_Central en {central_ip}:{central_port}...")
        
        try:
            client_socket.connect((central_ip, central_port))
        except socket.timeout:
            raise Exception(f"Timeout al conectar (10s). Verifica que EV_Central esté ejecutándose en {central_ip}:{central_port}")
        except ConnectionRefusedError:
            raise Exception(
                f"Connection refused. Posibles causas:\n"
                f"  1. EV_Central no está ejecutándose en {central_ip}:{central_port}\n"
                f"  2. El firewall de PC_A está bloqueando el puerto {central_port}\n"
                f"  3. La IP {central_ip} es incorrecta (debe ser la IP del PC_A, no 127.0.0.1)\n"
                f"  4. El contenedor de la Central no tiene el puerto 5000 mapeado correctamente"
            )
        except socket.gaierror as e:
            raise Exception(f"No se pudo resolver el hostname/IP {central_ip}: {e}")
        
        print("[CP_M] Conexión con Central establecida. Enviando REG...")
        
        # Quitar timeout para la comunicación posterior
        client_socket.settimeout(None)

        trama_registro = construir_trama('REG', [cp_id, ubicacion_cp, precio_kwh])
        client_socket.sendall(trama_registro)

        respuesta_bytes = client_socket.recv(1024)
        if not respuesta_bytes:
            raise Exception("No se recibió respuesta o Central cerró la conexión.")

        cod_op, campos = descomponer_trama(respuesta_bytes)
        
        print(f"[CP_M] Recibida respuesta bruta: {respuesta_bytes.decode(errors='ignore')}")

        if cod_op == 'AUTH' and campos and campos[0] == 'OK':
            print(f"[CP_M] ¡{cp_id} REGISTRO EXITOSO! Estado ACTIVADO. Mensaje: {campos[1]}")
            return client_socket 
        else:
            raise Exception(f"Fallo de autenticación. Respuesta inválida o AUTH#FAIL. Cod={cod_op}, Campos={campos}")

    except Exception as e:
        print(f"[CP_M] ERROR durante el registro: {e}")
        if client_socket:
            client_socket.close()
        raise

def escuchar_central(central_socket: socket.socket, cp_id: str, engine_ip: str, engine_port: int):
    """Bucle de escucha permanente para comandos síncronos de la Central."""
    print(f"[{cp_id}] Hilo de escucha de Central iniciado.")
    # NOTA: Necesitamos el socket del Engine para enviar la orden de START/STOP. 
    # Lo más limpio es reabrir la conexión brevemente o usar el hilo HCK.
    # Por ahora, vamos a notificar la recepción.
    
    try:
        while True:
            trama_bytes = central_socket.recv(1024)
            if not trama_bytes:
                print(f"[{cp_id}] Central cerró la conexión. Socket de comando cerrado.")
                break
            
            cod_op, campos = descomponer_trama(trama_bytes)
            
            if cod_op == 'AUTH_REQ':
                # AUTH_REQ#<driver_id>#<kw_deseados>
                try:
                    driver_id = campos[0] if len(campos) > 0 else 'UNKNOWN'
                    kw_deseados = campos[1] if len(campos) > 1 else '0'
                    print(f"[{cp_id}] <--- AUTH_REQ recibido de Central. Driver={driver_id}, kW={kw_deseados}")
                    # Guardar sesión actual
                    try:
                        globals()['SESION_DRIVER_ID'] = driver_id
                        globals()['SESION_KW_SOLICITADOS'] = float(kw_deseados)
                    except Exception:
                        globals()['SESION_DRIVER_ID'] = driver_id
                        globals()['SESION_KW_SOLICITADOS'] = None
                    # Marcar que estamos autorizados
                    globals()['WAITING_FOR_PLUG'] = True
                    
                    # NUEVO: Reenviar AUTH_REQ al Engine para que muestre el botón "Iniciar Suministro"
                    try:
                        print(f"[{cp_id}] 📤 Reenviando AUTH_REQ al Engine...")
                        trama_auth_engine = construir_trama('AUTH_REQ', [driver_id, kw_deseados])
                        # Encolar para envío en el siguiente ciclo HCK
                        COMMAND_QUEUE.put_nowait(('AUTH_REQ', time.time(), driver_id, kw_deseados))
                        print(f"[{cp_id}] ✓ AUTH_REQ encolado para Engine")
                    except Exception as e:
                        print(f"[{cp_id}] Error encolando AUTH_REQ para Engine: {e}")
                    
                    # Responder a la Central con autorización OK
                    resp = construir_trama('AUTH_RESP', [driver_id, 'OK', 'Autorizacion concedida'])
                    central_socket.sendall(resp)
                    print(f"[{cp_id}] ✓ AUTH_RESP enviado a Central. Esperando acción del operador del Engine...")
                except Exception as e:
                    print(f"[{cp_id}] Error procesando AUTH_REQ: {e}")
                continue

            if cod_op in ('STOP', 'START'):
                print(f"[{cp_id}] <--- COMANDO CENTRAL RECIBIDO: {cod_op}")
                # Encolamos la orden para que la ejecute el hilo HCK sobre su socket
                try:
                    if cod_op == 'START' and len(campos) >= 2:
                        # START con parámetros (driver_id, kw_deseados) desde comando manual de web
                        driver_id = campos[0] if len(campos) > 0 else None
                        kw_deseados = campos[1] if len(campos) > 1 else None
                        try:
                            kw_float = float(kw_deseados) if kw_deseados else None
                        except:
                            kw_float = None
                        COMMAND_QUEUE.put_nowait((cod_op, time.time(), kw_float, driver_id))
                        print(f"[{cp_id}] Orden '{cod_op}' encolada para Engine con parámetros: driver={driver_id}, kW={kw_float}")
                    else:
                        # STOP o START sin parámetros
                        COMMAND_QUEUE.put_nowait((cod_op, time.time(), None, None))
                        print(f"[{cp_id}] Orden '{cod_op}' encolada para Engine.")
                except Exception as e:
                    print(f"[{cp_id}] No se pudo encolar la orden {cod_op}: {e}")
                # Notificar inmediatamente a la Central el estado administrativo
                try:
                    nuevo_estado = 'PARADO' if cod_op == 'STOP' else 'ACTIVADO'
                    trama_state = construir_trama('STATE', [cp_id, nuevo_estado])
                    central_socket.sendall(trama_state)
                    print(f"[{cp_id}] STATE inmediato enviado a Central: {nuevo_estado}")
                except Exception as e:
                    print(f"[{cp_id}] Error enviando STATE a Central: {e}")

            else:
                 # Manejo de otros códigos, como AVR, o tramas inesperadas
                print(f"[{cp_id}] <--- Trama Central recibida (No comando): {cod_op}")


    except Exception as e:
        print(f"[{cp_id}] Error en hilo de escucha de Central: {e}")
    finally:
        central_socket.close()


def chequear_salud_engine(engine_ip: str, engine_port: int, central_socket: socket.socket, cp_id: str):
    """Hilo para enviar HCK al Engine cada 1 segundo y gestionar la respuesta."""
    engine_socket = None
    conexion_perdida_notificada = False

    while True:
        try:
            # 1. Intentar establecer/reestablecer conexión con el Engine
            if engine_socket is None:
                try:
                    print(f"[{cp_id}] Intentando conectar al Engine en {engine_ip}:{engine_port}...")
                    engine_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    engine_socket.settimeout(3.0)  # Timeout para el connect
                    engine_socket.connect((engine_ip, engine_port))
                    print(f"[{cp_id}] ✓ Conexión con Engine establecida.")
                    engine_socket.settimeout(HCK_INTERVAL * 0.8)
                    conexion_perdida_notificada = False
                except (ConnectionRefusedError, socket.timeout, OSError) as e:
                    if not conexion_perdida_notificada:
                        print(f"[{cp_id}] Engine no disponible aún. Reintentando cada {HCK_INTERVAL}s...")
                        conexion_perdida_notificada = True
                    if engine_socket:
                        engine_socket.close()
                    engine_socket = None
                    time.sleep(HCK_INTERVAL)
                    continue
            
            # 2. Antes de enviar HCK, consumir órdenes pendientes y enviarlas por el mismo socket
            #    Consumimos todas las que haya disponibles sin bloquear
            while True:
                try:
                    item = COMMAND_QUEUE.get_nowait()
                except Empty:
                    break
                try:
                    # item puede ser (orden, ts) o (orden, ts, param1, param2)
                    if isinstance(item, tuple) and len(item) >= 2:
                        orden = item[0]
                        ts = item[1]
                        param1 = item[2] if len(item) > 2 else None
                        param2 = item[3] if len(item) > 3 else None
                    else:
                        orden = str(item)
                        ts = time.time()
                        param1 = None
                        param2 = None

                    # Manejar AUTH_REQ especialmente (no es un CMD)
                    if orden == 'AUTH_REQ':
                        driver_id = param1
                        kw_deseados = param2
                        campos_auth = [driver_id, str(kw_deseados) if kw_deseados else '0']
                        trama_auth = construir_trama('AUTH_REQ', campos_auth)
                        engine_socket.sendall(trama_auth)
                        print(f"[{cp_id}] 📤 AUTH_REQ enviado al Engine (Driver: {driver_id}, kW: {kw_deseados})")
                        # El Engine procesará el AUTH_REQ internamente y responderá con ACK
                        # Leer la respuesta para limpiar el buffer
                        try:
                            resp_auth = engine_socket.recv(1024)
                            cod_resp, campos_resp = descomponer_trama(resp_auth)
                            if cod_resp == 'ACK':
                                print(f"[{cp_id}] ✓ Engine confirmó recepción de AUTH_REQ: {campos_resp[0] if campos_resp else 'OK'}")
                            else:
                                print(f"[{cp_id}] ⚠️ Respuesta inesperada a AUTH_REQ: {cod_resp}")
                        except Exception as e:
                            print(f"[{cp_id}] ⚠️ Error leyendo respuesta AUTH_REQ: {e}")
                        continue
                    
                    # Para START/STOP y otros comandos CMD
                    campos_cmd = [orden]
                    if orden == 'START' and param1 is not None:
                        # param1 es kw, param2 es driver
                        campos_cmd.append(str(param1))
                        if param2:
                            campos_cmd.append(str(param2))
                    trama_cmd = construir_trama('CMD', campos_cmd)
                    engine_socket.sendall(trama_cmd)
                    resp_cmd = engine_socket.recv(1024)
                    cod_cmd, campos_cmd = descomponer_trama(resp_cmd)
                    if cod_cmd == 'ACK':
                        detalle = campos_cmd[0] if campos_cmd else ''
                        print(f"[{cp_id}] ACK Engine a '{orden}': {detalle}")
                    else:
                        print(f"[{cp_id}] Respuesta inesperada a CMD '{orden}': {cod_cmd}")
                except Exception as e:
                    print(f"[{cp_id}] Error enviando comando '{orden}' por HCK socket: {e}")
                    # Reencolar para reintentar cuando se restablezca la conexión
                    try:
                        COMMAND_QUEUE.put_nowait(item)
                    except Exception:
                        pass
                    raise

            # 3. Enviar HCK
            trama_hck = construir_trama('HCK', [cp_id])
            engine_socket.sendall(trama_hck)
            
            # 4. Recibir y procesar todas las respuestas disponibles (puede llegar más de una trama)
            def _procesar_trama_engine(cod: str, args: list):
                if cod == 'HCK_RESP' and args:
                    status = args[0]
                    if status == 'OK':
                        return
                    if status == 'KO':
                        print(f"[{cp_id}] HCK KO recibido. Notificando avería a Central.")
                        notificar_averia_central(central_socket, cp_id, "Fallo reportado por Engine")
                    else:
                        print(f"[{cp_id}] Respuesta HCK_RESP inválida: {status}")
                    return
                if cod == 'FIN':
                    try:
                        print(f"[{cp_id}] ✅ FIN recibido del Engine. Reenviando a Central.")
                        print(f"[{cp_id}]   Campos FIN: {args}")
                        trama_fin = construir_trama('FIN', args)
                        central_socket.sendall(trama_fin)
                        print(f"[{cp_id}] ✅ FIN enviado exitosamente a Central")
                    except Exception as e:
                        print(f"[{cp_id}] ❌ Error reenviando FIN a Central: {e}")
                        import traceback
                        traceback.print_exc()
                    return
                if cod == 'READY_TO_START':
                    try:
                        engine_cp_id = args[0] if len(args) > 0 else cp_id
                        driver_id = args[1] if len(args) > 1 else 'UNKNOWN'
                        print(f"[{cp_id}] 📩 READY_TO_START recibido del Engine (Driver: {driver_id})")
                        trama = construir_trama('READY_TO_START', [engine_cp_id, driver_id])
                        central_socket.sendall(trama)
                        print(f"[{cp_id}] 📤 READY_TO_START reenviado a Central")
                    except Exception as e:
                        print(f"[{cp_id}] Error procesando READY_TO_START: {e}")
                    return
                if cod == 'REQUEST_STOP':
                    try:
                        engine_cp_id = args[0] if len(args) > 0 else cp_id
                        driver_id = args[1] if len(args) > 1 else 'UNKNOWN'
                        kw_actual = args[2] if len(args) > 2 else '0'
                        segundos = args[3] if len(args) > 3 else '0'
                        print(f"[{cp_id}] 📩 REQUEST_STOP recibido del Engine (Driver: {driver_id}, {kw_actual} kWh)")
                        trama = construir_trama('REQUEST_STOP', [engine_cp_id, driver_id, kw_actual, segundos])
                        central_socket.sendall(trama)
                        print(f"[{cp_id}] 📤 REQUEST_STOP reenviado a Central")
                    except Exception as e:
                        print(f"[{cp_id}] Error procesando REQUEST_STOP: {e}")
                    return
                if cod == 'STATE':
                    try:
                        estado = args[1] if len(args) > 1 else 'ACTIVADO'
                        print(f"[{cp_id}] STATE desde Engine: {estado}.")
                        print(f"[{cp_id}] Avisando a Central del estado: {estado}.")
                        trama_state = construir_trama('STATE', [cp_id, estado])
                        central_socket.sendall(trama_state)
                    except Exception as e:
                        print(f"[{cp_id}] Error reenviando STATE a Central: {e}")
                    return
                if cod == 'ACK':
                    detalle = args[0] if args else 'Sin detalle'
                    print(f"[{cp_id}] ACK tardío del Engine recibido: {detalle}")
                    return
                print(f"[{cp_id}] Trama inesperada desde Engine: {cod}")

            # Primer frame (bloqueante con timeout normal)
            respuesta_bytes = engine_socket.recv(1024)
            if not respuesta_bytes:
                raise ConnectionResetError("Engine cerró la conexión o respondió vacío.")
            cod_op, campos = descomponer_trama(respuesta_bytes)
            _procesar_trama_engine(cod_op, campos)

            # Drenar frames adicionales que pudieran haber llegado encadenados (no bloquear)
            try:
                engine_socket.settimeout(0.01)
                while True:
                    extra = engine_socket.recv(1024)
                    if not extra:
                        break
                    cod_extra, campos_extra = descomponer_trama(extra)
                    _procesar_trama_engine(cod_extra, campos_extra)
            except (socket.timeout, BlockingIOError):
                pass
            finally:
                engine_socket.settimeout(HCK_INTERVAL * 0.8)

        except socket.timeout:
            print(f"[{cp_id}] ⚠ Timeout HCK. Engine no responde. Notificando avería.")
            notificar_averia_central(central_socket, cp_id, "Timeout de HCK")
            if engine_socket:
                engine_socket.close()
            engine_socket = None # Forzar reconexión
            conexion_perdida_notificada = False
            
        except (ConnectionRefusedError, ConnectionResetError, BrokenPipeError, OSError) as e:
            if not conexion_perdida_notificada:
                print(f"[{cp_id}] ⚠ Conexión con Engine perdida. Reintentando reconexión...")
                notificar_averia_central(central_socket, cp_id, "Conexión con Engine perdida")
                conexion_perdida_notificada = True
            if engine_socket:
                engine_socket.close()
            engine_socket = None 

        except Exception as e:
            print(f"[{cp_id}] Error general en Hilo HCK: {e}")
            if engine_socket:
                engine_socket.close()
            engine_socket = None 
            conexion_perdida_notificada = False
            
        finally:
            # Esperar el intervalo antes de la siguiente comprobación
            time.sleep(HCK_INTERVAL)
            
def main():
    parser = argparse.ArgumentParser(description="Proceso EC_CP_M (Charging Point Monitor)")
    parser.add_argument("--engine_ip", type=str, required=True, help="IP del CP Engine")
    parser.add_argument("--engine_port", type=int, required=True, help="Puerto del CP Engine")
    parser.add_argument("--central_ip", type=str, required=True, help="IP del EV_Central")
    parser.add_argument("--central_port", type=int, required=True, help="Puerto del EV_Central")
    parser.add_argument("--cp_id", type=str, required=True, help="Identificador del Charging Point")
    args = parser.parse_args()

    print("="*40)
    print("[EC_CP_M] INICIADO")
    print(f"Conectando a Engine en: {args.engine_ip}:{args.engine_port}")
    print(f"Conectando a Central en: {args.central_ip}:{args.central_port}")
    print(f"ID del CP: {args.cp_id}")
    print("="*40)
    
    central_socket = None
    try:
        # 1. Registro en la Central
        central_socket = conectar_y_registrar(args.central_ip, args.central_port, args.cp_id)

        # 2. Hilo de escucha de comandos de la Central
        central_listener_thread = threading.Thread(
            target=escuchar_central,
            args=(central_socket, args.cp_id, args.engine_ip, args.engine_port),
            daemon=True
        )
        central_listener_thread.start()

        # 3. Hilo de Chequeo de Salud local (HCK)
        health_check_thread = threading.Thread(
            target=chequear_salud_engine,
            args=(args.engine_ip, args.engine_port, central_socket, args.cp_id),
            daemon=True
        )
        health_check_thread.start()

        print("\n[CP_M] Sistema ACTIVADO. Monitorización local de Engine iniciada.")

        # Bucle principal para mantener el proceso vivo
        while True:
            time.sleep(1)

    except Exception as e:
        print(f"[{args.cp_id}] Proceso EC_CP_M finalizado debido a un error crítico: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()