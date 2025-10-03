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

def handle_monitor_connection(conn: socket.socket, addr: tuple):
    """Maneja el chequeo de salud HCK del Monitor."""
    print(f"[ENGINE] Monitor conectado desde {addr[0]}:{addr[1]}")
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
            else:
                 print(f"[ENGINE] Recibido mensaje no HCK: {cod_op}")
            
    except ConnectionResetError:
        print(f"[ENGINE] Conexión con Monitor ({addr[0]}) perdida inesperadamente.")
    except Exception as e:
        print(f"[ENGINE] Error en bucle de conexión con Monitor: {e}")
    finally:
        conn.close()
        print("[ENGINE] Conexión con Monitor cerrada.")


def main():
    parser = argparse.ArgumentParser(description="Proceso EV_CP_E (Charging Point Engine)")
    parser.add_argument("--port", type=int, required=True, help="Puerto de escucha local")
    args = parser.parse_args()
    
    print("="*40)
    print("[EV_CP_E] INICIADO")
    print(f"Puerto de escucha: {args.port}")
    print("="*40)

    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('', args.port))
        server_socket.listen(1) 
        
        print(f"[EV_CP_E] Servidor escuchando en TCP (:{args.port}). Esperando Monitor...")

        # El Engine solo acepta una conexión: la del Monitor
        conn, addr = server_socket.accept()
        handle_monitor_connection(conn, addr)
        
    except KeyboardInterrupt:
        print("\n[EV_CP_E] Apagando...")
    except Exception as e:
        print(f"[EV_CP_E] Error principal: {e}")
    finally:
        if 'server_socket' in locals():
            server_socket.close()

if __name__ == "__main__":
    main()