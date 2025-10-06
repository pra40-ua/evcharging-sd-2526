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
    # ... [Tu lógica de registro permanece igual] ...
    # Asegúrate de que esta función usa el socket.settimeout(None) por defecto
    
    ubicacion_cp = "C/Mayor, 45"
    precio_kwh = "0.48"
    client_socket = None

    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"[CP_M] Intentando conectar a EV_Central en {central_ip}:{central_port}...")
        client_socket.connect((central_ip, central_port))
        print("[CP_M] Conexión con Central establecida. Enviando REG...")

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
            
            if cod_op in ('STOP', 'START'):
                print(f"[{cp_id}] <--- COMANDO CENTRAL RECIBIDO: {cod_op}")
                # Encolamos la orden para que la ejecute el hilo HCK sobre su socket
                try:
                    COMMAND_QUEUE.put_nowait((cod_op, time.time()))
                    print(f"[{cp_id}] Orden '{cod_op}' encolada para Engine.")
                except Exception as e:
                    print(f"[{cp_id}] No se pudo encolar la orden {cod_op}: {e}")

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

    while True:
        try:
            # 1. Intentar establecer/reestablecer conexión con el Engine
            if engine_socket is None:
                engine_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                engine_socket.connect((engine_ip, engine_port))
                print(f"[{cp_id}] Conexión con Engine establecida.")
                engine_socket.settimeout(HCK_INTERVAL * 0.8)
            
            # 2. Antes de enviar HCK, consumir órdenes pendientes y enviarlas por el mismo socket
            #    Consumimos todas las que haya disponibles sin bloquear
            while True:
                try:
                    orden, ts = COMMAND_QUEUE.get_nowait()
                except Empty:
                    break
                try:
                    trama_cmd = construir_trama('CMD', [orden])
                    engine_socket.sendall(trama_cmd)
                    resp_cmd = engine_socket.recv(1024)
                    cod_cmd, campos_cmd = descomponer_trama(resp_cmd)
                    if cod_cmd == 'ACK':
                        detalle = campos_cmd[0] if campos_cmd else ''
                        print(f"[{cp_id}] ACK Engine a '{orden}': {detalle}")
                    else:
                        print(f"[{cp_id}] Respuesta inesperada a CMD '{orden}': {cod_cmd}")
                except Exception as e:
                    print(f"[{cp_id}] Error enviando CMD '{orden}' por HCK socket: {e}")
                    # Reencolar para reintentar cuando se restablezca la conexión
                    try:
                        COMMAND_QUEUE.put_nowait((orden, ts))
                    except Exception:
                        pass
                    raise

            # 3. Enviar HCK
            trama_hck = construir_trama('HCK', [cp_id])
            engine_socket.sendall(trama_hck)
            
            # 4. Recibir respuesta HCK
            respuesta_bytes = engine_socket.recv(1024)
            
            if not respuesta_bytes:
                raise ConnectionResetError("Engine cerró la conexión o respondió vacío.")
            
            cod_op, campos = descomponer_trama(respuesta_bytes)

            if cod_op == 'HCK_RESP' and campos:
                status = campos[0]
                if status == 'OK':
                    # print(f"[{cp_id}] HCK OK.") # No saturar la salida si todo va bien
                    pass
                elif status == 'KO':
                    print(f"[{cp_id}] HCK KO recibido. Notificando avería a Central.")
                    notificar_averia_central(central_socket, cp_id, "Fallo reportado por Engine")
                else:
                    print(f"[{cp_id}] Respuesta HCK_RESP inválida: {status}")
            else:
                 print(f"[{cp_id}] Trama HCK_RESP inválida o ilegible.")

        except socket.timeout:
            print(f"[{cp_id}] ERROR: Timeout HCK. Engine no responde. Notificando avería.")
            notificar_averia_central(central_socket, cp_id, "Timeout de HCK")
            if engine_socket:
                engine_socket.close()
            engine_socket = None # Forzar reconexión
            
        except (ConnectionRefusedError, ConnectionResetError):
            print(f"[{cp_id}] ERROR: Conexión con Engine perdida/rechazada. Forzando reconexión.")
            notificar_averia_central(central_socket, cp_id, "Conexión con Engine perdida")
            if engine_socket:
                engine_socket.close()
            engine_socket = None 

        except Exception as e:
            print(f"[{cp_id}] Error general en Hilo HCK: {e}")
            if engine_socket:
                engine_socket.close()
            engine_socket = None 
            
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