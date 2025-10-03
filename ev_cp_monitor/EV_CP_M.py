import time
import argparse
import socket
import sys
import threading

# =================================================================
#                         FUNCIONES DE PROTOCOLO
# (Mantenidas desde tu implementación original)
# =================================================================
# Constantes de Protocolo
STX = b'\x02'
ETX = b'\x03'
DELIMITER = '#'

def calcular_lrc(data_bytes: bytes) -> bytes:
    """Calcula el Longitudinal Redundancy Check (XOR de todos los bytes)."""
    lrc = 0
    # Calcular el XOR de cada byte
    for byte in data_bytes:
        lrc ^= byte
    # Devolver el byte LRC
    return bytes([lrc])

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

def construir_trama(cod_op: str, campos: list) -> bytes:
    """Construye la trama completa del protocolo EV_CP_M."""
    
    # 1. Crear el contenido DATA (Cod_Op#campo1#campo2...)
    DATA = f"{cod_op}#{DELIMITER.join(map(str, campos))}"
    
    # 2. Codificar la DATA para obtener los BYTES a enviar
    DATA_bytes = DATA.encode('utf-8')
    
    # 3. Calcular el LRC de los BYTES
    LRC_byte = calcular_lrc(DATA_bytes) # <-- Ahora recibe bytes
    
    # 4. Ensamblar la trama: STX + DATA (en bytes) + ETX + LRC
    trama = STX + DATA_bytes + ETX + LRC_byte
    return trama


# =================================================================
#                       LÓGICA DEL MONITOR (CP_M)
# =================================================================

def conectar_y_registrar(central_ip: str, central_port: int, cp_id: str) -> socket.socket:
    """Conecta con la Central, envía REG y espera AUTH. Retorna el socket abierto."""
    
    ubicacion_cp = "C/Mayor, 45"
    precio_kwh = "0.48"
    client_socket = None

    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"[CP_M] Intentando conectar a EV_Central en {central_ip}:{central_port}...")
        client_socket.connect((central_ip, central_port))
        print("[CP_M] Conexión con Central establecida. Enviando REG...")

        # Construir y enviar la trama REG
        trama_registro = construir_trama('REG', [cp_id, ubicacion_cp, precio_kwh])
        client_socket.sendall(trama_registro)

        # Recibir la respuesta de la Central (AUTH)
        respuesta_bytes = client_socket.recv(1024)
        
        # 1. Verificar si Central cerró (respuesta vacía)
        if not respuesta_bytes:
            raise Exception("No se recibió respuesta o Central cerró la conexión.")

        # 2. Descomponer y validar la trama con el protocolo
        cod_op, campos = descomponer_trama(respuesta_bytes)
        
        # Comprobación de formato (para depuración)
        print(f"[CP_M] Recibida respuesta bruta: {respuesta_bytes.decode(errors='ignore')}")

        if cod_op == 'AUTH' and campos and campos[0] == 'OK':
            print(f"[CP_M] ¡{cp_id} REGISTRO EXITOSO! Estado ACTIVADO. Mensaje: {campos[1]}")
            return client_socket # Devuelve el socket abierto
        else:
            # Esto captura errores de formato (LRC, STX/ETX -> cod_op=None) o un AUTH#FAIL
            raise Exception(f"Fallo de autenticación. Respuesta inválida o AUTH#FAIL. Cod={cod_op}, Campos={campos}")

    except Exception as e:
        print(f"[CP_M] ERROR durante el registro: {e}")
        if client_socket:
            client_socket.close()
        raise # Vuelve a lanzar la excepción para que main lo maneje

def escuchar_central(central_socket: socket.socket, cp_id: str):
    """Bucle de escucha permanente para comandos síncronos de la Central (STOP, START)."""
    print(f"[{cp_id}] Hilo de escucha de Central iniciado.")
    try:
        while True:
            trama_bytes = central_socket.recv(1024)
            if not trama_bytes:
                print(f"[{cp_id}] Central cerró la conexión. Socket de comando cerrado.")
                break
            
            # Aquí iría la lógica para descomponer_trama y procesar comandos de la Central
            # Por ahora, solo imprime la recepción
            print(f"[{cp_id}] <--- Comando Central recibido: {trama_bytes.decode(errors='ignore')}")

    except Exception as e:
        print(f"[{cp_id}] Error en hilo de escucha de Central: {e}")
    finally:
        central_socket.close()
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
    # 1. Registro en la Central
    try:
        # 1. Registro en la Central (obtiene el socket abierto)
        central_socket = conectar_y_registrar(args.central_ip, args.central_port, args.cp_id)

        # 2. Iniciar el hilo de escucha de comandos de la Central
        central_listener_thread = threading.Thread(
            target=escuchar_central, 
            args=(central_socket, args.cp_id), 
            daemon=True
        )
        central_listener_thread.start()
        
        # 3. La función main() continúa con la siguiente fase (Chequeo de Salud local)
        print("\n[CP_M] Sistema ACTIVADO. Iniciando lógica de Chequeo de Salud (Próximo Paso)...")
        
        # Por ahora, un bucle simple para mantener el proceso vivo.
        while True:
            time.sleep(1) 

    except Exception:
        # La excepción ya fue impresa en conectar_y_registrar o escuchar_central
        print(f"[{args.cp_id}] Proceso EC_CP_M finalizado debido a un error crítico.")
        sys.exit(1)

if __name__ == "__main__":
    main()