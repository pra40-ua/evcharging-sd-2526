import time
import argparse
import socket
import sys
import threading

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

# ... [La función escuchar_central permanece igual] ...
def escuchar_central(central_socket: socket.socket, cp_id: str):
    # ... [Tu lógica de escucha de la Central permanece igual] ...
    print(f"[{cp_id}] Hilo de escucha de Central iniciado.")
    try:
        while True:
            trama_bytes = central_socket.recv(1024)
            if not trama_bytes:
                print(f"[{cp_id}] Central cerró la conexión. Socket de comando cerrado.")
                break
            
            # TODO: Descomponer y procesar comandos de la Central (STOP, START, etc.)
            print(f"[{cp_id}] <--- Comando Central recibido: {trama_bytes.decode(errors='ignore')}")

    except Exception as e:
        print(f"[{cp_id}] Error en hilo de escucha de Central: {e}")
    finally:
        central_socket.close()

# =================================================================
#                       LÓGICA DE MONITORIZACIÓN LOCAL (HCK)
# =================================================================

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
            
            # 2. Enviar HCK
            trama_hck = construir_trama('HCK', [cp_id])
            engine_socket.sendall(trama_hck)
            
            # 3. Recibir respuesta (establecer un timeout corto)
            engine_socket.settimeout(HCK_INTERVAL * 0.8) 
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
            args=(central_socket, args.cp_id), 
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

    except Exception:
        print(f"[{args.cp_id}] Proceso EC_CP_M finalizado debido a un error crítico.")
        sys.exit(1)

if __name__ == "__main__":
    main()