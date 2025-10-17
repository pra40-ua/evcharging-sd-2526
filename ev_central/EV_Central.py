import socket
import argparse
import threading
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from kafka import KafkaConsumer, KafkaProducer
import json

# =================================================================
#                 ESTADO GLOBAL DE CONEXIONES ACTIVAS
# =================================================================

# Diccionario de CP_ID -> socket
CONEXIONES_ACTIVAS = {}
CONEXIONES_ACTIVAS_LOCK = threading.Lock()

# Diccionario para almacenar la telemetría más reciente de cada CP
TELEMETRIA_ACTUAL = {}
TELEMETRIA_ACTUAL_LOCK = threading.Lock()

# Lista de hilos de clientes para cierre ordenado
CLIENT_THREADS = []
CLIENT_THREADS_LOCK = threading.Lock()

# Variable global para controlar el apagado limpio
SHUTDOWN_REQUESTED = False
SHUTDOWN_LOCK = threading.Lock()

# =================================================================
#                         FUNCIONES DE PROTOCOLO
# =================================================================

# Constantes de Protocolo
STX = b'\x02'
ETX = b'\x03'
DELIMITER = '#'
TELEMETRIA_TOPIC = 'telemetria_cp'
DRIVER_REQUESTS_TOPIC = 'driver_requests'

# Productor Kafka global para notificar a Drivers
KAFKA_PRODUCER = None
KAFKA_PRODUCER_LOCK = threading.Lock()

def consumir_telemetria_kafka(broker_list: str):
    """
    Se conecta a Kafka y consume mensajes del tópico de telemetría.
    """
    print(f"[KAFKA CONSUMER] Conectando al broker: {broker_list}")
    consumer = None
    try:
        # Configuración del Consumidor
        consumer = KafkaConsumer(
            TELEMETRIA_TOPIC,
            bootstrap_servers=[broker_list],
            # Deserializador para convertir los bytes del mensaje a un diccionario de Python
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            # Empieza a leer mensajes recientes si no hay offset previo
            auto_offset_reset='latest', 
            group_id='central-telemetry-group' # Grupo para distribuir la carga si hay múltiples centrales
        )
        
        print(f"[KAFKA CONSUMER] Suscrito al tópico '{TELEMETRIA_TOPIC}'. Esperando telemetría...")

        # Bucle de consumo con verificación de apagado no bloqueante
        while True:
            # Verificar si se solicita el apagado
            with SHUTDOWN_LOCK:
                if SHUTDOWN_REQUESTED:
                    print("[KAFKA CONSUMER] Apagado solicitado, cerrando consumidor de telemetría...")
                    break

            records = consumer.poll(timeout_ms=1000)
            if not records:
                continue

            for _tp, batch in records.items():
                for message in batch:
                    # Aquí 'message.value' es el diccionario de Python gracias al deserializador
                    telemetria = message.value
                    cp_id = telemetria.get('cp_id', 'UNKNOWN')

                    # --- Almacenar telemetría en estructura global ---
                    with TELEMETRIA_ACTUAL_LOCK:
                        TELEMETRIA_ACTUAL[cp_id] = telemetria

                    # --- Lógica principal del Central ---
                    print(f"[KAFKA CONSUMER] -> Telemetría de {cp_id} recibida: {telemetria}")
            
    except Exception as e:
        print(f"[KAFKA CONSUMER] Error crítico de consumo de Kafka: {e}")
    finally:
        if consumer:
            consumer.close()
            print("[KAFKA CONSUMER] Consumidor de telemetría cerrado.")

# =================================================================
#                    CONSUMIDOR DE DRIVER_REQUESTS
# =================================================================
            
def consumir_solicitudes_driver_kafka(broker_list: str, db_connection: mysql.connector.connection.MySQLConnection):
    """
    Se conecta a Kafka y consume mensajes del tópico de solicitudes de drivers.
    """
    print(f"[KAFKA CONSUMER] EV_Central iniciando consumidor para el topic: {DRIVER_REQUESTS_TOPIC}")
    consumer = None
    try:
        consumer = KafkaConsumer(
            DRIVER_REQUESTS_TOPIC,
            bootstrap_servers=[broker_list],
            auto_offset_reset='earliest',
            group_id='central_processing_group',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )

        print(f"[KAFKA CONSUMER] Suscrito a '{DRIVER_REQUESTS_TOPIC}'. Esperando solicitudes de drivers...")

        while True:
            # Verificar si se solicita el apagado
            with SHUTDOWN_LOCK:
                if SHUTDOWN_REQUESTED:
                    print("[KAFKA CONSUMER] Apagado solicitado, cerrando consumidor de driver requests...")
                    break

            records = consumer.poll(timeout_ms=1000)
            if not records:
                continue

            for _tp, batch in records.items():
                for message in batch:
                    solicitud = message.value
                    print("--- NUEVA SOLICITUD RECIBIDA ---")
                    print(f"\tDriver ID: {solicitud.get('id_driver')}")
                    print(f"\tCP ID:     {solicitud.get('id_charging_point')}")
                    print(f"\tMatrícula: {solicitud.get('matricula')}")
                    print(f"\tkW Deseados: {solicitud.get('kw_deseados')} kW")
                    # Lógica de autorización: validación BD, socket al CP, notificaciones a Driver
                    try:
                        id_driver = solicitud.get('id_driver')
                        cp_id = solicitud.get('id_charging_point')
                        kw_deseados = solicitud.get('kw_deseados')

                        if not id_driver or not cp_id or kw_deseados is None:
                            print("[CENTRAL] Solicitud inválida: faltan campos obligatorios")
                            notificar_driver(id_driver or 'UNKNOWN', 'DENEGADA', {
                                'motivo': 'Solicitud inválida: faltan campos'
                            })
                            continue

                        # Paso 1: Notificar recepción
                        notificar_driver(id_driver, 'RECIBIDA', {
                            'mensaje': 'Solicitud recibida. Validando disponibilidad del CP...'
                        })

                        # Paso 2: Validar contra BD
                        if not (db_connection and db_connection.is_connected()):
                            print("[CENTRAL] BD no disponible; denegando solicitud.")
                            notificar_driver(id_driver, 'DENEGADA', {
                                'motivo': 'BD no disponible; no es posible validar CP'
                            })
                            continue

                        estado_cp = obtener_estado_cp(db_connection, cp_id)
                        if estado_cp is None:
                            print(f"[CENTRAL] CP {cp_id} no existe en BD")
                            notificar_driver(id_driver, 'DENEGADA', {
                                'motivo': f'CP {cp_id} no registrado'
                            })
                            continue

                        estado_inferior = estado_cp.strip().lower()
                        if estado_inferior in ('activado',):
                            pass
                        elif estado_inferior in ('suministrando',):
                            notificar_driver(id_driver, 'DENEGADA', {
                                'motivo': f'CP {cp_id} ocupado (Suministrando)'
                            })
                            continue
                        elif estado_inferior in ('parado', 'averiado', 'desconectado'):
                            notificar_driver(id_driver, 'DENEGADA', {
                                'motivo': f'CP {cp_id} no disponible: {estado_cp}'
                            })
                            continue
                        else:
                            notificar_driver(id_driver, 'DENEGADA', {
                                'motivo': f'Estado de CP desconocido: {estado_cp}'
                            })
                            continue

                        # Paso 3: Verificar conexión TCP con el Monitor (persistente)
                        with CONEXIONES_ACTIVAS_LOCK:
                            cp_socket = CONEXIONES_ACTIVAS.get(cp_id)

                        if not cp_socket:
                            print(f"[CENTRAL] CP {cp_id} no está conectado por socket")
                            notificar_driver(id_driver, 'DENEGADA', {
                                'motivo': f'CP {cp_id} desconectado'
                            })
                            continue

                        # Paso 4: Enviar solicitud de autorización al Monitor
                        notificar_driver(id_driver, 'AUTORIZACION_EN_PROCESO', {
                            'mensaje': f'Contactando Monitor de {cp_id}...'
                        })

                        try:
                            trama_auth = construir_trama('AUTH_REQ', [id_driver, kw_deseados])
                            cp_socket.sendall(trama_auth)
                            print(f"[CENTRAL] -> AUTH_REQ enviado a {cp_id} para driver {id_driver}")
                            notificar_driver(id_driver, 'PENDIENTE_RESPUESTA_CP', {
                                'mensaje': 'Solicitud enviada al CP. Esperando confirmación.'
                            })
                        except Exception as e:
                            print(f"[CENTRAL] Error enviando AUTH_REQ a {cp_id}: {e}")
                            notificar_driver(id_driver, 'DENEGADA', {
                                'motivo': f'Error contactando con Monitor de {cp_id}'
                            })

                    except Exception as e:
                        print(f"[CENTRAL] Error procesando solicitud del driver: {e}")
    except Exception as e:
        print(f"[KAFKA CONSUMER] ERROR al iniciar el consumidor de la Central: {e}")
        print("[KAFKA CONSUMER] Verifica la conexión a Kafka.")
    finally:
        if consumer:
            consumer.close()
            print("[KAFKA CONSUMER] Consumidor de driver requests cerrado.")

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
            autocommit=True,
            charset='utf8mb4',
            collation='utf8mb4_general_ci'
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

def obtener_estado_cp(connection: mysql.connector.connection.MySQLConnection, cp_id: str):
    """Obtiene el estado actual del CP desde la BD. Devuelve str o None si no existe."""
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT estado FROM charging_points WHERE cp_id = %s", (cp_id,))
        result = cursor.fetchone()
        cursor.close()
        if result:
            return result[0]
        return None
    except Error as e:
        print(f"[CENTRAL] Error consultando estado de CP {cp_id}: {e}")
        return None
    except Exception as e:
        print(f"[CENTRAL] Error inesperado consultando estado de CP {cp_id}: {e}")
        return None

# =================================================================
#                      FUNCIONES DE NOTIFICACIÓN (Kafka)
# =================================================================

def inicializar_kafka_producer(broker_list: str):
    global KAFKA_PRODUCER
    with KAFKA_PRODUCER_LOCK:
        if KAFKA_PRODUCER is None:
            try:
                KAFKA_PRODUCER = KafkaProducer(
                    bootstrap_servers=[broker_list],
                    value_serializer=lambda v: json.dumps(v).encode('utf-8')
                )
                print("[KAFKA PRODUCER] Productor inicializado para notificaciones a drivers.")
            except Exception as e:
                print(f"[KAFKA PRODUCER] ERROR al inicializar productor: {e}")
                KAFKA_PRODUCER = None
    return KAFKA_PRODUCER

def notificar_driver(id_driver: str, evento: str, detalle=None):
    """Envía un mensaje al tópico específico del driver: driver_status_<ID>."""
    if not id_driver:
        return
    try:
        payload = {
            'driver_id': id_driver,
            'evento': evento,
            'detalle': detalle,
            'timestamp': datetime.now().isoformat()
        }
        topic = f"driver_status_{id_driver}"
        if KAFKA_PRODUCER is None:
            print("[KAFKA PRODUCER] No disponible. No se puede notificar al driver.")
            return
        KAFKA_PRODUCER.send(topic, value=payload)
        # Se puede forzar flush si se requiere entrega inmediata
        KAFKA_PRODUCER.flush(timeout=2)
        print(f"[CENTRAL] Notificación enviada a {topic}: {evento}")
    except Exception as e:
        print(f"[CENTRAL] Error notificando al driver {id_driver}: {e}")

# =================================================================
#                       LÓGICA DEL SERVIDOR CENTRAL
# =================================================================
def mostrar_estado_red():
    """Muestra el estado actual de los Puntos de Carga conectados."""
    print("\n" + "="*60)
    print(f"| ESTADO DE LA RED DE CARGA (Total: {len(CONEXIONES_ACTIVAS)} CP(s) Activos) |")
    print("="*60)
    
    if not CONEXIONES_ACTIVAS:
        print(">> No hay Puntos de Carga conectados actualmente.")
        print("="*60)
        return

    # Iterar sobre los datos en tiempo real (Telemetría y Registro)
    for cp_id, socket_obj in CONEXIONES_ACTIVAS.items():
        print(f"| CP ID: {cp_id}")
        print(f"|   Socket: Conectado en {socket_obj.getsockname()[1]}")
        
        # Obtener telemetría actual si está disponible
        with TELEMETRIA_ACTUAL_LOCK:
            telemetria = TELEMETRIA_ACTUAL.get(cp_id)
        
        if telemetria:
            # Mostrar datos reales de telemetría
            estado = telemetria.get('estado', 'DESCONOCIDO')
            potencia_actual = telemetria.get('potencia_actual', 'N/A')
            energia_total = telemetria.get('energia_total', 'N/A')
            timestamp = telemetria.get('timestamp', 'N/A')
            
            print(f"|   Estado: {estado}")
            print(f"|   Potencia Actual: {potencia_actual} kW")
            print(f"|   Energía Total: {energia_total} kWh")
            print(f"|   Última Actualización: {timestamp}")
        else:
            print(f"|   Estado: Sin telemetría disponible")
            print(f"|   (Conectado pero sin datos de Kafka)")
        
        print("-"*60)

def interfaz_consola_central():
    """Bucle principal para la interacción del operador (UI)."""
    while True:
        print("\n[CENTRAL CMD] Opciones:")
        print("  1. MOSTRAR ESTADO DE LA RED")
        print("  2. ENVIAR COMANDO MANUAL (STOP/START)")
        print("  3. SALIR")
        
        # Usamos input() para capturar comandos del operador.
        comando = input("\n[CENTRAL CMD] (Ej: 2 CP_001 STOP) > ").strip().upper()
        
        if comando == '1':
            mostrar_estado_red()
        
        elif comando.startswith('2'):
            partes = comando.split()
            if len(partes) < 3:
                print("Uso: 2 <CP_ID> <ORDEN> (Ej: 2 CP_001 STOP)")
                continue
                
            _, cp_id, orden = partes
            
            if cp_id not in CONEXIONES_ACTIVAS:
                print(f"ERROR: CP {cp_id} no está conectado o registrado via Socket.")
                continue

            # Construcción y envío del comando (Igual que en el Kafka Consumer, pero manual)
            try:
                cp_socket = CONEXIONES_ACTIVAS[cp_id]
                
                # Usamos el código de operación que el Engine espera (Ej: START/STOP)
                trama_comando = construir_trama(orden, ['MANUAL']) # Datos extra para el Engine
                cp_socket.sendall(trama_comando)
                
                print(f"[CONTROL MANUAL] Orden '{orden}' enviada a {cp_id} con éxito.")
                
            except Exception as e:
                print(f"[CONTROL MANUAL] ERROR al enviar comando a {cp_id}: {e}. Conexión perdida.")
                
        elif comando == '3':
            print("Cerrando la Central...")
            # Activar el apagado limpio
            with SHUTDOWN_LOCK:
                global SHUTDOWN_REQUESTED
                SHUTDOWN_REQUESTED = True
            print("[CENTRAL] Señal de apagado enviada a todos los hilos...")
            break
            
        else:
            print("Comando no reconocido. Use 1, 2, o 3.")
            
def manejar_cliente(conn: socket.socket, addr: tuple, db_connection: mysql.connector.connection.MySQLConnection):
    """Función ejecutada por un hilo para manejar la conexión de un CP."""
    
    print(f"[CENTRAL] Conexión establecida con {addr[0]}:{addr[1]}")
    cp_id = "Desconocido"
    
    try:
        # Establecer timeout para permitir cierre limpio
        conn.settimeout(1.0)

        # --- 1. REGISTRO Y AUTENTICACIÓN (Primer intercambio) ---
        trama_bytes = b''
        while True:
            # Verificar si se solicita el apagado antes de bloquear
            with SHUTDOWN_LOCK:
                if SHUTDOWN_REQUESTED:
                    print(f"[CENTRAL] Apagado solicitado antes de registro, cerrando conexión con {addr[0]}:{addr[1]}...")
                    return
            try:
                trama_bytes = conn.recv(1024)
            except socket.timeout:
                continue
            if not trama_bytes:
                raise ConnectionResetError("Conexión cerrada por el cliente antes del registro.")
            break

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
            # Verificar si se solicita el apagado
            with SHUTDOWN_LOCK:
                if SHUTDOWN_REQUESTED:
                    print(f"[CENTRAL] Apagado solicitado, cerrando conexión con {cp_id}...")
                    break
            
            # Ahora el hilo espera por comandos síncronos (AVR, telemetría síncrona, etc.)
            try:
                trama_bytes = conn.recv(1024)
            except socket.timeout:
                continue
            if not trama_bytes:
                # El CP cerró la conexión
                print(f"[CENTRAL] Conexión con CP {cp_id} cerrada por el cliente.")
                break 
                
            cod_op, campos = descomponer_trama(trama_bytes)
            
            if cod_op:
                print(f"[CENTRAL] Recibida trama de {cp_id}: Cod={cod_op}, Campos={campos}")
                # Manejo de tramas específicas desde el CP
                if cod_op == 'AUTH_RESP' and len(campos) >= 2:
                    # Esperado: AUTH_RESP#<driver_id>#<OK|KO>#<mensaje?>
                    try:
                        driver_id = campos[0]
                        resultado = campos[1].upper()
                        mensaje = campos[2] if len(campos) >= 3 else ''
                        if resultado == 'OK':
                            notificar_driver(driver_id, 'AUTORIZADO', {
                                'cp_id': cp_id,
                                'mensaje': mensaje or 'Autorización concedida por CP'
                            })
                        else:
                            notificar_driver(driver_id, 'DENEGADO', {
                                'cp_id': cp_id,
                                'motivo': mensaje or 'CP denegó la autorización'
                            })
                    except Exception as e:
                        print(f"[CENTRAL] Error procesando AUTH_RESP: {e}")
                else:
                    # [Lógica para manejar AVR, Suministro síncrono, etc.]
                    pass
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

    # Inicialización del productor Kafka para notificaciones
    inicializar_kafka_producer(args.kafka)

    # Inicialización del servidor de Sockets
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Permite reutilizar el puerto
        
        server_socket.bind(('', args.port)) 
        server_socket.listen(5)
        # Timeout corto para aceptar conexiones y poder revisar el flag de apagado
        server_socket.settimeout(1.0)
        
        # Hilo para la interfaz de consola del operador
        consola_thread = threading.Thread(target=interfaz_consola_central, daemon=True)
        consola_thread.start()
        # Hilo consumidor de Kafka para telemetría
        kafka_consumer_thread = threading.Thread(
            target=consumir_telemetria_kafka,
            args=(args.kafka,),
            daemon=True
        )
        kafka_consumer_thread.start()
        # Hilo consumidor de Kafka para solicitudes de drivers
        driver_requests_thread = threading.Thread(
            target=consumir_solicitudes_driver_kafka,
            args=(args.kafka, db_connection),
            daemon=True
        )
        driver_requests_thread.start()
        print(f"[EV_Central] Servidor escuchando en TCP (:{args.port})...")

        while True:
            # Verificar si se solicita el apagado
            with SHUTDOWN_LOCK:
                if SHUTDOWN_REQUESTED:
                    print("[EV_Central] Apagado solicitado, cerrando servidor...")
                    break
            
            # Bloqueante: Espera una conexión
            try:
                conn, addr = server_socket.accept()
            except socket.timeout:
                continue
            # Iniciar un nuevo hilo para manejar la conexión de forma concurrente
            client_thread = threading.Thread(target=manejar_cliente, args=(conn, addr, db_connection))
            client_thread.start()
            with CLIENT_THREADS_LOCK:
                CLIENT_THREADS.append(client_thread)

    
    except KeyboardInterrupt:
        print("\n[EV_Central] Apagando por interrupción de usuario...")
    except Exception as e:
        print(f"[EV_Central] Error principal: {e}")
    finally:
        # Cerrar todas las conexiones activas
        print("[EV_Central] Cerrando todas las conexiones activas...")
        with CONEXIONES_ACTIVAS_LOCK:
            for cp_id, conn in CONEXIONES_ACTIVAS.items():
                try:
                    conn.close()
                    print(f"[EV_Central] Conexión con {cp_id} cerrada.")
                except:
                    pass
            CONEXIONES_ACTIVAS.clear()
        # Esperar a que terminen los hilos de clientes (con timeout)
        with CLIENT_THREADS_LOCK:
            for t in CLIENT_THREADS:
                try:
                    t.join(timeout=2.0)
                except Exception:
                    pass
            CLIENT_THREADS.clear()
        
        # Cerrar el servidor socket
        if 'server_socket' in locals():
            server_socket.close()
            print("[EV_Central] Servidor socket cerrado.")
        
        # Cerrar conexión a BD
        if db_connection and db_connection.is_connected():
            db_connection.close()
            print("[EV_Central] Conexión a BD cerrada.")
        
        print("[EV_Central] Apagado completado.")

if __name__ == "__main__":
    main()