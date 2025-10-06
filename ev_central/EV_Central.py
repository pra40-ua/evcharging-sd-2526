import socket
import argparse
import threading
import mysql.connector
from mysql.connector import Error
from datetime import datetime

# =================================================================
#                 ESTADO GLOBAL DE CONEXIONES ACTIVAS
# =================================================================

# Diccionario de CP_ID -> socket
CONEXIONES_ACTIVAS = {}
CONEXIONES_ACTIVAS_LOCK = threading.Lock()

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
#                      FUNCIONES DE BASE DE DATOS
# =================================================================

def conectar_bd(db_config: str) -> mysql.connector.connection.MySQLConnection:
    """Establece conexión con la base de datos MySQL."""
    try:
        # Parsear la configuración de BD (formato: host:port:user:password:database)
        if not db_config:
            raise ValueError("Configuración de BD no proporcionada")
        
        parts = db_config.split(':')
        if len(parts) != 5:
            raise ValueError("Formato de BD incorrecto. Use: host:port:user:password:database")
        
        host, port, user, password, database = parts
        
        connection = mysql.connector.connect(
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=database,
            autocommit=True
        )
        
        if connection.is_connected():
            print(f"[CENTRAL] Conectado a MySQL en {host}:{port}")
            return connection
            
    except Error as e:
        print(f"[CENTRAL] Error conectando a MySQL: {e}")
        raise
    except Exception as e:
        print(f"[CENTRAL] Error inesperado en conexión BD: {e}")
        raise

def registrar_cp_en_bd(connection: mysql.connector.connection.MySQLConnection, 
                       cp_id: str, ubicacion: str, precio_kwh: float) -> bool:
    """Registra o actualiza un CP en la base de datos y lo marca como Activado."""
    try:
        cursor = connection.cursor()
        
        # Verificar si el CP ya existe
        cursor.execute("SELECT id, estado FROM charging_points WHERE cp_id = %s", (cp_id,))
        result = cursor.fetchone()
        
        if result:
            # CP existe, actualizar estado y fecha de conexión
            cp_db_id, estado_actual = result
            cursor.execute("""
                UPDATE charging_points 
                SET estado = 'Activado', fecha_ultima_conexion = %s 
                WHERE cp_id = %s
            """, (datetime.now(), cp_id))
            print(f"[CENTRAL] CP {cp_id} actualizado en BD. Estado anterior: {estado_actual} -> Activado")
        else:
            # CP nuevo, insertar
            cursor.execute("""
                INSERT INTO charging_points (cp_id, ubicacion, precio_kwh, estado, fecha_ultima_conexion)
                VALUES (%s, %s, %s, 'Activado', %s)
            """, (cp_id, ubicacion, precio_kwh, datetime.now()))
            print(f"[CENTRAL] CP {cp_id} registrado en BD como nuevo")
        
        cursor.close()
        return True
        
    except Error as e:
        print(f"[CENTRAL] Error en BD al registrar CP {cp_id}: {e}")
        return False
    except Exception as e:
        print(f"[CENTRAL] Error inesperado al registrar CP {cp_id}: {e}")
        return False

def actualizar_estado_cp(connection: mysql.connector.connection.MySQLConnection, 
                         cp_id: str, nuevo_estado: str) -> bool:
    """Actualiza el estado de un CP en la base de datos."""
    try:
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE charging_points 
            SET estado = %s, fecha_ultima_conexion = %s 
            WHERE cp_id = %s
        """, (nuevo_estado, datetime.now(), cp_id))
        
        if cursor.rowcount > 0:
            print(f"[CENTRAL] Estado de CP {cp_id} actualizado a: {nuevo_estado}")
            cursor.close()
            return True
        else:
            print(f"[CENTRAL] CP {cp_id} no encontrado en BD para actualizar estado")
            cursor.close()
            return False
            
    except Error as e:
        print(f"[CENTRAL] Error actualizando estado de CP {cp_id}: {e}")
        return False
    except Exception as e:
        print(f"[CENTRAL] Error inesperado actualizando estado de CP {cp_id}: {e}")
        return False

# =================================================================
#                       LÓGICA DEL SERVIDOR CENTRAL
# =================================================================

def manejar_cliente(conn: socket.socket, addr: tuple, db_connection: mysql.connector.connection.MySQLConnection):
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
            cp_id = campos[0]
            ubicacion = campos[1]
            precio_kwh = float(campos[2])
            
            # --- NUEVA LÓGICA: Almacenar la conexión ---
            with CONEXIONES_ACTIVAS_LOCK:
                CONEXIONES_ACTIVAS[cp_id] = conn
                print(f"[CENTRAL] Socket de {cp_id} guardado. Total: {len(CONEXIONES_ACTIVAS)}")
            
            # --- LÓGICA BD: Insertar/Actualizar CP y marcar como ACTIVADO ---
            if db_connection and db_connection.is_connected():
                if registrar_cp_en_bd(db_connection, cp_id, ubicacion, precio_kwh):
                    respuesta_trama = construir_trama('AUTH', ['OK', 'Autenticacion exitosa'])
                    conn.sendall(respuesta_trama)
                    print(f"[CENTRAL] <- Enviada respuesta AUTH: OK a {cp_id}")
                else:
                    # Error en BD, rechazar conexión
                    respuesta_trama = construir_trama('AUTH', ['FAIL', 'Error en base de datos'])
                    conn.sendall(respuesta_trama)
                    print(f"[CENTRAL] <- Enviada respuesta AUTH: FAIL a {cp_id} (Error BD)")
                    return
            else:
                # Sin BD, aceptar conexión pero advertir
                print(f"[CENTRAL] ADVERTENCIA: Sin conexión a BD, aceptando {cp_id} sin persistencia")
                respuesta_trama = construir_trama('AUTH', ['OK', 'Autenticacion exitosa (sin BD)'])
                conn.sendall(respuesta_trama)
                print(f"[CENTRAL] <- Enviada respuesta AUTH: OK a {cp_id} (sin BD)")

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
        # --- LÓGICA DB: Marcar el CP como DESCONECTADO ---
        if cp_id != "Desconocido" and db_connection and db_connection.is_connected():
            actualizar_estado_cp(db_connection, cp_id, "Desconectado")
        
        if cp_id in CONEXIONES_ACTIVAS:
            with CONEXIONES_ACTIVAS_LOCK:
                del CONEXIONES_ACTIVAS[cp_id]
                print(f"[CENTRAL] Socket de {cp_id} eliminado. Total: {len(CONEXIONES_ACTIVAS)}")
        
        conn.close()
        print(f"[CENTRAL] Hilo de conexión con {addr[0]}:{addr[1]} finalizado.")


def consola_central():
    """Hilo que permite al operador enviar comandos STOP/START desde la consola."""
    while True:
        try:
            # Esperamos comandos del operador, ej: STOP CP001
            comando_str = input("\n[CENTRAL CMD] (Ej: STOP CP001): ").strip().upper()
            if not comando_str:
                continue

            partes = comando_str.split()
            cod_op = partes[0]
            
            if cod_op in ('STOP', 'START') and len(partes) == 2:
                cp_id = partes[1]
                
                with CONEXIONES_ACTIVAS_LOCK:
                    conn = CONEXIONES_ACTIVAS.get(cp_id)
                
                if conn:
                    # Construir y enviar la trama de control
                    trama_control = construir_trama(cod_op, [cp_id])
                    conn.sendall(trama_control)
                    print(f"[CENTRAL] -> Enviado {cod_op} a {cp_id}.")
                else:
                    print(f"[CENTRAL] ERROR: CP ID {cp_id} no está conectado o no se registró.")
                    
            elif cod_op == 'EXIT':
                print("[CENTRAL] Saliendo de la consola...")
                break # Salir del bucle de comandos
            
            else:
                print("[CENTRAL] Comando inválido. Use STOP <ID> o START <ID>.")
                
        except EOFError:
            print("\n[CENTRAL] Consola terminada por EOF (Ctrl+Z o Ctrl+D).")
            break
        except Exception as e:
            print(f"[CENTRAL] Error en consola de comandos: {e}")
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

    # Inicialización de la base de datos
    db_connection = None
    if args.db:
        try:
            db_connection = conectar_bd(args.db)
        except Exception as e:
            print(f"[EV_Central] ADVERTENCIA: No se pudo conectar a BD: {e}")
            print("[EV_Central] Continuando sin persistencia de datos...")
    else:
        print("[EV_Central] ADVERTENCIA: No se proporcionó configuración de BD")
        print("[EV_Central] Continuando sin persistencia de datos...")

    # Inicialización del servidor de Sockets
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Permite reutilizar el puerto
        
        server_socket.bind(('', args.port)) 
        server_socket.listen(5)
        consola_thread = threading.Thread(target=consola_central, daemon=True)
        consola_thread.start()
        print(f"[EV_Central] Servidor escuchando en TCP (:{args.port})...")

        while True:
            # Bloqueante: Espera una conexión
            conn, addr = server_socket.accept()
            # Iniciar un nuevo hilo para manejar la conexión de forma concurrente
            client_thread = threading.Thread(target=manejar_cliente, args=(conn, addr, db_connection))
            client_thread.start()

    
    except KeyboardInterrupt:
        print("\n[EV_Central] Apagando por interrupción de usuario...")
    except Exception as e:
        print(f"[EV_Central] Error principal: {e}")
    finally:
        if 'server_socket' in locals():
            server_socket.close()
        if db_connection and db_connection.is_connected():
            db_connection.close()
            print("[EV_Central] Conexión a BD cerrada.")

if __name__ == "__main__":
    main()