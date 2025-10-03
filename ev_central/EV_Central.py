import socket
import argparse
import threading

# =================================================================
#                         FUNCIONES DE PROTOCOLO
# =================================================================

# Constantes de Protocolo
STX = b'\x02'
ETX = b'\x03'
DELIMITER = '#'

def calcular_lrc(data: bytes) -> bytes:
    """Calcula el Longitudinal Redundancy Check (XOR de todos los bytes)."""
    lrc = 0
    for byte in data:
        lrc ^= byte
    return bytes([lrc])

def construir_trama(cod_op: str, campos: list) -> bytes:
    """Construye la trama completa para enviar una respuesta (ej. AUTH)."""
    # 1. Crear el contenido DATA (Cod_Op#campo1#campo2...)
    DATA = f"{cod_op}#{DELIMITER.join(map(str, campos))}"
    
    # 2. Calcular el LRC de la DATA
    DATA_bytes = DATA.encode('utf-8')
    LRC_byte = calcular_lrc(DATA_bytes)
    
    # 3. Ensamblar la trama: STX + DATA (en bytes) + ETX + LRC
    trama = STX + DATA_bytes + ETX + LRC_byte
    return trama

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

# =================================================================
#                       LÓGICA DEL SERVIDOR CENTRAL
# =================================================================

def manejar_cliente(conn: socket.socket, addr: tuple):
    """Función ejecutada por un hilo para manejar la conexión de un CP."""
    
    print(f"[CENTRAL] Conexión establecida con {addr[0]}:{addr[1]}")
    cp_id = "Desconocido"
    
    try:
        # --- 1. REGISTRO Y AUTENTICACIÓN (Primer intercambio) ---
        trama_bytes = conn.recv(1024)
        if not trama_bytes:
            raise ConnectionResetError("Conexión cerrada por el cliente antes del registro.")

        cod_op, campos = descomponer_trama(trama_bytes)

        if cod_op == 'REG' and len(campos) >= 3:
            cp_id = campos[0] # Almacena el ID para usarlo en el hilo
            print(f"[CENTRAL] -> Recibido REG de CP ID: {cp_id}...")
            
            # [Lógica BD: Insertar/Actualizar CP y marcar como ACTIVADO]
            
            respuesta_trama = construir_trama('AUTH', ['OK', 'Autenticacion exitosa'])
            conn.sendall(respuesta_trama)
            print(f"[CENTRAL] <- Enviada respuesta AUTH: OK a {cp_id}")

        else:
            print(f"[CENTRAL] Error: Mensaje inicial no válido ({cod_op}). Cerrando conexión.")
            return # Sale de la función y va al finally

        # --- 2. BUCLE DE COMUNICACIÓN PERMANENTE ---
        print(f"[CENTRAL] Hilo {cp_id} iniciando bucle de escucha permanente.")
        while True:
            # Ahora el hilo espera por comandos síncronos (AVR, telemetría síncrona, etc.)
            trama_bytes = conn.recv(1024)
            if not trama_bytes:
                # El CP cerró la conexión
                print(f"[CENTRAL] Conexión con CP {cp_id} cerrada por el cliente.")
                break 
                
            cod_op, campos = descomponer_trama(trama_bytes)
            
            if cod_op:
                print(f"[CENTRAL] Recibida trama de {cp_id}: Cod={cod_op}, Campos={campos}")
                # [Lógica para manejar AVR, Suministro síncrono, etc.]
            else:
                print(f"[CENTRAL] Trama inválida de {cp_id}.")

    except ConnectionResetError:
        print(f"[CENTRAL] Conexión con {cp_id} perdida inesperadamente (Reset).")
    except Exception as e:
        print(f"[CENTRAL] Error en bucle de cliente {cp_id}: {e}")
    finally:
        # [Lógica DB: Marcar el CP como DESCONECTADO (Gris)]
        conn.close()
        print(f"[CENTRAL] Hilo de conexión con {cp_id} finalizado. Socket cerrado.")

def main():
    parser = argparse.ArgumentParser(description="Proceso EV_Central")
    parser.add_argument("--port", type=int, required=True, help="Puerto de escucha")
    parser.add_argument("--kafka", type=str, required=True, help="Broker Kafka (IP:puerto)")
    parser.add_argument("--db", type=str, help="Ruta/URL de la base de datos")
    args = parser.parse_args()

    print("="*40)
    print("[EV_Central] INICIADO")
    print(f"Puerto de escucha: {args.port}")
    print(f"Broker Kafka: {args.kafka}")
    print(f"Base de datos: {args.db if args.db else 'Ninguna'}")
    print("="*40)

    # Inicialización del servidor de Sockets
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Permite reutilizar el puerto
        
        server_socket.bind(('', args.port)) 
        server_socket.listen(5)
        
        print(f"[EV_Central] Servidor escuchando en TCP (:{args.port})...")

        while True:
            # Bloqueante: Espera una conexión
            conn, addr = server_socket.accept()
            # Iniciar un nuevo hilo para manejar la conexión de forma concurrente
            client_thread = threading.Thread(target=manejar_cliente, args=(conn, addr))
            client_thread.start()

    except KeyboardInterrupt:
        print("\n[EV_Central] Apagando por interrupción de usuario...")
    except Exception as e:
        print(f"[EV_Central] Error principal: {e}")
    finally:
        if 'server_socket' in locals():
            server_socket.close()

if __name__ == "__main__":
    main()