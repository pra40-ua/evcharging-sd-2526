import socket
import argparse
import threading
import time
from collections import deque
from queue import Queue, Empty
# Intentar importar ambos conectores para tener fallback disponible
PYMySQL_AVAILABLE = False
MYSQL_CONNECTOR_AVAILABLE = False

try:
    import pymysql
    import pymysql.cursors
    PYMySQL_AVAILABLE = True
except ImportError:
    pass

try:
    import mysql.connector
    from mysql.connector import Error
    MYSQL_CONNECTOR_AVAILABLE = True
except ImportError:
    pass
from datetime import datetime
from kafka import KafkaConsumer, KafkaProducer
import json
import os
import sys
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich import box
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
import logging
import base64
import hashlib
import secrets
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from cryptography.fernet import Fernet
try:
    import msvcrt as MSVCRT
except Exception:
    MSVCRT = None

# =================================================================
#                 ESTADO GLOBAL DE CONEXIONES ACTIVAS
# =================================================================

# Diccionario de CP_ID -> socket
CONEXIONES_ACTIVAS = {}
CONEXIONES_ACTIVAS_LOCK = threading.Lock()

# Diccionario para almacenar la telemetría más reciente de cada CP
TELEMETRIA_ACTUAL = {}
TELEMETRIA_ACTUAL_LOCK = threading.Lock()

# Estado manual (START/STOP ordenado por la Central) para reflejar en TUI
CP_ESTADO_MANUAL = {}
CP_ESTADO_MANUAL_LOCK = threading.Lock()

# Estado de alerta/avería detectado (por AVR o telemetría)
CP_ALERTA = {}
CP_ALERTA_LOCK = threading.Lock()

# Estado explícito de cada CP (pilar de la TUI y lógica)
CP_ESTADO = {}
CP_ESTADO_LOCK = threading.Lock()

# Precio kWh anunciado por cada CP (desde REG)
CP_PRECIO_KWH = {}
CP_PRECIO_KWH_LOCK = threading.Lock()

# Objetivo de kWh solicitado por Driver (por CP) para mostrar durante la sesión
CP_SESION_OBJETIVO_KWH = {}
CP_SESION_OBJETIVO_KWH_LOCK = threading.Lock()

# Driver actual de la sesión (por CP) para tickets y referencia
CP_SESION_DRIVER_ID = {}
CP_SESION_DRIVER_ID_LOCK = threading.Lock()

# Cola de espera por CP (cuando múltiples drivers solicitan el mismo CP)
CP_COLA_ESPERA = {}  # cp_id -> Queue de (driver_id, kw_deseados, timestamp)
CP_COLA_ESPERA_LOCK = threading.Lock()

# Estados del flujo interactivo (para confirmaciones en web)
# cp_id -> 'LISTO_PARA_INICIAR' o 'ESPERANDO_CONFIRMACION_FIN'
CP_PENDIENTE_CONFIRMACION = {}
CP_PENDIENTE_CONFIRMACION_LOCK = threading.Lock()

# CPs con Monitor desconectado manualmente (bloqueados para reconexión automática)
CP_MONITOR_BLOQUEADO = set()  # Set de cp_ids bloqueados manualmente
CP_MONITOR_BLOQUEADO_LOCK = threading.Lock()

# Lista de hilos de clientes para cierre ordenado
CLIENT_THREADS = []
CLIENT_THREADS_LOCK = threading.Lock()

# Variable global para controlar el apagado limpio
SHUTDOWN_REQUESTED = False
SHUTDOWN_LOCK = threading.Lock()

# Cola de comandos ingresados por el operador (desde consola)
COMMAND_QUEUE: Queue = Queue()

# Registro de eventos (histórico en memoria)
EVENT_LOG = deque(maxlen=300)
EVENT_LOG_LOCK = threading.Lock()

# Claves de cifrado simétrico por CP
CP_ENCRYPTION_KEYS = {}  # cp_id -> Fernet key object
CP_ENCRYPTION_KEYS_LOCK = threading.Lock()

# Estado de alertas climatológicas
WEATHER_ALERTS = {}  # cp_id -> {'activa': bool, 'temperatura': float, 'timestamp': float}
WEATHER_ALERTS_LOCK = threading.Lock()

# Configuración de EV_Registry (enforzar HTTPS)
REGISTRY_URL = os.getenv('REGISTRY_URL', 'https://127.0.0.1:6000/api')
# Normalizar: si por error viene con http://, forzar https://
if REGISTRY_URL.startswith('http://'):
    REGISTRY_URL = 'https://' + REGISTRY_URL[len('http://'):]

# Verbosidad de logs (para evitar spam en consola)
# - CENTRAL_VERBOSE_MESSAGES=1 -> imprime cada trama recibida
# - CENTRAL_VERBOSE_MESSAGES=0 -> modo resumido (por defecto)
CENTRAL_VERBOSE_MESSAGES = os.getenv('CENTRAL_VERBOSE_MESSAGES', '0').strip() == '1'

# Operaciones ruidosas a resumir cuando CENTRAL_VERBOSE_MESSAGES=0
# (STATE suele ser frecuente; puedes añadir aquí otras si lo necesitas)
CENTRAL_NOISY_OPS = {'STATE'}

# Throttle para logs resumidos (por CP y por op)
_MSG_THROTTLE_LOCK = threading.Lock()
_MSG_THROTTLE = {}  # (cp_id, cod_op) -> {'count': int, 'last_ts': float}
_MSG_THROTTLE_SECS = float(os.getenv('CENTRAL_THROTTLE_SECS', '10').strip() or '10')

# Flask app para API REST
API_APP = Flask(__name__)
CORS(API_APP)
API_PORT = 5000  # Mismo puerto que el socket server, pero diferente endpoint

# =================================================================
#                         REGISTRO / LOGS
# =================================================================

console = Console()
# Usar una ruta compatible con Windows y Linux
log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'central.log')
logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(message)s')

def registrar_evento(mensaje: str, tipo="info") -> None:
    """Registro de eventos con Rich + logging a archivo."""
    timestamp = datetime.now().strftime('%H:%M:%S')
    linea = f"[{timestamp}] {mensaje}"
    color = {"info": "cyan", "warn": "yellow", "error": "red", "ok": "green"}.get(tipo, "white")
    with EVENT_LOG_LOCK:
        EVENT_LOG.append(linea)
    try:
        console.print(f"[{color}]{linea}[/{color}]")
    except Exception:
        try:
            print(linea)
        except Exception:
            pass
    try:
        logging.info(linea)
    except Exception:
        pass

# =================================================================
#                    FUNCIONES DE AUDITORÍA
# =================================================================

def registrar_auditoria(accion: str, cp_id: str = None, origen_ip: str = None, 
                        descripcion: str = None, resultado: str = "OK", 
                        db_connection = None) -> None:
    """
    Registra un evento de auditoría en la base de datos.
    
    Args:
        accion: Tipo de acción (ej: "AUTENTICACION", "REGISTRO", "ALERTA_CLIMA", etc.)
        cp_id: ID del CP (opcional)
        origen_ip: IP de origen (opcional)
        descripcion: Descripción detallada del evento
        resultado: Resultado de la acción ("OK", "ERROR", "DENEGADO", etc.)
        db_connection: Conexión a la base de datos
    """
    try:
        if _verificar_conexion(db_connection):
            cursor = db_connection.cursor()
            cursor.execute("""
                INSERT INTO audit_log (fecha_hora, origen_ip, cp_id, accion, descripcion, resultado)
                VALUES (NOW(), %s, %s, %s, %s, %s)
            """, (origen_ip, cp_id, accion, descripcion, resultado))
            db_connection.commit()
            cursor.close()
    except Exception as e:
        # No fallar si hay error en auditoría, solo log
        print(f"[CENTRAL] ⚠️ Error registrando auditoría: {e}")

# =================================================================
#                    FUNCIONES DE CIFRADO
# =================================================================

def generar_clave_cifrado() -> bytes:
    """Genera una nueva clave de cifrado Fernet."""
    return Fernet.generate_key()

# Archivo para guardar claves cuando no hay BD disponible
ENCRYPTION_KEYS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'encryption_keys.json')

def _cargar_claves_desde_archivo() -> dict:
    """Carga las claves de cifrado desde un archivo JSON local."""
    try:
        os.makedirs(os.path.dirname(ENCRYPTION_KEYS_FILE), exist_ok=True)
        if os.path.exists(ENCRYPTION_KEYS_FILE):
            with open(ENCRYPTION_KEYS_FILE, 'r') as f:
                data = json.load(f)
                # Convertir de base64 a bytes
                return {cp_id: base64.b64decode(key_b64) for cp_id, key_b64 in data.items()}
    except Exception as e:
        print(f"[CENTRAL] ⚠️ Error cargando claves desde archivo: {e}")
    return {}

def _guardar_claves_en_archivo(claves: dict):
    """Guarda las claves de cifrado en un archivo JSON local."""
    try:
        os.makedirs(os.path.dirname(ENCRYPTION_KEYS_FILE), exist_ok=True)
        # Convertir de bytes a base64 para JSON
        data = {cp_id: base64.b64encode(key_bytes).decode('utf-8') 
                for cp_id, key_bytes in claves.items()}
        with open(ENCRYPTION_KEYS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[CENTRAL] ⚠️ Error guardando claves en archivo: {e}")

def obtener_clave_cifrado_cp(cp_id: str, db_connection = None) -> bytes:
    """
    Obtiene la clave de cifrado para un CP.
    Si no existe, genera una nueva y la almacena.
    Usa BD si está disponible, sino usa archivo local como fallback.
    
    Returns:
        Clave de cifrado Fernet (bytes)
    """
    # Primero verificar en memoria
    with CP_ENCRYPTION_KEYS_LOCK:
        if cp_id in CP_ENCRYPTION_KEYS:
            return CP_ENCRYPTION_KEYS[cp_id]
    
    # Si no está en memoria, buscar en BD
    if _verificar_conexion(db_connection):
        try:
            cursor = _db_cursor_dict(db_connection)
            cursor.execute("""
                SELECT encryption_key FROM cp_encryption_keys 
                WHERE cp_id = %s AND activo = TRUE
            """, (cp_id,))
            resultado = cursor.fetchone()
            cursor.close()
            
            if resultado:
                # Cargar clave desde BD
                if isinstance(resultado, dict):
                    key_b64 = resultado.get('encryption_key')
                else:
                    key_b64 = resultado[0] if resultado else None
                
                if key_b64:
                    key_bytes = base64.b64decode(key_b64)
                    with CP_ENCRYPTION_KEYS_LOCK:
                        CP_ENCRYPTION_KEYS[cp_id] = key_bytes
                    return key_bytes
        except Exception as e:
            print(f"[CENTRAL] ⚠️ Error obteniendo clave de BD: {e}")
    
    # Si no está en BD, buscar en archivo local (fallback)
    claves_archivo = _cargar_claves_desde_archivo()
    if cp_id in claves_archivo:
        key_bytes = claves_archivo[cp_id]
        with CP_ENCRYPTION_KEYS_LOCK:
            CP_ENCRYPTION_KEYS[cp_id] = key_bytes
        print(f"[CENTRAL] Clave de {cp_id} cargada desde archivo local (BD no disponible)")
        return key_bytes
    
    # Si no existe, generar nueva
    nueva_clave = generar_clave_cifrado()
    
    # Almacenar en BD si está disponible
    if _verificar_conexion(db_connection):
        try:
            cursor = db_connection.cursor()
            key_b64 = base64.b64encode(nueva_clave).decode('utf-8')
            cursor.execute("""
                INSERT INTO cp_encryption_keys (cp_id, encryption_key, activo)
                VALUES (%s, %s, TRUE)
                ON DUPLICATE KEY UPDATE
                    encryption_key = VALUES(encryption_key),
                    activo = TRUE,
                    fecha_ultima_actualizacion = NOW()
            """, (cp_id, key_b64))
            db_connection.commit()
            cursor.close()
            print(f"[CENTRAL] Clave de {cp_id} guardada en BD")
        except Exception as e:
            print(f"[CENTRAL] ⚠️ Error guardando clave en BD: {e}")
            # Si falla BD, guardar en archivo
            with CP_ENCRYPTION_KEYS_LOCK:
                claves_temp = CP_ENCRYPTION_KEYS.copy()
                claves_temp[cp_id] = nueva_clave
                _guardar_claves_en_archivo(claves_temp)
                print(f"[CENTRAL] Clave de {cp_id} guardada en archivo local (BD no disponible)")
    else:
        # BD no disponible, guardar en archivo
        with CP_ENCRYPTION_KEYS_LOCK:
            claves_temp = CP_ENCRYPTION_KEYS.copy()
            claves_temp[cp_id] = nueva_clave
            _guardar_claves_en_archivo(claves_temp)
            print(f"[CENTRAL] Clave de {cp_id} guardada en archivo local (BD no disponible)")
    
    # Almacenar en memoria
    with CP_ENCRYPTION_KEYS_LOCK:
        CP_ENCRYPTION_KEYS[cp_id] = nueva_clave
    
    return nueva_clave

def _inicializar_claves_desde_archivo():
    """Carga las claves desde archivo al iniciar (si BD no está disponible)."""
    claves_archivo = _cargar_claves_desde_archivo()
    if claves_archivo:
        with CP_ENCRYPTION_KEYS_LOCK:
            CP_ENCRYPTION_KEYS.update(claves_archivo)
        print(f"[CENTRAL] {len(claves_archivo)} claves cargadas desde archivo local (BD no disponible)")

def cifrar_mensaje(mensaje: bytes, clave: bytes) -> bytes:
    """Cifra un mensaje usando Fernet."""
    fernet = Fernet(clave)
    return fernet.encrypt(mensaje)

def descifrar_mensaje(mensaje_cifrado: bytes, clave: bytes) -> bytes:
    """Descifra un mensaje usando Fernet."""
    fernet = Fernet(clave)
    return fernet.decrypt(mensaje_cifrado)

def revocar_clave_cifrado(cp_id: str, db_connection = None) -> bool:
    """
    Revoca la clave de cifrado de un CP.
    Esto forzará una nueva autenticación.
    
    Returns:
        True si se revocó correctamente
    """
    try:
        # Eliminar de memoria
        with CP_ENCRYPTION_KEYS_LOCK:
            if cp_id in CP_ENCRYPTION_KEYS:
                del CP_ENCRYPTION_KEYS[cp_id]
        
        # Marcar como inactiva en BD
        if _verificar_conexion(db_connection):
            cursor = db_connection.cursor()
            cursor.execute("""
                UPDATE cp_encryption_keys 
                SET activo = FALSE, fecha_ultima_actualizacion = NOW()
                WHERE cp_id = %s
            """, (cp_id,))
            db_connection.commit()
            cursor.close()
        
        registrar_evento(f"🔑 Clave de cifrado revocada para {cp_id}", "warn")
        return True
    except Exception as e:
        print(f"[CENTRAL] ❌ Error revocando clave: {e}")
        return False

# =================================================================
#                    FUNCIONES DE EV_Registry
# =================================================================

def verificar_registro_cp(cp_id: str, db_connection=None) -> bool:
    """
    Verifica si un CP está registrado en EV_Registry.
    
    Si db_connection está disponible, consulta directamente la tabla cp_registry
    en la BD compartida (más eficiente y no depende de red).
    Si no, intenta verificar vía HTTP con el Registry.
    
    Args:
        cp_id: ID del CP a verificar
        db_connection: Conexión opcional a la BD MySQL
    
    Returns:
        True si está registrado y activo, False en caso contrario
    """
    # Prioridad 1: Verificar desde BD compartida (más eficiente)
    if _verificar_conexion(db_connection):
        try:
            cursor = _db_cursor_dict(db_connection)
            # Verificar si la tabla cp_registry existe (puede no existir si Registry nunca se ejecutó)
            cursor.execute(
                "SELECT cp_id, activo FROM cp_registry WHERE cp_id = %s",
                (cp_id,)
            )
            registro = cursor.fetchone()
            cursor.close()
            
            if registro and registro.get('activo'):
                print(f"[CENTRAL] ✓ CP {cp_id} verificado en BD (registrado y activo)")
                return True
            elif registro:
                print(f"[CENTRAL] ⚠️ CP {cp_id} encontrado en BD pero está inactivo")
                return False
            else:
                print(f"[CENTRAL] ⚠️ CP {cp_id} NO encontrado en cp_registry (BD)")
                return False
        except Exception as e:
            # Puede ser error SQL, tabla inexistente o diferencia de driver
            error_msg = str(e).lower()
            if "doesn't exist" in error_msg or "table" in error_msg or "1146" in error_msg:
                print(f"[CENTRAL] ⚠️ Tabla cp_registry no encontrada en BD, usando método HTTP")
            else:
                print(f"[CENTRAL] ⚠️ Error consultando BD para verificar registro de {cp_id}: {e}")
            # Continuar con método HTTP como fallback
    
    # Prioridad 2: Verificar vía HTTP con Registry (si BD no disponible o falló)
    try:
        # Deshabilitar advertencias SSL para certificados autofirmados
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        url = f"{REGISTRY_URL}/cps"
        response = requests.get(url, timeout=5, verify=False)  # verify=False para certificados autofirmados
        
        if response.status_code == 200:
            data = response.json()
            cps = data.get('cps', [])
            for cp in cps:
                if cp.get('cp_id') == cp_id and cp.get('activo'):
                    print(f"[CENTRAL] ✓ CP {cp_id} verificado en Registry (HTTP)")
                    return True
        return False
    except Exception as e:
        print(f"[CENTRAL] ⚠️ Error verificando registro en EV_Registry vía HTTP: {e}")
        # Por compatibilidad, permitir conexión si EV_Registry no está disponible
        return True

def verificar_credenciales_registry(cp_id: str, username: str, password: str, db_connection=None) -> bool:
    """
    Verifica las credenciales de un CP consultando directamente la BD.
    Según los requisitos, EV_Central consulta la BD (en PC_A) para validar
    si el CP está registrado y si las credenciales son correctas.
    
    Args:
        cp_id: ID del CP
        username: Username proporcionado por EV_Registry
        password: Password proporcionado por EV_Registry
    
    Returns:
        True si las credenciales son válidas, False en caso contrario
    """
    try:
        # Usar conexión compartida si está disponible; evita reconexiones lentas durante AUTH
        connection = db_connection if _verificar_conexion(db_connection) else None
        created_conn = False
        if connection is None:
            cfg = globals().get('DB_CONFIG_STR')
            if not cfg:
                print(f"[CENTRAL] ❌ No hay configuración de BD disponible")
                return False
            connection = conectar_bd(cfg)
            created_conn = True
            if not _verificar_conexion(connection):
                print(f"[CENTRAL] ❌ No se pudo conectar a la BD para verificar credenciales")
                return False
        
        try:
            cursor = _db_cursor_dict(connection)
            
            # Verificar que el CP esté registrado y activo en cp_registry
            cursor.execute("""
                SELECT r.cp_id, r.activo as cp_activo,
                       c.username, c.password_hash, c.salt, c.activo as creds_activas
                FROM cp_registry r
                LEFT JOIN cp_credentials c ON r.cp_id = c.cp_id
                WHERE r.cp_id = %s
            """, (cp_id,))
            
            resultado = cursor.fetchone()
            cursor.close()
            if created_conn:
                try:
                    connection.close()
                except Exception:
                    pass
            
            if not resultado:
                print(f"[CENTRAL] ❌ CP {cp_id} no encontrado en cp_registry")
                return False
            
            if not resultado['cp_activo']:
                print(f"[CENTRAL] ❌ CP {cp_id} está dado de baja en cp_registry")
                return False
            
            if not resultado['username'] or not resultado['password_hash']:
                print(f"[CENTRAL] ❌ CP {cp_id} no tiene credenciales registradas")
                return False
            
            if not resultado['creds_activas']:
                print(f"[CENTRAL] ❌ Las credenciales del CP {cp_id} están desactivadas")
                return False
            
            # Verificar que el username coincida
            if resultado['username'] != username:
                print(f"[CENTRAL] ❌ Username no coincide para CP {cp_id}")
                return False
            
            # Verificar password usando SHA256 con salt (misma lógica que EV_Registry)
            salt = resultado.get('salt', '')
            if not salt:
                print(f"[CENTRAL] ❌ CP {cp_id} tiene credenciales sin salt (requiere regeneración)")
                return False
            
            # Calcular hash del password proporcionado
            combined = f"{password}{salt}".encode('utf-8')
            hash_calculado = hashlib.sha256(combined).hexdigest()
            
            if hash_calculado != resultado['password_hash']:
                print(f"[CENTRAL] ❌ Password incorrecto para CP {cp_id}")
                return False
            
            print(f"[CENTRAL] ✓ Credenciales verificadas en BD para CP {cp_id}")
            return True
            
        except Exception as e:
            print(f"[CENTRAL] ❌ Error de BD verificando credenciales: {e}")
            if created_conn:
                try:
                    connection.close()
                except Exception:
                    pass
            return False
            
    except Exception as e:
        print(f"[CENTRAL] ❌ Error verificando credenciales: {e}")
        import traceback
        traceback.print_exc()
        return False

# =================================================================
#                    API REST - ALERTAS DE CLIMA
# =================================================================

@API_APP.route('/api/weather_alert', methods=['POST'])
def api_weather_alert():
    """
    Endpoint para recibir alertas climatológicas de EV_W.
    
    Body JSON:
        {
            "cp_id": "CP001",
            "temperatura": -5.0,
            "alerta_activa": true,
            "timestamp": "2024-01-01T12:00:00"
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No se proporcionó JSON en el body'
            }), 400
        
        cp_id = data.get('cp_id')
        temperatura = data.get('temperatura')
        alerta_activa = data.get('alerta_activa', False)
        
        if not cp_id:
            return jsonify({
                'status': 'error',
                'message': 'cp_id es requerido'
            }), 400
        
        # Verificar si la alerta realmente cambió para evitar procesamiento duplicado
        alerta_anterior = None
        with WEATHER_ALERTS_LOCK:
            alerta_anterior = WEATHER_ALERTS.get(cp_id, {}).get('activa')
            # Solo procesar si la alerta cambió de estado
            if alerta_anterior == alerta_activa:
                # No hay cambio, solo actualizar temperatura y timestamp sin procesar
                WEATHER_ALERTS[cp_id] = {
                    'activa': alerta_activa,
                    'temperatura': temperatura,
                    'timestamp': time.time()
                }
                return jsonify({
                    'status': 'ok',
                    'message': f'Alerta sin cambio para {cp_id} (ya estaba {"activa" if alerta_activa else "inactiva"})'
                })
            # Actualizar estado de alerta
            WEATHER_ALERTS[cp_id] = {
                'activa': alerta_activa,
                'temperatura': temperatura,
                'timestamp': time.time()
            }
        
        # Registrar en BD si hay conexión
        db_conn = globals().get('_DB_CONN_FOR_API')
        if db_conn and _verificar_conexion(db_conn):
            try:
                cursor = db_conn.cursor()
                cursor.execute("""
                    INSERT INTO weather_alerts (cp_id, temperatura, alerta_activa, fecha_hora)
                    VALUES (%s, %s, %s, NOW())
                """, (cp_id, temperatura, alerta_activa))
                db_conn.commit()
                cursor.close()
            except Exception as e:
                print(f"[CENTRAL] ⚠️ Error guardando alerta en BD: {e}")
        
        # Si hay alerta activa, cambiar estado a FUERA_DE_SERVICIO inmediatamente
        if alerta_activa:
            with CP_ESTADO_LOCK:
                estado_cp = CP_ESTADO.get(cp_id, '')
            
            # Cambiar estado a FUERA_DE_SERVICIO inmediatamente (incluso si está suministrando)
            try:
                cambiar_estado_cp(cp_id, 'FUERA_DE_SERVICIO', db_conn)
                registrar_evento(f"⚠️ CP {cp_id} fuera de servicio por alerta climatológica (T={temperatura}°C)", "warn")
            except Exception as e:
                print(f"[CENTRAL] ⚠️ Error cambiando estado a FUERA_DE_SERVICIO: {e}")
            
            # Si está suministrando, enviar STOP para detener el suministro inmediatamente
            if estado_cp == 'SUMINISTRANDO' or estado_cp == 'CARGANDO':
                registrar_evento(f"⚠️ Alerta climatológica activa para {cp_id} (T={temperatura}°C). Deteniendo suministro activo.", "warn")
                # Enviar STOP para que finalice el suministro actual
                try:
                    with CONEXIONES_ACTIVAS_LOCK:
                        conn = CONEXIONES_ACTIVAS.get(cp_id)
                    if conn:
                        # Enviar STOP cifrado al CP
                        trama_stop = construir_trama('STOP', [], cp_id=cp_id, cifrar=True)
                        conn.sendall(trama_stop)
                        print(f"[CENTRAL] 📤 STOP enviado a {cp_id} por alerta climatológica (T={temperatura}°C)")
                        registrar_evento(f"📤 STOP enviado a {cp_id} por alerta climatológica", "warn")
                except Exception as e:
                    print(f"[CENTRAL] ⚠️ Error enviando STOP a {cp_id}: {e}")
            
            # Publicar telemetría actualizada para que el dashboard refleje el cambio
            try:
                with TELEMETRIA_ACTUAL_LOCK:
                    telemetria_actual = TELEMETRIA_ACTUAL.get(cp_id, {})
                telemetria_actualizada = {
                    **telemetria_actual,
                    'cp_id': cp_id,
                    'estado': 'FUERA_DE_SERVICIO',
                    'estado_carga': 'FUERA_DE_SERVICIO',
                    'timestamp': time.time(),
                    'alerta_clima_activa': True,
                    'temperatura': temperatura
                }
                with TELEMETRIA_ACTUAL_LOCK:
                    TELEMETRIA_ACTUAL[cp_id] = telemetria_actualizada
                if KAFKA_PRODUCER:
                    KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_actualizada)
                    KAFKA_PRODUCER.flush(timeout=1)
                    print(f"[CENTRAL] Telemetría publicada para {cp_id}: FUERA_DE_SERVICIO (alerta climatológica)")
            except Exception as e:
                print(f"[CENTRAL] ⚠️ Error publicando telemetría de alerta: {e}")
        else:
            # Alerta desactivada, restaurar operación (solo si no está en avería o estado interactivo)
            try:
                # Verificar estado actual antes de cambiar
                with CP_ESTADO_LOCK:
                    estado_actual = CP_ESTADO.get(cp_id, '')
                with CP_ALERTA_LOCK:
                    tiene_averia = CP_ALERTA.get(cp_id, False)
                
                estados_interactivos = {
                    'PENDIENTE_CONFIRMACION_CENTRAL',
                    'ESPERANDO_OPERADOR_ENGINE',
                    'LISTO_PARA_INICIAR',
                    'ESPERANDO_CONFIRMACION_FIN',
                    'CARGANDO',
                    'SUMINISTRANDO'
                }
                
                # Solo restaurar a ACTIVADO si no está en avería, no está en estado interactivo, y no está ya en ACTIVADO
                if not tiene_averia and estado_actual.upper() not in estados_interactivos:
                    if estado_actual.upper() != 'ACTIVADO':
                        cambiar_estado_cp(cp_id, 'ACTIVADO', db_conn)
                        registrar_evento(f"✓ CP {cp_id} restaurado tras alerta climatológica (T={temperatura}°C)", "ok")
                        
                        # Enviar señal STATE al Monitor para notificar que el CP vuelve a estar ACTIVADO
                        try:
                            with CONEXIONES_ACTIVAS_LOCK:
                                conn = CONEXIONES_ACTIVAS.get(cp_id)
                            if conn:
                                # Enviar STATE cifrado al Monitor para notificar el cambio a ACTIVADO
                                trama_state = construir_trama('STATE', [cp_id, 'ACTIVADO'], cp_id=cp_id, cifrar=True)
                                conn.sendall(trama_state)
                                print(f"[CENTRAL] 📤 STATE ACTIVADO enviado a {cp_id} (alerta climatológica desactivada)")
                                registrar_evento(f"📤 STATE ACTIVADO enviado a {cp_id} tras desactivar alerta climatológica", "ok")
                        except Exception as e:
                            print(f"[CENTRAL] ⚠️ Error enviando STATE a {cp_id}: {e}")
                    else:
                        # Ya está en ACTIVADO, no hacer nada más
                        print(f"[CENTRAL] CP {cp_id} ya está en ACTIVADO, no se necesita restaurar")
                else:
                    # No restaurar porque está en avería o estado interactivo
                    motivo_no_restaurar = 'en avería' if tiene_averia else f'en estado interactivo ({estado_actual})'
                    print(f"[CENTRAL] CP {cp_id} no se restaura a ACTIVADO: está {motivo_no_restaurar}")
                
                # Publicar telemetría actualizada para que el dashboard refleje el cambio
                try:
                    with TELEMETRIA_ACTUAL_LOCK:
                        telemetria_actual = TELEMETRIA_ACTUAL.get(cp_id, {})
                    telemetria_actualizada = {
                        **telemetria_actual,
                        'cp_id': cp_id,
                        'estado': 'ACTIVADO',
                        'estado_carga': 'ACTIVADO',
                        'timestamp': time.time(),
                        'alerta_clima_activa': False,
                        'temperatura': temperatura
                    }
                    with TELEMETRIA_ACTUAL_LOCK:
                        TELEMETRIA_ACTUAL[cp_id] = telemetria_actualizada
                    if KAFKA_PRODUCER:
                        KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_actualizada)
                        KAFKA_PRODUCER.flush(timeout=1)
                        print(f"[CENTRAL] Telemetría publicada para {cp_id}: ACTIVADO (alerta climatológica desactivada)")
                except Exception as e:
                    print(f"[CENTRAL] ⚠️ Error publicando telemetría de restauración: {e}")
            except Exception:
                pass
        
        # Registrar auditoría
        registrar_auditoria(
            accion="ALERTA_CLIMA",
            cp_id=cp_id,
            origen_ip=request.remote_addr,
            descripcion=f"Alerta climatológica: T={temperatura}°C, activa={alerta_activa}",
            resultado="OK",
            db_connection=db_conn
        )
        
        return jsonify({
            'status': 'ok',
            'message': f'Alerta procesada para {cp_id}',
            'cp_id': cp_id,
            'alerta_activa': alerta_activa
        }), 200
        
    except Exception as e:
        print(f"[CENTRAL] ❌ Error procesando alerta climatológica: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': f'Error interno: {str(e)}'
        }), 500

@API_APP.route('/api/status', methods=['GET'])
def api_status_central():
    """Endpoint para consultar el estado de la Central."""
    try:
        with CONEXIONES_ACTIVAS_LOCK:
            cps_conectados = list(CONEXIONES_ACTIVAS.keys())
        
        with CP_ESTADO_LOCK:
            estados = dict(CP_ESTADO)
        
        with WEATHER_ALERTS_LOCK:
            alertas = dict(WEATHER_ALERTS)
        
        return jsonify({
            'status': 'ok',
            'cps_conectados': len(cps_conectados),
            'cps_ids': cps_conectados,
            'estados': estados,
            'alertas_clima': alertas
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@API_APP.route('/api/revoke_key/<cp_id>', methods=['POST'])
def api_revoke_key(cp_id):
    """Endpoint para revocar la clave de cifrado de un CP."""
    try:
        db_conn = globals().get('_DB_CONN_FOR_API')
        if revocar_clave_cifrado(cp_id, db_conn):
            registrar_auditoria(
                accion="REVOCACION_CLAVE",
                cp_id=cp_id,
                origen_ip=request.remote_addr,
                descripcion="Clave de cifrado revocada manualmente",
                resultado="OK",
                db_connection=db_conn
            )
            return jsonify({
                'status': 'ok',
                'message': f'Clave revocada para {cp_id}'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': f'Error revocando clave para {cp_id}'
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def iniciar_api_rest(port: int, db_connection):
    """Inicia el servidor Flask para la API REST en un hilo separado."""
    global _DB_CONN_FOR_API
    _DB_CONN_FOR_API = db_connection
    print(f"[CENTRAL] Iniciando API REST en puerto {port}...")
    API_APP.run(host='0.0.0.0', port=port, debug=False, threaded=True, use_reloader=False)

def resumen_telemetria(telemetria: dict) -> str:
    """Devuelve un breve resumen textual de una telemetría para logs."""
    if not isinstance(telemetria, dict):
        return "-"
    estado = telemetria.get('estado') or telemetria.get('estado_carga') or 'N/D'
    energia = (
        telemetria.get('energia_total')
        if 'energia_total' in telemetria
        else telemetria.get('kwh', telemetria.get('kw_entregados', 'N/D'))
    )
    potencia = telemetria.get('potencia_actual', 'N/D')
    try:
        energia_str = f"{float(energia):.2f}" if energia not in ('N/D', None) else 'N/D'
    except Exception:
        energia_str = str(energia)
    return f"est={estado}, E={energia_str}, P={potencia}"

def bucle_entrada_comandos_windows() -> None:
    """Lector no bloqueante de teclado en Windows usando msvcrt.
    Acepta:
      - Teclas rápidas: '1' y '3' (si el buffer está vacío)
      - Comandos completos: escribir texto y pulsar Enter (\r)
    """
    if MSVCRT is None:
        # Fallback: usar entrada clásica por consola si MSVCRT no está disponible
        interfaz_consola_central()
        return
    buffer_chars = []
    while True:
        with SHUTDOWN_LOCK:
            if SHUTDOWN_REQUESTED:
                return
        try:
            if MSVCRT.kbhit():
                ch = MSVCRT.getwch()
                if ch in ('\r', '\n'):
                    cmd = ''.join(buffer_chars).strip()
                    buffer_chars = []
                    if cmd:
                        COMMAND_QUEUE.put(cmd)
                        registrar_evento(f"Entrada recibida: {cmd}")
                elif ch in ('\x08', '\x7f'):  # Backspace
                    if buffer_chars:
                        buffer_chars.pop()
                elif not buffer_chars and ch == '1':
                    # Atajo rápido para refrescar estado
                    COMMAND_QUEUE.put(ch)
                    registrar_evento(f"Entrada rápida: {ch}")
                elif ch == '\x03':  # Ctrl+C
                    # No cerrar inmediatamente, requerir confirmación
                    COMMAND_QUEUE.put('EXIT')
                    registrar_evento("Entrada Ctrl+C -> Requiere confirmación para salir")
                else:
                    # Acumular caracteres para comandos largos (ej.: 2 START CP001)
                    # Filtrar caracteres no imprimibles básicos
                    if ch.isprintable() or ch == ' ':
                        buffer_chars.append(ch)
            else:
                time.sleep(0.05)
        except Exception:
            # En caso de error inesperado, pequeño backoff
            time.sleep(0.1)

def _enviar_comando_cp(cp_id: str, orden: str) -> bool:
    with CONEXIONES_ACTIVAS_LOCK:
        cp_socket = CONEXIONES_ACTIVAS.get(cp_id)
    if not cp_socket:
        registrar_evento(f"ERROR: CP {cp_id} no conectado")
        return False
    try:
        # Para START, necesitamos enviar los parámetros de sesión si existen
        if orden.upper() == 'START':
            # Obtener los parámetros de la sesión activa
            with CP_SESION_DRIVER_ID_LOCK:
                driver_id = CP_SESION_DRIVER_ID.get(cp_id)
            with CP_SESION_OBJETIVO_KWH_LOCK:
                kw_objetivo = CP_SESION_OBJETIVO_KWH.get(cp_id)
            
            if driver_id and kw_objetivo:
                # Hay sesión activa válida: iniciar carga
                trama = construir_trama('START', [driver_id, str(kw_objetivo)], cp_id=cp_id, cifrar=True)
                registrar_evento(f"Iniciando carga en {cp_id} (Driver: {driver_id}, kW: {kw_objetivo})")
            else:
                # Sin sesión activa: NO se puede iniciar
                registrar_evento(f"ERROR: No hay sesión activa en {cp_id}. Se requiere solicitud de driver primero.", "error")
                return False
        else:
            # Para STOP y otros comandos
            trama = construir_trama(orden, ['MANUAL'], cp_id=cp_id, cifrar=True)
        
        cp_socket.sendall(trama)
        
        if orden.upper() == 'START':
            # Publicar telemetría actualizada con sesión activa
            try:
                with CP_SESION_DRIVER_ID_LOCK:
                    driver_id_sesion = CP_SESION_DRIVER_ID.get(cp_id)
                with TELEMETRIA_ACTUAL_LOCK:
                    telemetria_actual = TELEMETRIA_ACTUAL.get(cp_id, {})
                telemetria_actualizada = {
                    **telemetria_actual,
                    'cp_id': cp_id,
                    'estado_carga': 'PRE-SUMINISTRO',
                    'estado': 'PRE-SUMINISTRO',
                    'timestamp': time.time(),
                    'tiene_sesion_activa': True,
                    'driver_id_sesion': driver_id_sesion
                }
                with TELEMETRIA_ACTUAL_LOCK:
                    TELEMETRIA_ACTUAL[cp_id] = telemetria_actualizada
                if KAFKA_PRODUCER:
                    KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_actualizada)
                    KAFKA_PRODUCER.flush(timeout=1)
                    print(f"[CENTRAL] Telemetría actualizada publicada para {cp_id} (sesión iniciada manualmente)")
            except Exception as e:
                print(f"[CENTRAL] No se pudo publicar telemetría actualizada: {e}")
        elif orden.upper() == 'STOP':
            # Al hacer STOP, el CP enviará FIN con los datos finales
            # No limpiamos la sesión aquí, se limpiará al recibir FIN
            registrar_evento(f"Enviando STOP a {cp_id}. Esperando FIN con datos finales...")
            print(f"[CENTRAL] Comando STOP enviado a {cp_id}. Aguardando respuesta FIN del CP...")
        
        registrar_evento(f"Comando {orden} enviado a {cp_id}")
        return True
    except Exception as e:
        registrar_evento(f"ERROR enviando {orden} a {cp_id}: {e}")
        return False

def bucle_procesador_comandos() -> None:
    global SHUTDOWN_REQUESTED
    while True:
        with SHUTDOWN_LOCK:
            if SHUTDOWN_REQUESTED:
                return
        try:
            cmd = COMMAND_QUEUE.get(timeout=0.25)
        except Empty:
            continue
        texto = cmd.strip()
        up = texto.upper()
        if up == '1':
            # Mostrar todos los CP (engines/monitores) conectados y su estado
            try:
                mostrar_estado_red()
            except Exception:
                registrar_evento("Error mostrando estado de la red")
            continue
        if up == '3' or up == 'EXIT' or up == 'QUIT':
            # Requerir confirmación para evitar cierres accidentales
            registrar_evento("⚠️ Comando de SALIDA recibido. Se requiere confirmación: escribe 'EXIT CONFIRM' para salir", "warn")
            print("\n" + "="*70)
            print("  ⚠️⚠️⚠️  ADVERTENCIA: COMANDO DE SALIDA DETECTADO  ⚠️⚠️⚠️")
            print("="*70)
            print("  Para CONFIRMAR el cierre del sistema, escribe:")
            print("  EXIT CONFIRM")
            print("="*70 + "\n")
            continue
        if up == 'EXIT CONFIRM':
            registrar_evento("✓ Apagado CONFIRMADO por operador", "warn")
            print("\n" + "="*70)
            print("  🛑 CERRANDO SISTEMA CENTRAL...")
            print("="*70 + "\n")
            with SHUTDOWN_LOCK:
                SHUTDOWN_REQUESTED = True
            continue
        # Comando tipo: admite "2 CP_001 START" o "2 START CP_001"
        if up.startswith('2'):
            partes = texto.split()
            if len(partes) < 3:
                registrar_evento("Uso: 2 START|STOP CP_ID (ej.: 2 START CP001)")
                continue
            token_a = partes[1].upper()
            token_b = partes[2].upper()
            orden = None
            cp_id = None
            if token_a in ("START", "STOP") and token_b not in ("START", "STOP"):
                orden = token_a
                cp_id = partes[2]
            elif token_b in ("START", "STOP") and token_a not in ("START", "STOP"):
                orden = token_b
                cp_id = partes[1]
            else:
                registrar_evento("Uso: 2 START|STOP CP_ID (ej.: 2 START CP001)")
                continue
            _enviar_comando_cp(cp_id, orden)
            continue
        # También admitir formato directo: START CP_ID o STOP CP_ID
        if up.startswith('START ') or up.startswith('STOP '):
            partes = texto.split()
            if len(partes) >= 2:
                orden = partes[0].upper()
                cp_id = partes[1]
                _enviar_comando_cp(cp_id, orden)
                continue
        registrar_evento(f"Comando no reconocido: {texto}")

# =================================================================
#                         FUNCIONES DE PROTOCOLO
# =================================================================

# Constantes de Protocolo
STX = b'\x02'
ETX = b'\x03'
DELIMITER = '#'
TELEMETRIA_TOPIC = 'telemetria_cp'

def _extraer_tramas_desde_buffer(rx_buffer: bytes) -> tuple[list, bytes]:
    """
    Extrae tramas completas del buffer TCP.
    Formato: STX + DATA + ETX + LRC

    Nota: el DATA cifrado usa Fernet (base64 urlsafe) con prefijo 'ENC', por lo que
    el byte ETX (0x03) no debería aparecer dentro del DATA.
    """
    if not rx_buffer:
        return [], b''

    frames = []
    buf = rx_buffer

    while True:
        # Buscar inicio de trama
        stx_idx = buf.find(STX)
        if stx_idx < 0:
            # No hay STX: descartar todo
            return frames, b''
        if stx_idx > 0:
            # Descartar basura antes de STX
            buf = buf[stx_idx:]

        # Buscar ETX tras STX
        etx_idx = buf.find(ETX, 1)
        if etx_idx < 0:
            # No hay ETX todavía: esperar más datos
            return frames, buf

        # Necesitamos también el LRC (1 byte) después del ETX
        if len(buf) < etx_idx + 2:
            return frames, buf

        frame = buf[:etx_idx + 2]  # incluye STX..ETX..LRC
        frames.append(frame)
        buf = buf[etx_idx + 2:]

        if not buf:
            return frames, b''

def _validar_trama_lrc_y_formato(trama_bytes: bytes) -> bool:
    """Valida STX/ETX y LRC sin descifrar (LRC se calcula sobre DATA original)."""
    try:
        if not trama_bytes or len(trama_bytes) < 4:
            return False
        # STX al inicio, ETX justo antes del LRC
        if not (trama_bytes.startswith(STX) and trama_bytes[-2:-1] == ETX):
            return False
        data_bytes = trama_bytes[1:-2]   # DATA (posible ENC+fernet)
        lrc_recibido = trama_bytes[-1:]
        lrc_calculado = calcular_lrc(data_bytes)
        return lrc_recibido == lrc_calculado
    except Exception:
        return False
DRIVER_REQUESTS_TOPIC = 'driver_requests'
CENTRAL_COMMANDS_TOPIC = 'central_commands'

# Productor Kafka global para notificar a Drivers
KAFKA_PRODUCER = None
KAFKA_PRODUCER_LOCK = threading.Lock()

# Configuración de BD global para reconexión
DB_CONFIG_STR = None

def _db_cursor_dict(connection):
    """
    Devuelve un cursor "dict" compatible con PyMySQL y mysql.connector.
    - PyMySQL: en conectar_bd usamos DictCursor, así que cursor() ya devuelve dicts.
    - mysql.connector: cursor(dictionary=True) devuelve dicts.
    """
    if connection is None:
        return None
    try:
        return connection.cursor(dictionary=True)
    except TypeError:
        # PyMySQL no soporta dictionary=True
        return connection.cursor()

def publicar_telemetria_kafka(cp_id: str, telemetria_data: dict):
    """
    Publica telemetría actualizada a Kafka para que el dashboard la vea.
    """
    try:
        if KAFKA_PRODUCER:
            # Enriquecer con información de sesión
            with CP_SESION_DRIVER_ID_LOCK:
                telemetria_data['tiene_sesion_activa'] = cp_id in CP_SESION_DRIVER_ID
                telemetria_data['driver_id_sesion'] = CP_SESION_DRIVER_ID.get(cp_id, None)
            
            # Asegurar campos obligatorios
            if 'timestamp' not in telemetria_data:
                telemetria_data['timestamp'] = time.time()
            if 'cp_id' not in telemetria_data:
                telemetria_data['cp_id'] = cp_id
            
            # Publicar a Kafka
            KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_data)
            KAFKA_PRODUCER.flush(timeout=1)
            print(f"[CENTRAL] → Telemetría de {cp_id} publicada a Kafka: kW={telemetria_data.get('kw_entregados', 0)}, P={telemetria_data.get('potencia_actual', 0)}")
    except Exception as e:
        print(f"[CENTRAL] Error publicando telemetría a Kafka: {e}")

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
            security_protocol='PLAINTEXT',
            api_version=(2, 5, 0),
            # Deserializador para convertir los bytes del mensaje a un diccionario de Python
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            # Si hay offset confirmado previo, retomamos desde ahí; si no, desde lo más reciente
            auto_offset_reset='latest',
            enable_auto_commit=True,
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
                    mensaje_recibido = message.value
                    cp_id = mensaje_recibido.get('cp_id', 'UNKNOWN')

                    # Validar que el CP esté REGISTRADO/CONECTADO por socket
                    with CONEXIONES_ACTIVAS_LOCK:
                        conectado = cp_id in CONEXIONES_ACTIVAS
                    if not conectado:
                        continue
                    
                    # --- DESCIFRAR MENSAJE SI ESTÁ CIFRADO ---
                    telemetria = None
                    error_descifrado = False
                    
                    # Verificar si el mensaje tiene formato cifrado (tiene 'payload')
                    if 'payload' in mensaje_recibido:
                        # Mensaje cifrado: descifrar usando la clave del CP
                        try:
                            payload_cifrado_b64 = mensaje_recibido['payload']
                            payload_cifrado = base64.b64decode(payload_cifrado_b64)
                            
                            # Obtener clave de cifrado del CP
                            clave_cifrado = obtener_clave_cifrado_cp(cp_id, None)
                            if not clave_cifrado:
                                raise Exception(f"No hay clave de cifrado para {cp_id}")
                            
                            # Descifrar usando Fernet
                            fernet = Fernet(clave_cifrado)
                            mensaje_descifrado = fernet.decrypt(payload_cifrado)
                            telemetria = json.loads(mensaje_descifrado.decode('utf-8'))
                            
                            # Reset contador de errores si descifrado exitoso
                            # (el contador se maneja en el except)
                            
                        except Exception as e:
                            # Error al descifrar - clave incorrecta o mensaje corrupto
                            error_descifrado = True
                            print(f"\n[CENTRAL] ╔═══════════════════════════════════════════╗")
                            print(f"[CENTRAL] ║  🚨 INCIDENCIA DE COMUNICACIÓN            ║")
                            print(f"[CENTRAL] ╚═══════════════════════════════════════════╝")
                            print(f"[CENTRAL]    CP: {cp_id}")
                            print(f"[CENTRAL]    Error: No se pudo descifrar mensaje de Kafka")
                            print(f"[CENTRAL]    Causa: {str(e)}")
                            print(f"[CENTRAL]    Posible discrepancia en clave de cifrado")
                            print(f"[CENTRAL] ═══════════════════════════════════════════\n")
                            
                            registrar_evento(f"🚨 INCIDENCIA: Error descifrando mensaje de {cp_id} - Clave incorrecta o corrupta", "error")
                            
                            # Registrar en auditoría
                            try:
                                db_conn = globals().get('_DB_CONN_FOR_CONSUMER')
                                if db_conn and _verificar_conexion(db_conn):
                                    registrar_auditoria(
                                        accion="ERROR_DESCIFRADO_KAFKA",
                                        cp_id=cp_id,
                                        origen_ip="kafka",
                                        descripcion=f"Error descifrando mensaje de Kafka: {str(e)}",
                                        resultado="ERROR",
                                        db_connection=db_conn
                                    )
                            except Exception:
                                pass
                            
                            # Continuar con el siguiente mensaje
                            continue
                    else:
                        # Mensaje sin cifrar (modo compatibilidad)
                        telemetria = mensaje_recibido

                    # --- Almacenar telemetría en estructura global ---
                    # Asegurar timestamp presente para heartbeat/TUI
                    if 'timestamp' not in telemetria or not telemetria.get('timestamp'):
                        telemetria['timestamp'] = time.time()
                    
                    # Verificar estado autoritativo antes de almacenar (preservar estados interactivos)
                    with CP_ESTADO_LOCK:
                        estado_autoritativo = CP_ESTADO.get(cp_id, 'ACTIVADO')
                    
                    estados_interactivos = {
                        'PENDIENTE_CONFIRMACION_CENTRAL',
                        'ESPERANDO_OPERADOR_ENGINE',
                        'LISTO_PARA_INICIAR',
                        'ESPERANDO_CONFIRMACION_FIN'
                    }
                    
                    # Si está en estado interactivo, preservar el estado autoritativo en la telemetría almacenada
                    if estado_autoritativo.upper() in estados_interactivos:
                        telemetria['estado'] = estado_autoritativo
                        telemetria['estado_carga'] = estado_autoritativo
                    
                    # Mapear ESPERANDO_DRIVER a ESPERANDO_OPERADOR_ENGINE si viene del Engine
                    if telemetria.get('estado', '').upper() == 'ESPERANDO_DRIVER' or telemetria.get('estado_carga', '').upper() == 'ESPERANDO_DRIVER':
                        telemetria['estado'] = 'ESPERANDO_OPERADOR_ENGINE'
                        telemetria['estado_carga'] = 'ESPERANDO_OPERADOR_ENGINE'
                    
                    # Enriquecer telemetría con información de sesión activa
                    with CP_SESION_DRIVER_ID_LOCK:
                        telemetria['tiene_sesion_activa'] = cp_id in CP_SESION_DRIVER_ID
                        telemetria['driver_id_sesion'] = CP_SESION_DRIVER_ID.get(cp_id, None)
                    
                    with TELEMETRIA_ACTUAL_LOCK:
                        TELEMETRIA_ACTUAL[cp_id] = telemetria

                    # --- Guardar histórico de telemetría en BD si disponible ---
                    try:
                        # Intentar usar variable cerrada sobre db_connection si existe en enclosing scope
                        db_conn = globals().get('_DB_CONN_FOR_CONSUMER')
                        if db_conn and _verificar_conexion(db_conn):
                            cursor = db_conn.cursor()
                            cursor.execute("""
                                INSERT INTO telemetria_log (cp_id, timestamp, estado_carga, kw_entregados, tiempo_carga_s)
                                VALUES (%s, %s, %s, %s, %s)
                            """, (
                                cp_id,
                                telemetria.get('timestamp', time.time()),
                                telemetria.get('estado_carga', telemetria.get('estado', 'N/D')),
                                telemetria.get('kw_entregados', telemetria.get('energia_total', 0.0)),
                                telemetria.get('tiempo_carga_s', 0)
                            ))
                            db_conn.commit()
                            cursor.close()
                    except Exception as e:
                        registrar_evento(f"[WARN] No se pudo registrar telemetría: {e}", "warn")

                    # --- Lógica principal del Central ---
                    # Mostrar objetivo solicitado si existe
                    objetivo_txt = ''
                    objetivo_kwh = None
                    try:
                        with CP_SESION_OBJETIVO_KWH_LOCK:
                            obj = CP_SESION_OBJETIVO_KWH.get(cp_id)
                        if obj is not None:
                            objetivo_kwh = float(obj)
                            objetivo_txt = f" | Solicitado={objetivo_kwh:.2f} kWh"
                    except Exception:
                        objetivo_txt = ''
                    
                    # Mostrar telemetría detallada en consola
                    resumen = resumen_telemetria(telemetria)
                    print(f"\n[KAFKA] ═══════════════════════════════════════════")
                    print(f"[KAFKA] 📊 TELEMETRÍA de {cp_id}")
                    print(f"[KAFKA]    Estado: {telemetria.get('estado_carga', 'N/D')}")
                    print(f"[KAFKA]    Potencia: {telemetria.get('potencia_actual', 0.0):.2f} kW")
                    print(f"[KAFKA]    Energía: {telemetria.get('kw_entregados', telemetria.get('energia_total', 0.0)):.3f} kWh{objetivo_txt}")
                    print(f"[KAFKA]    Tiempo: {telemetria.get('tiempo_carga_s', 0)} s")
                    if telemetria.get('driver_id_sesion'):
                        print(f"[KAFKA]    Driver: {telemetria.get('driver_id_sesion')}")
                    print(f"[KAFKA] ═══════════════════════════════════════════\n")
                    
                    registrar_evento(f"📊 Telemetría de {cp_id}: {resumen}{objetivo_txt}")
                    print(f"[KAFKA CONSUMER] -> Telemetría de {cp_id} recibida: {telemetria}{objetivo_txt}")

                    # Promover estados por telemetría (respetando PARADO manual y evitando regresiones)
                    est_raw = telemetria.get('estado') or telemetria.get('estado_carga')
                    est = str(est_raw or '').strip().lower()
                    try:
                        # Mapear ESPERANDO_DRIVER del Engine a ESPERANDO_OPERADOR_ENGINE en Central
                        if est in ("esperando_driver", "esperando driver"):
                            est = "esperando_operador_engine"
                            est_raw = "ESPERANDO_OPERADOR_ENGINE"
                        
                        # Verificar estado actual para no sobrescribir estados interactivos
                        with CP_ESTADO_LOCK:
                            estado_actual = CP_ESTADO.get(cp_id, '')
                        
                        estados_interactivos = {
                            'PENDIENTE_CONFIRMACION_CENTRAL',
                            'ESPERANDO_OPERADOR_ENGINE',
                            'LISTO_PARA_INICIAR',
                            'ESPERANDO_CONFIRMACION_FIN'
                        }
                        
                        # No sobrescribir si está en un estado interactivo (excepto si viene SUMINISTRANDO)
                        en_estado_interactivo = estado_actual.upper() in estados_interactivos
                        
                        manual_parado = False
                        with CP_ESTADO_MANUAL_LOCK:
                            manual_parado = CP_ESTADO_MANUAL.get(cp_id) == 'PARADO'
                        
                        # Evitar regresión: si ya está CARGANDO/SUMINISTRANDO, ignorar LISTO_PARA_INICIAR
                        if str(estado_actual).upper() in ("CARGANDO", "SUMINISTRANDO") and est in ("listo_para_iniciar", "listo para iniciar"):
                            print(f"[KAFKA CONSUMER] Ignorando regresión de {cp_id}: {estado_actual} -> {est_raw}")
                            pass
                        
                        if est in ("cargando", "suministrando", "charging", "en_carga"):
                            if not manual_parado:
                                # Mostrar objetivo en el mensaje de cambio de estado
                                estado_info = f'SUMINISTRANDO{objetivo_txt}'
                                cambiar_estado_cp(cp_id, 'SUMINISTRANDO')
                                if objetivo_kwh:
                                    energia_actual = telemetria.get('kw_entregados', 0.0)
                                    try:
                                        progreso = (float(energia_actual) / objetivo_kwh) * 100
                                        print(f"[{cp_id}] Progreso: {energia_actual:.2f}/{objetivo_kwh:.2f} kWh ({progreso:.1f}%)")
                                    except Exception:
                                        pass
                        elif est == "esperando_operador_engine":
                            # Mapear ESPERANDO_DRIVER a ESPERANDO_OPERADOR_ENGINE
                            if not en_estado_interactivo or estado_actual.upper() != 'ESPERANDO_OPERADOR_ENGINE':
                                cambiar_estado_cp(cp_id, 'ESPERANDO_OPERADOR_ENGINE')
                        elif est in ("finalizado", "reposo", "idle", "ready", "activado"):
                            # Solo volver a ACTIVADO si no está PARADO manualmente Y no está en estado interactivo
                            if not manual_parado and not en_estado_interactivo:
                                cambiar_estado_cp(cp_id, 'ACTIVADO')
                            elif en_estado_interactivo:
                                # Preservar estado interactivo, solo actualizar telemetría
                                print(f"[KAFKA CONSUMER] Preservando estado interactivo {estado_actual} para {cp_id} (telemetría reporta {est})")
                    except Exception:
                        pass

                    # Reenviar actualización periódica al Driver asociado (si existe)
                    try:
                        with CP_SESION_DRIVER_ID_LOCK:
                            driver_id = CP_SESION_DRIVER_ID.get(cp_id)
                        if driver_id:
                            # Calcular importe aproximado en tiempo real
                            energia = (
                                telemetria.get('energia_total')
                                if 'energia_total' in telemetria
                                else telemetria.get('kwh', telemetria.get('kw_entregados', 0.0))
                            )
                            try:
                                energia_val = float(energia)
                            except Exception:
                                energia_val = 0.0
                            with CP_PRECIO_KWH_LOCK:
                                precio = CP_PRECIO_KWH.get(cp_id, 0.0)
                            try:
                                precio_val = float(precio)
                            except Exception:
                                precio_val = 0.0
                            importe = round(energia_val * precio_val, 2)
                            
                            # Usar estado autoritativo de Central (prioridad sobre telemetría recibida)
                            with CP_ESTADO_LOCK:
                                estado_autoritativo = CP_ESTADO.get(cp_id, 'ACTIVADO')
                            
                            estados_interactivos = {
                                'PENDIENTE_CONFIRMACION_CENTRAL',
                                'ESPERANDO_OPERADOR_ENGINE',
                                'LISTO_PARA_INICIAR',
                                'ESPERANDO_CONFIRMACION_FIN'
                            }
                            
                            # Determinar estado a enviar al driver
                            estado_tel = (telemetria.get('estado') or telemetria.get('estado_carga') or '').upper()
                            potencia_act = telemetria.get('potencia_actual', 0.0)

                            # PRIORIDAD 1: Respetar estados interactivos (no sobrescribir por energía residual)
                            if estado_autoritativo.upper() in estados_interactivos:
                                estado_para_driver = estado_autoritativo
                            # PRIORIDAD 2: Si hay POTENCIA ACTIVA (carga en progreso), es SUMINISTRANDO
                            elif isinstance(potencia_act, (int, float)) and float(potencia_act) > 0.0:
                                estado_para_driver = 'SUMINISTRANDO'
                            # PRIORIDAD 3: Si telemetría reporta SUMINISTRANDO/CARGANDO activamente
                            elif estado_tel in ['SUMINISTRANDO', 'CARGANDO']:
                                estado_para_driver = 'SUMINISTRANDO'
                            # PRIORIDAD 4: Usar estado autoritativo o telemetría
                            else:
                                estado_para_driver = telemetria.get('estado') or telemetria.get('estado_carga') or estado_autoritativo
                            
                            notificar_driver(driver_id, 'TELEMETRIA', {
                                'cp_id': cp_id,
                                'energia_kwh': energia_val,
                                'importe_eur': importe,
                                'estado': estado_para_driver,
                                'potencia_kw': telemetria.get('potencia_actual'),
                                'timestamp': telemetria.get('timestamp'),
                            })
                    except Exception:
                        pass

            # Confirmar offsets tras procesar el batch para retomar desde el último confirmado
            try:
                consumer.commit()
            except Exception:
                pass
            
    except Exception as e:
        print(f"[KAFKA CONSUMER] Error crítico de consumo de Kafka: {e}")
    finally:
        if consumer:
            consumer.close()
            print("[KAFKA CONSUMER] Consumidor de telemetría cerrado.")

# =================================================================
#                    CONSUMIDOR DE DRIVER_REQUESTS
# =================================================================
            
def consumir_comandos_control_kafka(broker_list: str):
    """
    Se conecta a Kafka y consume mensajes del tópico de comandos de control (desde web dashboard).
    """
    print(f"[KAFKA CONSUMER] Iniciando consumidor para comandos de control: {CENTRAL_COMMANDS_TOPIC}")
    consumer = None
    try:
        consumer = KafkaConsumer(
            CENTRAL_COMMANDS_TOPIC,
            bootstrap_servers=[broker_list],
            security_protocol='PLAINTEXT',
            api_version=(2, 5, 0),
            auto_offset_reset='latest',
            group_id='central-control-group',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        
        print(f"[KAFKA CONSUMER] Suscrito a '{CENTRAL_COMMANDS_TOPIC}'. Esperando comandos de control...")
        
        while True:
            with SHUTDOWN_LOCK:
                if SHUTDOWN_REQUESTED:
                    print("[KAFKA CONSUMER] Apagado solicitado, cerrando consumidor de comandos de control...")
                    break
            
            records = consumer.poll(timeout_ms=1000)
            if not records:
                continue
            
            for _tp, batch in records.items():
                for message in batch:
                    comando = message.value
                    cp_id = comando.get('cp_id')
                    command = comando.get('command', '').upper()
                    source = comando.get('source', 'unknown')
                    
                    if not cp_id:
                        registrar_evento(f"[WARN] Comando sin cp_id: {comando}", "warn")
                        continue
                    
                    registrar_evento(f"[CONTROL WEB] Comando {command} para {cp_id} desde {source}")
                    print(f"[KAFKA CONSUMER] Comando recibido: {command} para {cp_id}")
                    
                    # Manejar comando especial PREPARE_SUPPLY
                    if command == 'PREPARE_SUPPLY':
                        try:
                            # Obtener datos de sesión y enviar AUTH_REQ
                            with CP_SESION_DRIVER_ID_LOCK:
                                driver_id = CP_SESION_DRIVER_ID.get(cp_id)
                            with CP_SESION_OBJETIVO_KWH_LOCK:
                                kw_objetivo = CP_SESION_OBJETIVO_KWH.get(cp_id)
                            
                            if not driver_id or not kw_objetivo:
                                print(f"[CENTRAL] No hay sesión activa para {cp_id}")
                                registrar_evento(f"[ERROR] No hay sesión activa para {cp_id}", "error")
                                continue
                            
                            # Enviar AUTH_REQ al CP
                            with CONEXIONES_ACTIVAS_LOCK:
                                cp_socket = CONEXIONES_ACTIVAS.get(cp_id)
                            
                            if not cp_socket:
                                print(f"[CENTRAL] CP {cp_id} no está conectado")
                                registrar_evento(f"[ERROR] CP {cp_id} no está conectado", "error")
                                continue
                            
                            try:
                                trama_auth = construir_trama('AUTH_REQ', [driver_id, str(kw_objetivo)], cp_id=cp_id, cifrar=True)
                                cp_socket.sendall(trama_auth)
                                print(f"\n[CENTRAL] ╔═══════════════════════════════════════════╗")
                                print(f"[CENTRAL] ║  📤 ENVIANDO COMANDO AL CP                ║")
                                print(f"[CENTRAL] ╚═══════════════════════════════════════════╝")
                                print(f"[CENTRAL]    Comando: AUTH_REQ")
                                print(f"[CENTRAL]    Destino: {cp_id}")
                                print(f"[CENTRAL]    Driver: {driver_id}")
                                print(f"[CENTRAL]    kW Solicitados: {kw_objetivo}")
                                print(f"[CENTRAL] ═══════════════════════════════════════════\n")
                                registrar_evento(f"📤 AUTH_REQ enviado a {cp_id} (Driver: {driver_id}, {kw_objetivo} kWh)", "ok")
                                
                                # Cambiar estado (sin db_connection, se obtendrá si es necesario)
                                try:
                                    cambiar_estado_cp(cp_id, 'ESPERANDO_OPERADOR_ENGINE', None)
                                except Exception as e_estado:
                                    print(f"[CENTRAL] Error cambiando estado de {cp_id}: {e_estado}")
                                    # Continuar aunque falle el cambio de estado en BD
                                
                                # Publicar telemetría actualizada
                                with TELEMETRIA_ACTUAL_LOCK:
                                    telemetria_actual = TELEMETRIA_ACTUAL.get(cp_id, {})
                                telemetria_actualizada = {
                                    **telemetria_actual,
                                    'cp_id': cp_id,
                                    'estado_carga': 'ESPERANDO_OPERADOR_ENGINE',
                                    'estado': 'ESPERANDO_OPERADOR_ENGINE',
                                    'timestamp': time.time(),
                                    'tiene_sesion_activa': True,
                                    'driver_id_sesion': driver_id
                                }
                                with TELEMETRIA_ACTUAL_LOCK:
                                    TELEMETRIA_ACTUAL[cp_id] = telemetria_actualizada
                                if KAFKA_PRODUCER:
                                    KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_actualizada)
                                    KAFKA_PRODUCER.flush(timeout=1)
                            except Exception as e:
                                print(f"[CENTRAL] Error enviando AUTH_REQ a {cp_id}: {e}")
                                registrar_evento(f"[ERROR] Error enviando AUTH_REQ a {cp_id}: {e}", "error")
                                import traceback
                                traceback.print_exc()
                        except Exception as e:
                            print(f"[CENTRAL] Error crítico procesando PREPARE_SUPPLY para {cp_id}: {e}")
                            registrar_evento(f"[ERROR] Error crítico procesando PREPARE_SUPPLY para {cp_id}: {e}", "error")
                            import traceback
                            traceback.print_exc()
                            # Continuar procesando otros comandos
                            continue
                    
                    elif command == 'DISCONNECT_MONITOR':
                        # Simular caída del Monitor (cerrar socket TCP)
                        # El Engine seguirá suministrando pero la Central no recibirá telemetría
                        try:
                            print(f"[CENTRAL] ⚠️ Desconectando Monitor de {cp_id} (simulación de caída)")
                            registrar_evento(f"🔌 Desconectando Monitor de {cp_id}", "warn")
                            
                            # Cerrar socket TCP del monitor
                            with CONEXIONES_ACTIVAS_LOCK:
                                if cp_id in CONEXIONES_ACTIVAS:
                                    try:
                                        socket_monitor = CONEXIONES_ACTIVAS[cp_id]
                                        socket_monitor.close()
                                        del CONEXIONES_ACTIVAS[cp_id]
                                        print(f"[CENTRAL] Socket de {cp_id} cerrado. Conexiones activas: {len(CONEXIONES_ACTIVAS)}")
                                    except Exception as e_socket:
                                        print(f"[CENTRAL] Error cerrando socket de {cp_id}: {e_socket}")
                                else:
                                    print(f"[CENTRAL] {cp_id} no tiene socket activo")
                            
                            # Verificar si hay un suministro activo antes de desconectar
                            with TELEMETRIA_ACTUAL_LOCK:
                                telemetria_actual = TELEMETRIA_ACTUAL.get(cp_id, {})
                            estado_telemetria = telemetria_actual.get('estado', '').upper()
                            tiene_sesion_activa = telemetria_actual.get('tiene_sesion_activa', False)
                            
                            # Si hay suministro activo, finalizarlo y enviar ticket al driver
                            if tiene_sesion_activa or estado_telemetria in ('SUMINISTRANDO', 'CARGANDO'):
                                print(f"[CENTRAL] ⚠️ Monitor de {cp_id} desconectado durante suministro activo. Finalizando suministro...")
                                
                                # Obtener información del driver y energía suministrada
                                with CP_SESION_DRIVER_ID_LOCK:
                                    driver_id = CP_SESION_DRIVER_ID.get(cp_id)
                                
                                if driver_id and driver_id != 'UNKNOWN':
                                    # Calcular energía entregada desde telemetría
                                    energia = (
                                        telemetria_actual.get('energia_total')
                                        if 'energia_total' in telemetria_actual
                                        else telemetria_actual.get('kw_entregados', 0.0)
                                    )
                                    try:
                                        energia_val = float(energia)
                                    except Exception:
                                        energia_val = 0.0
                                    
                                    # Calcular duración
                                    tiempo_carga_s = telemetria_actual.get('tiempo_carga_s', 0)
                                    try:
                                        duracion_seg = int(tiempo_carga_s)
                                    except Exception:
                                        duracion_seg = 0
                                    
                                    # Calcular importe usando precio del CP
                                    with CP_PRECIO_KWH_LOCK:
                                        precio_kwh = CP_PRECIO_KWH.get(cp_id, 0.48)
                                    try:
                                        precio_val = float(precio_kwh)
                                    except Exception:
                                        precio_val = 0.48
                                    
                                    importe = round(energia_val * precio_val, 2)
                                    
                                    # Generar tx_id
                                    tx_id = f"TX-{cp_id}-{int(time.time())}"
                                    
                                    # Crear ticket
                                    detalle_ticket = {
                                        'cp_id': cp_id,
                                        'energia_kwh': energia_val,
                                        'importe_eur': importe,
                                        'duracion_seg': duracion_seg,
                                        'motivo': 'Monitor desconectado - suministro finalizado',
                                        'tx_id': tx_id
                                    }
                                    
                                    # Enviar ticket al driver
                                    notificar_driver(driver_id, 'TICKET_FINAL', detalle_ticket)
                                    registrar_evento(f"✅ Ticket enviado a {driver_id} por desconexión de Monitor en {cp_id}: {energia_val} kWh, {importe} €", "ok")
                                    print(f"[CENTRAL] ✅ Ticket enviado a {driver_id} por desconexión de Monitor. Energía: {energia_val} kWh, Importe: {importe} €")
                                    
                                    # Limpiar sesión
                                    with CP_SESION_DRIVER_ID_LOCK:
                                        if cp_id in CP_SESION_DRIVER_ID:
                                            del CP_SESION_DRIVER_ID[cp_id]
                                    with CP_SESION_OBJETIVO_KWH_LOCK:
                                        if cp_id in CP_SESION_OBJETIVO_KWH:
                                            del CP_SESION_OBJETIVO_KWH[cp_id]
                                    
                                    # Resetear telemetría de sesión
                                    telemetria_actual['tiene_sesion_activa'] = False
                                    telemetria_actual['driver_id_sesion'] = None
                                    telemetria_actual['kw_entregados'] = 0.0
                                    telemetria_actual['energia_total'] = 0.0
                                    telemetria_actual['tiempo_carga_s'] = 0
                                    
                                    registrar_evento(f"🛑 Suministro finalizado en {cp_id} debido a desconexión del Monitor", "warn")
                            
                            # Marcar CP como DESCONECTADO
                            cambiar_estado_cp(cp_id, 'DESCONECTADO', None)
                            
                            # Publicar telemetría actualizada para que el dashboard web refleje el cambio
                            telemetria_actualizada = {
                                **telemetria_actual,
                                'cp_id': cp_id,
                                'estado': 'DESCONECTADO',
                                'estado_carga': 'DESCONECTADO',
                                'timestamp': time.time()
                            }
                            with TELEMETRIA_ACTUAL_LOCK:
                                TELEMETRIA_ACTUAL[cp_id] = telemetria_actualizada
                            if KAFKA_PRODUCER:
                                KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_actualizada)
                                KAFKA_PRODUCER.flush(timeout=1)
                                print(f"[CENTRAL] ✓ Telemetría DESCONECTADO publicada para {cp_id}")
                            
                            # BLOQUEAR reconexión automática del Monitor
                            with CP_MONITOR_BLOQUEADO_LOCK:
                                CP_MONITOR_BLOQUEADO.add(cp_id)
                                print(f"[CENTRAL] {cp_id} BLOQUEADO para reconexión automática")
                            
                            registrar_evento(f"✓ Monitor de {cp_id} desconectado. CP no admitirá nuevos suministros.", "info")
                            print(f"[CENTRAL] Monitor de {cp_id} desconectado. CP marcado como DESCONECTADO y no admitirá nuevos suministros.")
                            
                        except Exception as e:
                            print(f"[CENTRAL] Error desconectando monitor de {cp_id}: {e}")
                            registrar_evento(f"[ERROR] Error desconectando monitor de {cp_id}: {e}", "error")
                            import traceback
                            traceback.print_exc()
                    
                    elif command == 'RECONNECT_MONITOR':
                        # Marcar Monitor como listo para reconexión
                        # El Monitor debe reiniciarse manualmente para volver a conectarse
                        try:
                            print(f"[CENTRAL] ✅ Marcando Monitor de {cp_id} como listo para reconexión")
                            registrar_evento(f"✅ Monitor de {cp_id} marcado para reconexión", "info")
                            
                            # Determinar estado correcto según sesión activa
                            with CP_SESION_DRIVER_ID_LOCK:
                                tiene_sesion = cp_id in CP_SESION_DRIVER_ID and CP_SESION_DRIVER_ID[cp_id] is not None
                            
                            if tiene_sesion:
                                # Hay sesión activa - mantener estado pendiente o activado
                                # (El Monitor al reconectarse continuará con la sesión)
                                nuevo_estado = 'ACTIVADO'
                                print(f"[CENTRAL] {cp_id} tiene sesión activa. Estado: {nuevo_estado}")
                            else:
                                # Sin sesión - simplemente ACTIVADO
                                nuevo_estado = 'ACTIVADO'
                                print(f"[CENTRAL] {cp_id} sin sesión activa. Estado: {nuevo_estado}")
                            
                            cambiar_estado_cp(cp_id, nuevo_estado, None)
                            
                            # Publicar telemetría actualizada para que el dashboard web refleje el cambio
                            with TELEMETRIA_ACTUAL_LOCK:
                                telemetria_actual = TELEMETRIA_ACTUAL.get(cp_id, {})
                            telemetria_actualizada = {
                                **telemetria_actual,
                                'cp_id': cp_id,
                                'estado': nuevo_estado,
                                'estado_carga': nuevo_estado,
                                'timestamp': time.time()
                            }
                            with TELEMETRIA_ACTUAL_LOCK:
                                TELEMETRIA_ACTUAL[cp_id] = telemetria_actualizada
                            if KAFKA_PRODUCER:
                                KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_actualizada)
                                KAFKA_PRODUCER.flush(timeout=1)
                                print(f"[CENTRAL] ✓ Telemetría {nuevo_estado} publicada para {cp_id}")
                            
                            # DESBLOQUEAR reconexión automática del Monitor
                            with CP_MONITOR_BLOQUEADO_LOCK:
                                CP_MONITOR_BLOQUEADO.discard(cp_id)
                                print(f"[CENTRAL] {cp_id} DESBLOQUEADO para reconexión")
                            
                            registrar_evento(f"✓ {cp_id} listo para reconexión. Reinicie el proceso Monitor.", "info")
                            print(f"[CENTRAL] {cp_id} marcado como {nuevo_estado}. El Monitor debe reiniciarse para volver a conectarse.")
                            
                        except Exception as e:
                            print(f"[CENTRAL] Error marcando monitor de {cp_id} para reconexión: {e}")
                            registrar_evento(f"[ERROR] Error marcando monitor de {cp_id} para reconexión: {e}", "error")
                            import traceback
                            traceback.print_exc()
                    
                    elif command in ['START', 'STOP']:
                        # Comandos normales START/STOP
                        _enviar_comando_cp(cp_id, command)
                    else:
                        registrar_evento(f"[WARN] Comando desconocido: {command}", "warn")
            
            try:
                consumer.commit()
            except Exception:
                pass
                
    except Exception as e:
        print(f"[KAFKA CONSUMER] Error en consumidor de comandos de control: {e}")
    finally:
        if consumer:
            consumer.close()
            print("[KAFKA CONSUMER] Consumidor de comandos de control cerrado.")


def consumir_solicitudes_driver_kafka(broker_list: str, db_connection):
    """
    Se conecta a Kafka y consume mensajes del tópico de solicitudes de drivers.
    """
    print(f"[KAFKA CONSUMER] EV_Central iniciando consumidor para el topic: {DRIVER_REQUESTS_TOPIC}")
    consumer = None
    try:
        consumer = KafkaConsumer(
            DRIVER_REQUESTS_TOPIC,
            bootstrap_servers=[broker_list],
            security_protocol='PLAINTEXT',
            api_version=(2, 5, 0),
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
                    print(f"\n[KAFKA] ╔═══════════════════════════════════════════╗")
                    print(f"[KAFKA] ║  🚗 SOLICITUD DE DRIVER RECIBIDA         ║")
                    print(f"[KAFKA] ╚═══════════════════════════════════════════╝")
                    print(f"[KAFKA]    Driver ID: {solicitud.get('id_driver')}")
                    print(f"[KAFKA]    CP ID:     {solicitud.get('id_charging_point')}")
                    print(f"[KAFKA]    Matrícula: {solicitud.get('matricula')}")
                    print(f"[KAFKA]    kW Deseados: {solicitud.get('kw_deseados')} kW")
                    print(f"[KAFKA] ═══════════════════════════════════════════\n")
                    registrar_evento(f"🚗 Solicitud de Driver {solicitud.get('id_driver')} para CP {solicitud.get('id_charging_point')}: {solicitud.get('kw_deseados')} kWh")
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

                        # Paso 2: Validar contra BD (intentar reconectar si es necesario)
                        if not (db_connection and _verificar_conexion(db_connection)):
                            print("[CENTRAL] BD no conectada, intentando reconectar...")
                            db_connection = _asegurar_conexion_bd(db_connection)
                        
                        if not (db_connection and _verificar_conexion(db_connection)):
                            print("[CENTRAL] BD no disponible tras intento de reconexión; denegando solicitud.")
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

                        estado_inferior = estado_cp.strip().lower() if estado_cp else ''
                        
                        # Verificar si el CP ya tiene una sesión activa
                        with CP_SESION_DRIVER_ID_LOCK:
                            tiene_sesion = cp_id in CP_SESION_DRIVER_ID and CP_SESION_DRIVER_ID[cp_id] is not None
                        
                        if tiene_sesion:
                            # CP ocupado - añadir a cola de espera
                            print(f"[CENTRAL] CP {cp_id} ocupado. Añadiendo {id_driver} a cola de espera...")
                            
                            with CP_COLA_ESPERA_LOCK:
                                if cp_id not in CP_COLA_ESPERA:
                                    from queue import Queue
                                    CP_COLA_ESPERA[cp_id] = Queue()
                                CP_COLA_ESPERA[cp_id].put((id_driver, kw_deseados, time.time()))
                            
                            # Obtener posición en la cola
                            with CP_COLA_ESPERA_LOCK:
                                posicion = CP_COLA_ESPERA[cp_id].qsize()
                            
                            notificar_driver(id_driver, 'EN_COLA', {
                                'mensaje': f'CP {cp_id} ocupado. Posición en cola: {posicion}',
                                'posicion': posicion,
                                'cp_id': cp_id
                            })
                            
                            registrar_evento(f"Driver {id_driver} en cola para {cp_id} (posición {posicion})", "info")
                            continue
                        
                        # Estados válidos para aceptar solicitudes (case-insensitive)
                        estados_validos = {
                            'activado', 'reposo', 'ready', 'idle',
                            'pendiente confirmacion central',
                            'pendiente_confirmacion_central',
                            'esperando operador engine',
                            'esperando_operador_engine',
                            'listo para iniciar',
                            'listo_para_iniciar'
                        }
                        
                        # Estados que indican ocupación (añadir a cola)
                        estados_ocupados = {
                            'suministrando', 'cargando', 'charging', 'en_carga'
                        }
                        
                        # Estados que indican no disponible (denegar)
                        estados_no_disponibles = {
                            'parado', 'averiado', 'avería', 'desconectado', 'desconectada',
                            'fuera_de_servicio', 'fuera de servicio', 'FUERA_DE_SERVICIO'
                        }
                        
                        if estado_inferior in estados_validos:
                            # Estado válido, continuar con el proceso
                            pass
                        elif estado_inferior in estados_ocupados:
                            # CP ocupado - añadir a cola
                            print(f"[CENTRAL] CP {cp_id} ocupado ({estado_cp}). Añadiendo {id_driver} a cola de espera...")
                            
                            with CP_COLA_ESPERA_LOCK:
                                if cp_id not in CP_COLA_ESPERA:
                                    from queue import Queue
                                    CP_COLA_ESPERA[cp_id] = Queue()
                                CP_COLA_ESPERA[cp_id].put((id_driver, kw_deseados, time.time()))
                            
                            with CP_COLA_ESPERA_LOCK:
                                posicion = CP_COLA_ESPERA[cp_id].qsize()
                            
                            notificar_driver(id_driver, 'EN_COLA', {
                                'mensaje': f'CP {cp_id} ocupado ({estado_cp}). Posición en cola: {posicion}',
                                'posicion': posicion,
                                'cp_id': cp_id
                            })
                            registrar_evento(f"Driver {id_driver} en cola para {cp_id} (posición {posicion})", "info")
                            continue
                        elif estado_inferior in estados_no_disponibles:
                            mensaje_error = f'CP {cp_id} no disponible. CP fuera de servicio'
                            print(f"[CENTRAL] ❌ {mensaje_error}")
                            registrar_evento(f"❌ {mensaje_error}", "error")
                            notificar_driver(id_driver, 'DENEGADA', {
                                'motivo': mensaje_error
                            })
                            continue
                        else:
                            # Estado desconocido - intentar permitir si el CP está conectado
                            print(f"[CENTRAL] Estado desconocido '{estado_cp}' para {cp_id}. Verificando conexión...")
                            with CONEXIONES_ACTIVAS_LOCK:
                                if cp_id in CONEXIONES_ACTIVAS:
                                    # CP conectado pero estado desconocido - permitir (puede ser un estado nuevo)
                                    print(f"[CENTRAL] CP {cp_id} conectado. Permitiendo solicitud a pesar de estado desconocido.")
                                    pass
                                else:
                                    notificar_driver(id_driver, 'DENEGADA', {
                                        'motivo': f'Estado de CP desconocido y no conectado: {estado_cp}'
                                    })
                                    continue

                        # Paso 3: Verificar conexión TCP con el Monitor (persistente)
                        with CONEXIONES_ACTIVAS_LOCK:
                            cp_socket = CONEXIONES_ACTIVAS.get(cp_id)

                        if not cp_socket:
                            mensaje_error = f'Imposible conectar con CP {cp_id}. Mensajes no comprensibles'
                            print(f"[CENTRAL] ❌ {mensaje_error}")
                            registrar_evento(f"❌ {mensaje_error}", "error")
                            notificar_driver(id_driver, 'DENEGADA', {
                                'motivo': mensaje_error
                            })
                            continue

                        # Paso 4: Registrar objetivo de sesión PERO NO ENVIAR AUTH_REQ TODAVÍA
                        # Esperar a que el operador de Central de click en "Iniciar Suministro"
                        try:
                            with CP_SESION_OBJETIVO_KWH_LOCK:
                                CP_SESION_OBJETIVO_KWH[cp_id] = float(kw_deseados)
                        except Exception:
                            with CP_SESION_OBJETIVO_KWH_LOCK:
                                CP_SESION_OBJETIVO_KWH[cp_id] = kw_deseados
                        try:
                            with CP_SESION_DRIVER_ID_LOCK:
                                CP_SESION_DRIVER_ID[cp_id] = id_driver
                        except Exception:
                            pass

                        # NUEVO: Cambiar a estado PENDIENTE_CONFIRMACION_CENTRAL
                        # El operador de Central debe confirmar desde la web
                        try:
                            cambiar_estado_cp(cp_id, 'PENDIENTE_CONFIRMACION_CENTRAL', db_connection)
                        except Exception:
                            pass
                        
                        # Publicar telemetría para que aparezca botón en dashboard de Central
                        # RESETEAR contadores de sesión anterior (si existían)
                        try:
                            with TELEMETRIA_ACTUAL_LOCK:
                                telemetria_actual = TELEMETRIA_ACTUAL.get(cp_id, {})
                            # Resetear contadores para nueva sesión (evitar energía residual)
                            telemetria_actualizada = {
                                **telemetria_actual,
                                'cp_id': cp_id,
                                'estado_carga': 'PENDIENTE_CONFIRMACION_CENTRAL',
                                'estado': 'PENDIENTE_CONFIRMACION_CENTRAL',
                                'timestamp': time.time(),
                                'tiene_sesion_activa': True,
                                'driver_id_sesion': id_driver,
                                'objetivo_kwh': kw_deseados,
                                # Resetear contadores para nueva sesión
                                'kw_entregados': 0.0,
                                'energia_total': 0.0,
                                'potencia_actual': 0.0,
                                'tiempo_carga_s': 0
                            }
                            with TELEMETRIA_ACTUAL_LOCK:
                                TELEMETRIA_ACTUAL[cp_id] = telemetria_actualizada
                            if KAFKA_PRODUCER:
                                KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_actualizada)
                                KAFKA_PRODUCER.flush(timeout=1)
                                print(f"[CENTRAL] Telemetría publicada para {cp_id}: PENDIENTE_CONFIRMACION_CENTRAL (contadores reseteados)")
                        except Exception as e:
                            print(f"[CENTRAL] No se pudo publicar telemetría: {e}")
                        
                        # Notificar al driver que su solicitud está en espera de confirmación
                        notificar_driver(id_driver, 'EN_ESPERA_CONFIRMACION', {
                            'mensaje': f'Solicitud validada. Esperando confirmación del operador de Central.',
                            'cp_id': cp_id
                        })
                        
                        print(f"[CENTRAL] ✓ Solicitud de {id_driver} para {cp_id} registrada.")
                        print(f"[CENTRAL] ⏳ Esperando que operador de Central confirme en web dashboard...")
                        registrar_evento(f"[FLUJO] Solicitud {id_driver} → {cp_id} ({kw_deseados} kWh). Esperando confirmación de operador Central.", "info")

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

def construir_trama(cod_op: str, campos: list, cp_id: str = None, cifrar: bool = True) -> bytes:
    """
    Construye la trama completa para enviar una respuesta (ej. AUTH).
    Si se proporciona cp_id y hay clave, cifra el mensaje.
    """
    # 1. Crear el contenido DATA (Cod_Op#campo1#campo2...)
    DATA = f"{cod_op}#{DELIMITER.join(map(str, campos))}"
    
    # 2. Calcular el LRC de la DATA
    DATA_bytes = DATA.encode('utf-8')
    
    # 3. Cifrar si hay clave disponible
    if cifrar and cp_id:
        try:
            clave = obtener_clave_cifrado_cp(cp_id, None)
            if clave:
                fernet = Fernet(clave)
                DATA_bytes = fernet.encrypt(DATA_bytes)
                # Prefijo para indicar que está cifrado
                DATA_bytes = b'ENC' + DATA_bytes
        except Exception as e:
            print(f"[CENTRAL] ⚠️ Error cifrando mensaje para {cp_id}: {e}")
            # Continuar sin cifrar si hay error
    
    LRC_byte = calcular_lrc(DATA_bytes)
    
    # 4. Ensamblar la trama: STX + DATA (en bytes) + ETX + LRC
    trama = STX + DATA_bytes + ETX + LRC_byte
    return trama

def descomponer_trama(trama_bytes: bytes, cp_id: str = None) -> tuple:
    """
    Descompone, valida y parsea la trama recibida del CP.
    Si está cifrada, la descifra primero.
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
        print("[CENTRAL] Error: Formato de trama incorrecto (STX/ETX faltantes).")
        return None, None
    
    # 2. Verificar LRC sobre los datos ORIGINALES (antes de descifrar)
    # El LRC fue calculado sobre los datos cifrados, así que debemos verificarlo antes de descifrar
    lrc_calculado = calcular_lrc(data_bytes)
    if lrc_recibido != lrc_calculado:
        print(f"[CENTRAL] Error LRC. Recibido: {lrc_recibido.hex()}, Calculado: {lrc_calculado.hex()}. Trama descartada.")
        return None, None
    
    # 3. Verificar si está cifrado (prefijo 'ENC') y descifrar
    if data_bytes.startswith(b'ENC'):
        if not cp_id:
            print("[CENTRAL] Error: Mensaje cifrado recibido pero no hay cp_id para descifrar")
            return None, None
        
        # Obtener clave de cifrado
        clave = obtener_clave_cifrado_cp(cp_id, None)
        if not clave:
            mensaje_error = f"Imposible conectar con CP {cp_id}. Mensajes no comprensibles"
            print(f"[CENTRAL] ❌ {mensaje_error}")
            registrar_evento(f"❌ {mensaje_error}", "error")
            return None, None
        
        try:
            # Descifrar
            fernet = Fernet(clave)
            data_cifrado = data_bytes[3:]  # Quitar prefijo 'ENC'
            data_bytes = fernet.decrypt(data_cifrado)
        except Exception as e:
            mensaje_error = f"Imposible conectar con CP {cp_id}. Mensajes no comprensibles"
            print(f"[CENTRAL] ❌ {mensaje_error}")
            registrar_evento(f"❌ {mensaje_error}", "error")
            return None, None
        
    # 4. Decodificar y parsear DATA
    try:
        DATA = data_bytes.decode('utf-8')
        partes = DATA.split(DELIMITER)
        
        cod_op = partes[0]
        campos = partes[1:]
        
        return cod_op, campos
    except UnicodeDecodeError:
        mensaje_error = f"Imposible conectar con CP {cp_id if cp_id else 'desconocido'}. Mensajes no comprensibles"
        print(f"[CENTRAL] ❌ {mensaje_error}")
        if cp_id:
            registrar_evento(f"❌ {mensaje_error}", "error")
        return None, None

# =================================================================
#                      FUNCIONES DE BASE DE DATOS
# =================================================================

def _verificar_conexion(connection):
    """Verifica si una conexión MySQL está activa (compatible con PyMySQL y mysql.connector)."""
    if connection is None:
        return False
    try:
        # Detectar tipo de conexión por el método disponible
        # PyMySQL tiene ping(), mysql.connector tiene is_connected()
        if hasattr(connection, 'ping'):
            # PyMySQL: intentar hacer un ping
            connection.ping(reconnect=False)
            return True
        elif hasattr(connection, 'is_connected'):
            # mysql.connector: usar is_connected()
            return connection.is_connected()
        else:
            # Fallback: intentar hacer una operación simple
            try:
                connection.ping(reconnect=False)
                return True
            except:
                return False
    except:
        return False

def conectar_bd(db_config: str):
    """Establece conexión con la base de datos MariaDB/MySQL."""
    try:
        # Parsear la configuración de BD (formato: host:port:user:password:database)
        if not db_config:
            raise ValueError("Configuración de BD no proporcionada")
        
        parts = db_config.split(':')
        if len(parts) != 5:
            raise ValueError("Formato de BD incorrecto. Use: host:port:user:password:database")
        
        host, port, user, password, database = parts
        
        # Intentar conexión con PyMySQL (más compatible con MySQL 8)
        if PYMySQL_AVAILABLE:
            try:
                connection = pymysql.connect(
                    host=host,
                    port=int(port),
                    user=user,
                    password=password,
                    database=database,
                    charset='utf8mb4',
                    cursorclass=pymysql.cursors.DictCursor,
                    autocommit=True,
                    connect_timeout=10
                )
                print(f"[CENTRAL] ✓ Conectado a MariaDB en {host}:{port} (usando PyMySQL)")
                return connection
            except Exception as e:
                # Si falla, intentar con mysql.connector como fallback
                print(f"[CENTRAL] ⚠️ PyMySQL falló: {e}, intentando mysql.connector...")
        
        # Fallback a mysql.connector
        if MYSQL_CONNECTOR_AVAILABLE:
            try:
                connection_params = {
                    'host': host,
                    'port': int(port),
                    'user': user,
                    'password': password,
                    'database': database,
                    'autocommit': True,
                    'charset': 'utf8mb4',
                    'collation': 'utf8mb4_general_ci',
                    'ssl_disabled': True,
                    'allow_local_infile': True,
                    'use_unicode': True,
                    'connection_timeout': 10
                }
                connection = mysql.connector.connect(**connection_params)
                if _verificar_conexion(connection):
                    print(f"[CENTRAL] ✓ Conectado a MariaDB en {host}:{port} (usando mysql.connector)")
                    return connection
            except Exception as e:
                print(f"[CENTRAL] ❌ Error conectando con mysql.connector: {e}")
                raise
        else:
            raise ImportError("Ni PyMySQL ni mysql.connector están disponibles. Instala uno de ellos: pip install pymysql o pip install mysql-connector-python")
            
    except Exception as e:
        print(f"[CENTRAL] Error conectando a MySQL: {e}")
        raise

def registrar_cp_en_bd(connection, 
                       cp_id: str, ubicacion: str, precio_kwh: float) -> bool:
    """Registra o actualiza un CP en la base de datos y lo marca como Activado."""
    try:
        cursor = connection.cursor()
        
        # Verificar si el CP ya existe
        cursor.execute("SELECT id, estado FROM charging_points WHERE cp_id = %s", (cp_id,))
        result = cursor.fetchone()
        
        if result:
            # CP existe, actualizar estado y fecha de conexión
            # Compatible con PyMySQL (dict) y mysql.connector (tuple)
            if isinstance(result, dict):
                cp_db_id = result.get('id')
                estado_actual = result.get('estado')
            else:
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

def _asegurar_conexion_bd(connection) -> any:
    """Verifica y, si es necesario, reestablece la conexión a BD usando DB_CONFIG_STR."""
    try:
        if connection and _verificar_conexion(connection):
            return connection
    except Exception:
        pass
    try:
        cfg = globals().get('DB_CONFIG_STR')
        if not cfg:
            return connection
        nuevo = conectar_bd(cfg)
        # Actualizar referencia global usada por consumidores
        globals()['_DB_CONN_FOR_CONSUMER'] = nuevo
        return nuevo
    except Exception as _:
        return connection


def actualizar_estado_cp(connection, 
                         cp_id: str, nuevo_estado: str) -> bool:
    """Actualiza el estado de un CP en la base de datos."""
    if connection is None:
        # Intentar obtener conexión si no se proporciona
        try:
            connection = _asegurar_conexion_bd(connection)
        except Exception:
            pass
    
    if connection is None:
        # Sin conexión disponible, no es crítico, solo log
        return False
    
    try:
        # Verificar conexión antes de usar
        if not _verificar_conexion(connection):
            connection = _asegurar_conexion_bd(connection)
            if connection is None:
                return False
        
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
            # CP no encontrado - intentar registrarlo primero (con valores por defecto)
            print(f"[CENTRAL] ⚠️ CP {cp_id} no encontrado en BD. Intentando registrar...")
            cursor.close()
            # Intentar registrar con valores por defecto
            try:
                ubicacion_default = 'Desconocida'
                precio_kwh_default = 0.48
                if registrar_cp_en_bd(connection, cp_id, ubicacion_default, precio_kwh_default):
                    # Ahora intentar actualizar el estado de nuevo
                    cursor = connection.cursor()
                    cursor.execute("""
                        UPDATE charging_points 
                        SET estado = %s, fecha_ultima_conexion = %s 
                        WHERE cp_id = %s
                    """, (nuevo_estado, datetime.now(), cp_id))
                    cursor.close()
                    print(f"[CENTRAL] ✓ CP {cp_id} registrado y estado actualizado a: {nuevo_estado}")
                    return True
                else:
                    print(f"[CENTRAL] ⚠️ No se pudo registrar CP {cp_id} en BD")
                    return False
            except Exception as e:
                print(f"[CENTRAL] ⚠️ Error intentando registrar CP {cp_id} en BD: {e}")
                return False
            
    except Error as e:
        try:
            # Intento de reconexión para errores típicos de desconexión
            if getattr(e, 'errno', None) in (2006, 2013) or 'Lost connection' in str(e):
                print(f"[CENTRAL] Aviso: {e}. Reintentando actualización tras reconexión...")
                connection = _asegurar_conexion_bd(connection)
                if connection is None:
                    return False
                try:
                    cursor = connection.cursor()
                    cursor.execute("""
                        UPDATE charging_points 
                        SET estado = %s, fecha_ultima_conexion = %s 
                        WHERE cp_id = %s
                    """, (nuevo_estado, datetime.now(), cp_id))
                    ok = cursor.rowcount > 0
                    connection.commit()
                    cursor.close()
                    if ok:
                        print(f"[CENTRAL] Estado de CP {cp_id} actualizado tras reconexión: {nuevo_estado}")
                    return ok
                except Exception as e2:
                    print(f"[CENTRAL] Error tras reintento de actualización de CP {cp_id}: {e2}")
                    return False
        except Exception:
            pass
        print(f"[CENTRAL] Error actualizando estado de CP {cp_id}: {e}")
        return False
    except Exception as e:
        print(f"[CENTRAL] Error inesperado actualizando estado de CP {cp_id}: {e}")
        import traceback
        traceback.print_exc()
        return False

def obtener_estado_cp(connection, cp_id: str):
    """Obtiene el estado actual del CP desde la BD. Devuelve str o None si no existe.
    Primero busca en charging_points, si no encuentra, verifica cp_registry como fallback."""
    try:
        cursor = connection.cursor()
        # Primero buscar en charging_points
        cursor.execute("SELECT estado FROM charging_points WHERE cp_id = %s", (cp_id,))
        result = cursor.fetchone()
        if result:
            cursor.close()
            # Compatible con PyMySQL (dict) y mysql.connector (tuple)
            if isinstance(result, dict):
                return result.get('estado')
            else:
                return result[0]
        
        # Si no está en charging_points, verificar si está registrado en cp_registry
        # (puede estar registrado en Registry pero no en charging_points si se conectó sin BD)
        try:
            cursor.execute("SELECT activo FROM cp_registry WHERE cp_id = %s", (cp_id,))
            registry_result = cursor.fetchone()
            if registry_result:
                # CP está registrado en Registry, devolver "Activado" como estado por defecto
                cursor.close()
                print(f"[CENTRAL] CP {cp_id} encontrado en cp_registry pero no en charging_points. Usando estado 'Activado'.")
                return "Activado"
        except Exception:
            # Si la tabla cp_registry no existe o hay error, ignorar
            pass
        
        cursor.close()
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
                    security_protocol='PLAINTEXT',
                    api_version=(2, 5, 0),
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
        
        # Logging detallado de notificaciones
        print(f"\n[KAFKA] ═══════════════════════════════════════════")
        print(f"[KAFKA] 📢 NOTIFICACIÓN A DRIVER")
        print(f"[KAFKA]    Driver: {id_driver}")
        print(f"[KAFKA]    Evento: {evento}")
        if detalle:
            print(f"[KAFKA]    Detalle: {detalle}")
        print(f"[KAFKA]    Topic: {topic}")
        print(f"[KAFKA] ═══════════════════════════════════════════\n")
        registrar_evento(f"📢 Notificación a Driver {id_driver}: {evento}", "info")
    except Exception as e:
        print(f"[CENTRAL] ❌ Error notificando al driver {id_driver}: {e}")
        registrar_evento(f"❌ Error notificando a Driver {id_driver}: {e}", "error")

# =================================================================
#                       LÓGICA DEL SERVIDOR CENTRAL
# =================================================================

def monitorizar_actividad_cps(db_connection):
    """Monitoriza la actividad de los CPs y publica heartbeats periódicos."""
    contador_heartbeat = 0
    while not SHUTDOWN_REQUESTED:
        ahora = time.time()
        try:
            # Verificar CPs sin actividad (telemetría)
            with TELEMETRIA_ACTUAL_LOCK:
                for cp_id, data in list(TELEMETRIA_ACTUAL.items()):
                    ultima = data.get("timestamp", 0)
                    tiempo_sin_telemetria = ahora - ultima
                    if tiempo_sin_telemetria > 15:
                        # Verificar si el socket TCP está activo
                        with CONEXIONES_ACTIVAS_LOCK:
                            tiene_socket_activo = cp_id in CONEXIONES_ACTIVAS
                        
                        if tiene_socket_activo:
                            # ADVERTENCIA: Socket activo pero SIN telemetría - problema en el Engine
                            if tiempo_sin_telemetria > 30:  # Solo advertir cada 30s para no saturar
                                registrar_evento(f"[⚠️] CP {cp_id} conectado por socket pero SIN telemetría hace {int(tiempo_sin_telemetria)}s - revisar Engine", "warn")
                                data['timestamp'] = time.time()  # Reset para no repetir advertencia constantemente
                            continue
                        
                        # No desconectar si está en avería activa
                        with CP_ALERTA_LOCK:
                            alerta = CP_ALERTA.get(cp_id, False)
                        if alerta:
                            continue
                        if CP_ESTADO.get(cp_id) != "DESCONECTADO":
                            registrar_evento(f"[⚠️] CP {cp_id} sin telemetría hace {int(tiempo_sin_telemetria)}s y socket cerrado → DESCONECTADO", "warn")
                            cambiar_estado_cp(cp_id, "DESCONECTADO", db_connection)
            
            # Publicar heartbeat cada 10 segundos (cada 2 ciclos de 5s)
            contador_heartbeat += 1
            if contador_heartbeat >= 2:
                contador_heartbeat = 0
                publicar_heartbeat_cps()
                
        except Exception as e:
            registrar_evento(f"[WARN] Monitor error: {e}", "warn")
        time.sleep(5)


def publicar_heartbeat_cps():
    """Publica el estado actual de todos los CPs conectados para que el dashboard lo detecte."""
    try:
        with CONEXIONES_ACTIVAS_LOCK:
            cps_conectados = list(CONEXIONES_ACTIVAS.keys())
        
        if not cps_conectados:
            return
        
        print(f"[CENTRAL] 💓 Publicando heartbeat para {len(cps_conectados)} CP(s) conectados...")
        
        for cp_id in cps_conectados:
            try:
                # Obtener telemetría actual o crear una básica
                with TELEMETRIA_ACTUAL_LOCK:
                    telemetria = TELEMETRIA_ACTUAL.get(cp_id, {})
                
                # Obtener estado autoritativo desde CP_ESTADO (prioridad sobre telemetría)
                with CP_ESTADO_LOCK:
                    estado_autoritativo = CP_ESTADO.get(cp_id, 'ACTIVADO')
                
                # Estados interactivos que deben preservarse (no sobrescribir con ACTIVADO)
                estados_interactivos = {
                    'PENDIENTE_CONFIRMACION_CENTRAL',
                    'ESPERANDO_OPERADOR_ENGINE',
                    'LISTO_PARA_INICIAR',
                    'ESPERANDO_CONFIRMACION_FIN'
                }
                
                # Si el estado autoritativo es interactivo, usarlo; si no, usar el de telemetría si existe
                if estado_autoritativo.upper() in estados_interactivos:
                    estado_a_publicar = estado_autoritativo
                else:
                    # Usar estado de telemetría si existe, sino el autoritativo
                    estado_a_publicar = telemetria.get('estado', telemetria.get('estado_carga', estado_autoritativo))
                
                # Asegurar que tenga los campos mínimos
                if not telemetria or 'timestamp' not in telemetria:
                    with CP_PRECIO_KWH_LOCK:
                        precio = CP_PRECIO_KWH.get(cp_id, 0.0)
                    
                    telemetria = {
                        'cp_id': cp_id,
                        'estado_carga': estado_a_publicar,
                        'estado': estado_a_publicar,
                        'potencia_actual': 0.0,
                        'energia_total': 0.0,
                        'kw_entregados': 0.0,
                        'tiempo_carga_s': 0,
                        'timestamp': time.time(),
                        'precio_kwh': precio,
                        'tiene_sesion_activa': False,
                        'driver_id_sesion': None
                    }
                else:
                    # Actualizar timestamp y estado del heartbeat (preservar estado interactivo)
                    telemetria = {
                        **telemetria,
                        'timestamp': time.time(),
                        'estado_carga': estado_a_publicar,
                        'estado': estado_a_publicar
                    }
                
                # Enriquecer con información de sesión
                with CP_SESION_DRIVER_ID_LOCK:
                    telemetria['tiene_sesion_activa'] = cp_id in CP_SESION_DRIVER_ID
                    telemetria['driver_id_sesion'] = CP_SESION_DRIVER_ID.get(cp_id, None)
                
                # Publicar en Kafka
                if KAFKA_PRODUCER:
                    KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria)
                    print(f"[CENTRAL]   → {cp_id}: {telemetria.get('estado', 'N/D')}")
                
            except Exception as e:
                print(f"[CENTRAL] ✗ Error publicando heartbeat de {cp_id}: {e}")
        
        # Flush para asegurar envío
        if KAFKA_PRODUCER:
            KAFKA_PRODUCER.flush(timeout=1)
            print(f"[CENTRAL] ✓ Heartbeat enviado correctamente a Kafka")
            
    except Exception as e:
        print(f"[CENTRAL] ✗ Error en publicar_heartbeat_cps: {e}")
        import traceback
        traceback.print_exc()
def mostrar_estado_red():
    """Compat: imprime estado (modo no-TUI); preservado por si se usa sin Rich."""
    print("\n" + "="*60)
    print(f"| ESTADO DE LA RED DE CARGA (Total: {len(CONEXIONES_ACTIVAS)} CP(s) Activos) |")
    print("="*60)
    if not CONEXIONES_ACTIVAS:
        print(">> No hay Puntos de Carga conectados actualmente.")
        print("="*60)
        return
    for cp_id, socket_obj in CONEXIONES_ACTIVAS.items():
        print(f"| CP ID: {cp_id}")
        print(f"|   Socket: Conectado en {socket_obj.getsockname()[1]}")
        # Mostrar estado consolidado conocido por la Central
        with CP_ESTADO_LOCK:
            estado_central = CP_ESTADO.get(cp_id, 'DESCONOCIDO')
        if estado_central == 'PARADO':
            print(f"|   Estado: PARADO  (Out of Order)")
        with TELEMETRIA_ACTUAL_LOCK:
            telemetria = TELEMETRIA_ACTUAL.get(cp_id)
        if telemetria:
            estado = telemetria.get('estado', 'DESCONOCIDO')
            potencia_actual = telemetria.get('potencia_actual', 'N/A')
            energia_total = telemetria.get('energia_total', 'N/A')
            timestamp = telemetria.get('timestamp', 'N/A')
            print(f"|   Estado: {estado}")
            print(f"|   Potencia Actual: {potencia_actual} kW")
            print(f"|   Energía Total: {energia_total} kWh")
            print(f"|   Última Actualización: {timestamp}")
            try:
                with CP_SESION_OBJETIVO_KWH_LOCK:
                    obj = CP_SESION_OBJETIVO_KWH.get(cp_id)
                if obj is not None:
                    print(f"|   Objetivo: {float(obj):.2f} kWh")
            except Exception:
                pass
        else:
            print(f"|   Estado: Sin telemetría disponible")
            print(f"|   (Conectado pero sin datos de Kafka)")
        print("-"*60)

def interfaz_consola_central():
    """Deprecado por TUI Rich. Mantener por compatibilidad si TUI no está disponible."""
    registrar_evento("Modo consola simple activado")
    while True:
        comando = input("\n[CENTRAL CMD] (ej.: 2 START CP001 | 3=salir) > ").strip()
        if not comando:
            continue
        COMMAND_QUEUE.put(comando)
        time.sleep(0.1)

def render_panel():
    """Renderiza un panel completo con toda la información de telemetría y eventos."""
    # Layout principal dividido en secciones
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="events", size=12)
    )
    
    # === HEADER ===
    header_text = Text()
    header_text.append("🚗 ", style="bold cyan")
    header_text.append("SISTEMA CENTRAL DE CARGA EV", style="bold white")
    header_text.append(f" | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style="dim")
    layout["header"].update(Panel(header_text, style="bold cyan"))
    
    # === MAIN - TABLA DE CHARGING POINTS ===
    table = Table(title="📊 TELEMETRÍA EN TIEMPO REAL", box=box.DOUBLE_EDGE, expand=True)
    table.add_column("CP ID", justify="center", style="bold white", width=10)
    table.add_column("Estado", justify="center", width=15)
    table.add_column("Driver", justify="center", width=12)
    table.add_column("Potencia\n(kW)", justify="right", width=10)
    table.add_column("Energía\n(kWh)", justify="right", width=10)
    table.add_column("Precio\n(€/kWh)", justify="right", width=10)
    table.add_column("Importe\n(€)", justify="right", width=10)
    table.add_column("Tiempo\n(s)", justify="right", width=10)
    table.add_column("Última Act.", justify="center", width=12)
    
    with TELEMETRIA_ACTUAL_LOCK:
        if not TELEMETRIA_ACTUAL:
            table.add_row(
                "[dim]---[/dim]", 
                "[dim]Sin CPs conectados[/dim]", 
                "[dim]---[/dim]", "[dim]---[/dim]", "[dim]---[/dim]", 
                "[dim]---[/dim]", "[dim]---[/dim]", "[dim]---[/dim]", "[dim]---[/dim]"
            )
        else:
            for cp_id in sorted(TELEMETRIA_ACTUAL.keys()):
                data = TELEMETRIA_ACTUAL[cp_id]
                estado = CP_ESTADO.get(cp_id, "N/D")
                
                # Driver actual
                driver_id = CP_SESION_DRIVER_ID.get(cp_id, "---")
                if driver_id == "---" or driver_id is None:
                    driver_str = "[dim]---[/dim]"
                else:
                    driver_str = f"[cyan]{driver_id}[/cyan]"
                
                # Telemetría
                potencia = data.get("potencia_actual", 0.0)
                energia = data.get("kw_entregados") or data.get("energia_total", 0.0)
                tiempo_s = data.get("tiempo_carga_s", 0)
                precio_kwh = CP_PRECIO_KWH.get(cp_id, data.get("precio_kwh", 0.0))
                
                # Calcular importe
                importe = float(energia) * float(precio_kwh) if precio_kwh else 0.0
                
                # Tiempo desde última actualización
                t_ago = round(time.time() - data.get("timestamp", 0), 1)
                
                # Color según estado
                color = {
                    "ACTIVADO": "green",
                    "SUMINISTRANDO": "cyan",
                    "DESCONECTADO": "red",
                    "AVERÍA": "magenta",
                    "DESACTIVADO": "yellow"
                }.get(str(estado).upper(), "white")
                
                table.add_row(
                    f"[bold]{cp_id}[/bold]",
                    f"[{color}]{estado}[/{color}]",
                    driver_str,
                    f"{float(potencia):.2f}",
                    f"{float(energia):.3f}",
                    f"{float(precio_kwh):.3f}",
                    f"{importe:.2f}",
                    f"{tiempo_s}",
                    f"{t_ago}s" if t_ago < 10 else f"[yellow]{t_ago}s[/yellow]"
                )
    
    layout["main"].update(Panel(table, title="[bold]Charging Points Activos[/bold]", border_style="cyan"))
    
    # === EVENTS - REGISTRO DE EVENTOS RECIENTES ===
    events_table = Table(title="📝 EVENTOS RECIENTES", box=box.SIMPLE, expand=True, show_header=False)
    events_table.add_column("Evento", justify="left", style="dim")
    
    with EVENT_LOG_LOCK:
        eventos_recientes = list(EVENT_LOG)[-10:]  # Últimos 10 eventos
        if not eventos_recientes:
            events_table.add_row("[dim italic]Sin eventos registrados aún...[/dim italic]")
        else:
            for evento in eventos_recientes:
                events_table.add_row(evento)
    
    layout["events"].update(Panel(events_table, title="[bold]Log de Eventos[/bold]", border_style="yellow"))
    
    return layout

def iniciar_interfaz_visual():
    with Live(render_panel(), refresh_per_second=1, console=console) as live:
        while not SHUTDOWN_REQUESTED:
            live.update(render_panel())
            time.sleep(2)
            
def manejar_cliente(conn: socket.socket, addr: tuple, db_connection):
    """Función ejecutada por un hilo para manejar la conexión de un CP."""
    
    print(f"[CENTRAL] Conexión establecida con {addr[0]}:{addr[1]}")
    cp_id = "Desconocido"
    
    try:
        # Establecer timeout para permitir cierre limpio
        conn.settimeout(1.0)
        rx_buffer = b''

        # --- 1. REGISTRO Y AUTENTICACIÓN (Primer intercambio) ---
        while True:
            # Verificar si se solicita el apagado antes de bloquear
            with SHUTDOWN_LOCK:
                if SHUTDOWN_REQUESTED:
                    print(f"[CENTRAL] Apagado solicitado antes de registro, cerrando conexión con {addr[0]}:{addr[1]}...")
                    return
            try:
                chunk = conn.recv(2048)
            except socket.timeout:
                continue
            if not chunk:
                raise ConnectionResetError("Conexión cerrada por el cliente antes del registro.")
            rx_buffer += chunk
            frames, rx_buffer = _extraer_tramas_desde_buffer(rx_buffer)
            if not frames:
                continue
            # Solo se procesa la primera trama como REG; el resto queda para el bucle permanente
            trama_bytes = frames[0]
            if len(frames) > 1:
                # Reinyectar el resto al buffer para procesarlo después
                rx_buffer = b''.join(frames[1:]) + rx_buffer
            break

        # El primer mensaje REG no está cifrado (aún no hay clave)
        cod_op, campos = descomponer_trama(trama_bytes, cp_id=None)

        if cod_op is None or campos is None:
            mensaje_error = f"Imposible conectar con CP. Mensajes no comprensibles"
            print(f"[CENTRAL] ❌ {mensaje_error}")
            registrar_evento(f"❌ {mensaje_error}", "error")
            conn.close()
            return

        if cod_op == 'REG' and len(campos) >= 3:
            cp_id = campos[0]
            ubicacion = campos[1]
            precio_kwh = float(campos[2])
            
            # Extraer credenciales si están presentes (nuevo formato: REG#cp_id#ubicacion#precio#username#password)
            username = None
            password = None
            if len(campos) >= 5:
                username = campos[3]
                password = campos[4]

            # ====== VERIFICAR SI EL MONITOR ESTÁ BLOQUEADO MANUALMENTE ======
            with CP_MONITOR_BLOQUEADO_LOCK:
                esta_bloqueado = cp_id in CP_MONITOR_BLOQUEADO
            
            if esta_bloqueado:
                print(f"\n[CENTRAL] ╔═══════════════════════════════════════════╗")
                print(f"[CENTRAL] ║  🚫 CONEXIÓN RECHAZADA                    ║")
                print(f"[CENTRAL] ╚═══════════════════════════════════════════╝")
                print(f"[CENTRAL]    CP ID: {cp_id}")
                print(f"[CENTRAL]    Motivo: Monitor desconectado manualmente")
                print(f"[CENTRAL]    Acción: Use 'Reconectar Monitor' en el dashboard")
                print(f"[CENTRAL] ═══════════════════════════════════════════\n")
                registrar_evento(f"🚫 CONEXIÓN RECHAZADA: {cp_id} está bloqueado manualmente", "warn")
                
                # Enviar mensaje de rechazo al Monitor (sin cifrar, es antes del registro)
                try:
                    trama_reject = construir_trama('REJECT', ['Monitor bloqueado manualmente. Use boton Reconectar en dashboard.'], cp_id=None, cifrar=False)
                    conn.sendall(trama_reject)
                except Exception:
                    pass
                
                # Cerrar conexión
                conn.close()
                return

            # ====== DETECCIÓN DE RECONEXIÓN ======
            with CONEXIONES_ACTIVAS_LOCK:
                ya_conectado = cp_id in CONEXIONES_ACTIVAS

            print(f"\n[CENTRAL] ╔═══════════════════════════════════════════╗")
            if ya_conectado:
                print(f"[CENTRAL] ║  🔄 RECONEXIÓN DE CHARGING POINT         ║")
                registrar_evento(f"🔄 RECONEXIÓN: CP {cp_id} se ha reconectado correctamente.", "ok")
            else:
                print(f"[CENTRAL] ║  ✅ NUEVO CHARGING POINT REGISTRADO      ║")
                registrar_evento(f"✅ NUEVO CP: Registro inicial de {cp_id}.", "ok")
            print(f"[CENTRAL] ╚═══════════════════════════════════════════╝")
            print(f"[CENTRAL]    CP ID: {cp_id}")
            print(f"[CENTRAL]    Ubicación: {ubicacion}")
            print(f"[CENTRAL]    Precio: {precio_kwh} €/kWh")
            print(f"[CENTRAL]    Estado: ACTIVADO")
            print(f"[CENTRAL] ═══════════════════════════════════════════\n")
            
            if ya_conectado:
                try:
                    cambiar_estado_cp(cp_id, 'ACTIVADO', db_connection)
                except Exception:
                    pass
            
            registrar_evento(f"⚡ CP {cp_id} registrado y conectado ({ubicacion})", "ok")
            # Estado: ACTIVADO tras registro exitoso
            try:
                cambiar_estado_cp(cp_id, 'ACTIVADO', db_connection)
            except Exception:
                pass
            # Guardar el precio comunicado por el CP para cálculos de importe en tiempo real
            try:
                with CP_PRECIO_KWH_LOCK:
                    CP_PRECIO_KWH[cp_id] = precio_kwh
            except Exception:
                pass
            
            # --- PUBLICAR ESTADO INICIAL EN KAFKA PARA QUE EL DASHBOARD LO DETECTE ---
            try:
                telemetria_inicial = {
                    'cp_id': cp_id,
                    'estado_carga': 'ACTIVADO',
                    'estado': 'ACTIVADO',
                    'potencia_actual': 0.0,
                    'energia_total': 0.0,
                    'kw_entregados': 0.0,
                    'tiempo_carga_s': 0,
                    'timestamp': time.time(),
                    'ubicacion': ubicacion,
                    'precio_kwh': precio_kwh,
                    'tiene_sesion_activa': False,
                    'driver_id_sesion': None
                }
                with TELEMETRIA_ACTUAL_LOCK:
                    TELEMETRIA_ACTUAL[cp_id] = telemetria_inicial
                
                if KAFKA_PRODUCER is None:
                    print(f"[CENTRAL] ✗ ADVERTENCIA: Productor Kafka no disponible, no se puede publicar telemetría de {cp_id}")
                else:
                    print(f"[CENTRAL] → Publicando telemetría inicial de {cp_id} en topic '{TELEMETRIA_TOPIC}'...")
                    future = KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_inicial)
                    KAFKA_PRODUCER.flush(timeout=2)
                    print(f"[CENTRAL] ✓ Telemetría inicial de {cp_id} publicada correctamente en Kafka")
                    registrar_evento(f"Telemetría inicial publicada para {cp_id}", "ok")
            except Exception as e:
                print(f"[CENTRAL] ✗ ERROR publicando telemetría inicial de {cp_id}: {e}")
                import traceback
                traceback.print_exc()
            
            # --- VERIFICAR REGISTRO Y CREDENCIALES EN EV_Registry ---
            origen_ip = addr[0] if addr else None
            
            # Verificar que el CP esté registrado (usando BD compartida si está disponible)
            if not verificar_registro_cp(cp_id, db_connection):
                # CP no registrado en EV_Registry
                respuesta_trama = construir_trama('AUTH', ['FAIL', 'CP no registrado en EV_Registry. Debe registrarse primero.'], cp_id=None, cifrar=False)
                conn.sendall(respuesta_trama)
                print(f"[CENTRAL] <- Enviada respuesta AUTH: FAIL a {cp_id} (No registrado)")
                registrar_evento(f"❌ AUTH DENEGADO: {cp_id} no registrado en EV_Registry", "error")
                registrar_auditoria(
                    accion="INTENTO_AUTENTICACION",
                    cp_id=cp_id,
                    origen_ip=origen_ip,
                    descripcion="Intento de autenticación sin registro previo en EV_Registry",
                    resultado="DENEGADO",
                    db_connection=db_connection
                )
                return
            
            # Verificar credenciales si fueron proporcionadas
            if username and password:
                print(f"\n[CENTRAL] ╔═══════════════════════════════════════════╗")
                print(f"[CENTRAL] ║  🔐 VERIFICANDO CREDENCIALES CON REGISTRY  ║")
                print(f"[CENTRAL] ╚═══════════════════════════════════════════╝")
                print(f"[CENTRAL]    CP ID: {cp_id}")
                print(f"[CENTRAL]    Username: {username}")
                print(f"[CENTRAL]    Verificando con EV_Registry...")
                
                if not verificar_credenciales_registry(cp_id, username, password, db_connection):
                    # Credenciales inválidas
                    respuesta_trama = construir_trama('AUTH', ['FAIL', 'Credenciales inválidas. Verifique username y password de EV_Registry.'], cp_id=None, cifrar=False)
                    conn.sendall(respuesta_trama)
                    print(f"[CENTRAL] ❌ CREDENCIALES INVÁLIDAS")
                    print(f"[CENTRAL]    El Registry rechazó las credenciales proporcionadas")
                    print(f"[CENTRAL] ═══════════════════════════════════════════\n")
                    registrar_evento(f"❌ AUTH DENEGADO: {cp_id} credenciales inválidas", "error")
                    registrar_auditoria(
                        accion="INTENTO_AUTENTICACION",
                        cp_id=cp_id,
                        origen_ip=origen_ip,
                        descripcion=f"Intento de autenticación con credenciales inválidas (username: {username[:10]}...)",
                        resultado="DENEGADO",
                        db_connection=db_connection
                    )
                    return
                else:
                    print(f"[CENTRAL] ✓ CREDENCIALES VÁLIDAS")
                    print(f"[CENTRAL]    EV_Registry confirmó que las credenciales son correctas")
                    print(f"[CENTRAL]    Autenticación exitosa mediante Registry")
                    print(f"[CENTRAL] ═══════════════════════════════════════════\n")
                    registrar_evento(f"✓ AUTH OK: {cp_id} autenticado con credenciales del Registry", "ok")
                    registrar_auditoria(
                        accion="VERIFICACION_CREDENCIALES",
                        cp_id=cp_id,
                        origen_ip=origen_ip,
                        descripcion=f"Credenciales verificadas correctamente con EV_Registry (username: {username[:10]}...)",
                        resultado="OK",
                        db_connection=db_connection
                    )
            else:
                # No se proporcionaron credenciales, solo verificar registro (modo compatibilidad)
                print(f"[CENTRAL] ⚠️ No se proporcionaron credenciales en REG. Verificando solo registro...")
            
            # --- OBTENER O GENERAR CLAVE DE CIFRADO ---
            clave_cifrado = obtener_clave_cifrado_cp(cp_id, db_connection)
            clave_b64 = base64.b64encode(clave_cifrado).decode('utf-8')
            
            # --- LÓGICA BD: Insertar/Actualizar CP y marcar como ACTIVADO ---
            if _verificar_conexion(db_connection):
                if registrar_cp_en_bd(db_connection, cp_id, ubicacion, precio_kwh):
                    # Enviar AUTH con clave de cifrado (sin cifrar, es el primer mensaje después de REG)
                    respuesta_trama = construir_trama('AUTH', ['OK', 'Autenticacion exitosa', clave_b64], cp_id=None, cifrar=False)
                    conn.sendall(respuesta_trama)
                    print(f"[CENTRAL] <- Enviada respuesta AUTH: OK a {cp_id} (con clave de cifrado)")
                    registrar_evento(f"AUTH OK enviado a {cp_id} (clave de cifrado proporcionada)")
                    registrar_auditoria(
                        accion="AUTENTICACION",
                        cp_id=cp_id,
                        origen_ip=origen_ip,
                        descripcion=f"Autenticación exitosa. Clave de cifrado proporcionada.",
                        resultado="OK",
                        db_connection=db_connection
                    )
                else:
                    # Error en BD, rechazar conexión (sin cifrar)
                    respuesta_trama = construir_trama('AUTH', ['FAIL', 'Error en base de datos'], cp_id=None, cifrar=False)
                    conn.sendall(respuesta_trama)
                    print(f"[CENTRAL] <- Enviada respuesta AUTH: FAIL a {cp_id} (Error BD)")
                    registrar_auditoria(
                        accion="AUTENTICACION",
                        cp_id=cp_id,
                        origen_ip=origen_ip,
                        descripcion="Error en base de datos durante autenticación",
                        resultado="ERROR",
                        db_connection=db_connection
                    )
                    return
            else:
                # Sin BD, intentar reconectar y registrar
                print(f"[CENTRAL] ADVERTENCIA: Sin conexión a BD, intentando reconectar...")
                db_connection = _asegurar_conexion_bd(db_connection)
                
                if _verificar_conexion(db_connection):
                    # Reconectó, intentar registrar ahora
                    if registrar_cp_en_bd(db_connection, cp_id, ubicacion, precio_kwh):
                        respuesta_trama = construir_trama('AUTH', ['OK', 'Autenticacion exitosa', clave_b64], cp_id=None, cifrar=False)
                        conn.sendall(respuesta_trama)
                        print(f"[CENTRAL] <- Enviada respuesta AUTH: OK a {cp_id} (con clave de cifrado)")
                        registrar_evento(f"AUTH OK enviado a {cp_id} (clave de cifrado proporcionada)")
                        registrar_auditoria(
                            accion="AUTENTICACION",
                            cp_id=cp_id,
                            origen_ip=origen_ip,
                            descripcion=f"Autenticación exitosa. Clave de cifrado proporcionada.",
                            resultado="OK",
                            db_connection=db_connection
                        )
                    else:
                        # Falló registro pero BD está conectada
                        respuesta_trama = construir_trama('AUTH', ['OK', 'Autenticacion exitosa (error al registrar en BD)', clave_b64], cp_id=None, cifrar=False)
                        conn.sendall(respuesta_trama)
                        print(f"[CENTRAL] <- Enviada respuesta AUTH: OK a {cp_id} (error al registrar en BD)")
                        registrar_evento(f"AUTH OK enviado a {cp_id} (error al registrar en BD)")
                else:
                    # Sin BD, aceptar conexión pero advertir (sin cifrar)
                    print(f"[CENTRAL] ADVERTENCIA: Sin conexión a BD, aceptando {cp_id} sin persistencia")
                    respuesta_trama = construir_trama('AUTH', ['OK', 'Autenticacion exitosa (sin BD)', clave_b64], cp_id=None, cifrar=False)
                    conn.sendall(respuesta_trama)
                    print(f"[CENTRAL] <- Enviada respuesta AUTH: OK a {cp_id} (sin BD, con clave)")
                    registrar_evento(f"AUTH OK enviado a {cp_id} (sin BD, clave proporcionada)")
                    registrar_auditoria(
                        accion="AUTENTICACION",
                        cp_id=cp_id,
                        origen_ip=origen_ip,
                        descripcion="Autenticación exitosa sin BD (modo degradado)",
                        resultado="OK",
                        db_connection=None
                    )
            
            # --- ALMACENAR CONEXIÓN SOLO DESPUÉS DE COMPLETAR AUTENTICACIÓN ---
            with CONEXIONES_ACTIVAS_LOCK:
                CONEXIONES_ACTIVAS[cp_id] = conn
                print(f"[CENTRAL] Socket de {cp_id} guardado. Total: {len(CONEXIONES_ACTIVAS)}")
            
            # --- PROCESAR COLA SI HAY DRIVERS ESPERANDO ---
            try:
                with CP_COLA_ESPERA_LOCK:
                    if cp_id in CP_COLA_ESPERA and not CP_COLA_ESPERA[cp_id].empty():
                        from queue import Empty
                        try:
                            next_driver, next_kw, timestamp_cola = CP_COLA_ESPERA[cp_id].get_nowait()
                            print(f"[CENTRAL] 🔄 CP {cp_id} reconectado. Procesando primer driver en cola: {next_driver}")
                            
                            # Registrar sesión
                            with CP_SESION_DRIVER_ID_LOCK:
                                CP_SESION_DRIVER_ID[cp_id] = next_driver
                            with CP_SESION_OBJETIVO_KWH_LOCK:
                                CP_SESION_OBJETIVO_KWH[cp_id] = next_kw
                            
                            # Estado: PENDIENTE_CONFIRMACION_CENTRAL
                            try:
                                cambiar_estado_cp(cp_id, 'PENDIENTE_CONFIRMACION_CENTRAL', db_connection)
                            except Exception:
                                pass
                            
                            # Publicar telemetría para que aparezca el botón en el dashboard
                            try:
                                with TELEMETRIA_ACTUAL_LOCK:
                                    telemetria_actual = TELEMETRIA_ACTUAL.get(cp_id, {})
                                # Resetear contadores para nueva sesión
                                telemetria_actualizada = {
                                    **telemetria_actual,
                                    'cp_id': cp_id,
                                    'estado_carga': 'PENDIENTE_CONFIRMACION_CENTRAL',
                                    'estado': 'PENDIENTE_CONFIRMACION_CENTRAL',
                                    'timestamp': time.time(),
                                    'tiene_sesion_activa': True,
                                    'driver_id_sesion': next_driver,
                                    'objetivo_kwh': next_kw,
                                    # Resetear contadores
                                    'kw_entregados': 0.0,
                                    'energia_total': 0.0,
                                    'potencia_actual': 0.0,
                                    'tiempo_carga_s': 0
                                }
                                with TELEMETRIA_ACTUAL_LOCK:
                                    TELEMETRIA_ACTUAL[cp_id] = telemetria_actualizada
                                if KAFKA_PRODUCER:
                                    KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_actualizada)
                                    KAFKA_PRODUCER.flush(timeout=1)
                                    print(f"[CENTRAL] ✓ Telemetría PENDIENTE_CONFIRMACION_CENTRAL publicada para {cp_id} (driver: {next_driver}, contadores reseteados)")
                            except Exception as e:
                                print(f"[CENTRAL] Error publicando telemetría (reconexión→cola): {e}")
                            
                            # Notificar al driver
                            notificar_driver(next_driver, 'EN_ESPERA_CONFIRMACION', {
                                'mensaje': f'CP {cp_id} reconectado. Solicitud pendiente de confirmación del operador de Central.',
                                'cp_id': cp_id,
                                'kw_disponibles': next_kw
                            })
                            registrar_evento(f"✅ Driver {next_driver} pasado de cola a pendiente tras reconexión de {cp_id}", "ok")
                        except Empty:
                            pass
            except Exception as e:
                print(f"[CENTRAL] Error procesando cola tras reconexión de {cp_id}: {e}")

        else:
            print(f"[CENTRAL] Error: Mensaje inicial no válido ({cod_op}). Cerrando conexión.")
            return # Sale de la función y va al finally

        # --- 2. BUCLE DE COMUNICACIÓN PERMANENTE ---
        print(f"[CENTRAL] Hilo {cp_id} iniciando bucle de escucha permanente.")
        lrc_errors_consecutivos = 0
        decrypt_errors_consecutivos = 0
        while True:
            # Verificar si se solicita el apagado
            with SHUTDOWN_LOCK:
                if SHUTDOWN_REQUESTED:
                    print(f"[CENTRAL] Apagado solicitado, cerrando conexión con {cp_id}...")
                    break
            
            # Leer datos TCP y extraer tramas completas
            try:
                chunk = conn.recv(4096)
            except socket.timeout:
                continue

            if not chunk:
                print(f"[CENTRAL] Conexión con CP {cp_id} cerrada por el cliente.")
                break

            rx_buffer += chunk
            frames, rx_buffer = _extraer_tramas_desde_buffer(rx_buffer)
            if not frames:
                continue

            for trama_bytes in frames:
                # Después del REG, todos los mensajes deben estar cifrados
                cod_op, campos = descomponer_trama(trama_bytes, cp_id=cp_id)

                if not cod_op and trama_bytes:
                    # Distinguir LRC/FORMATO vs descifrado para no tumbar la conexión por fragmentación
                    es_enc = (len(trama_bytes) >= 4 and trama_bytes[1:4] == b'ENC') or (b'ENC' in trama_bytes)
                    lrc_ok = _validar_trama_lrc_y_formato(trama_bytes)

                    if not lrc_ok:
                        lrc_errors_consecutivos += 1
                        decrypt_errors_consecutivos = 0
                        if lrc_errors_consecutivos >= 3:
                            print(f"[CENTRAL] ⚠️ Demasiados errores LRC consecutivos con {cp_id}. Cerrando conexión.")
                            break
                        # Trama corrupta/partial: descartar y seguir
                        continue

                    # LRC ok pero no se pudo parsear/descifrar => probable clave mala
                    if es_enc:
                        decrypt_errors_consecutivos += 1
                        lrc_errors_consecutivos = 0
                        print(f"[CENTRAL] ⚠️ ERROR: No se pudo descifrar mensaje de {cp_id}. Clave posiblemente revocada.")
                        registrar_evento(f"🔑 ERROR: No se pudo descifrar mensaje de {cp_id}. Clave revocada o inválida.", "warn")
                        registrar_auditoria(
                            accion="ERROR_CIFRADO",
                            cp_id=cp_id,
                            origen_ip=addr[0] if addr else None,
                            descripcion="Mensaje cifrado recibido pero no se pudo descifrar. Clave posiblemente revocada.",
                            resultado="ERROR",
                            db_connection=db_connection
                        )
                        if decrypt_errors_consecutivos >= 2:
                            print(f"[CENTRAL] Cerrando conexión con {cp_id} para forzar reautenticación...")
                            break
                        continue

                    # No cifrado (o trama rara) y no parseable: descartar
                    continue

                # Si llegamos aquí, la trama fue OK
                lrc_errors_consecutivos = 0
                decrypt_errors_consecutivos = 0
            
                if cod_op:
                    # Evitar saturar consola: modo resumido por defecto (configurable por env)
                    if (not CENTRAL_VERBOSE_MESSAGES) and (cod_op in CENTRAL_NOISY_OPS):
                        try:
                            ahora = time.time()
                            key = (cp_id, cod_op)
                            with _MSG_THROTTLE_LOCK:
                                entry = _MSG_THROTTLE.get(key)
                                if not entry:
                                    entry = {'count': 0, 'last_ts': 0.0}
                                    _MSG_THROTTLE[key] = entry
                                entry['count'] += 1
                                if (ahora - entry['last_ts']) >= _MSG_THROTTLE_SECS:
                                    count = entry['count']
                                    entry['count'] = 0
                                    entry['last_ts'] = ahora
                                    registrar_evento(f"📨 {cp_id}: [{cod_op}] x{count} (resumido)", "info")
                        except Exception:
                            # Si falla el throttle, no romper el bucle
                            pass
                    else:
                        # Registrar TODOS los mensajes recibidos con formato claro
                        registrar_evento(f"📨 MENSAJE de {cp_id}: [{cod_op}] Campos={campos}", "info")
                        print(f"[CENTRAL] ========================================")
                        print(f"[CENTRAL] 📨 TRAMA RECIBIDA de {cp_id}")
                        print(f"[CENTRAL]    Código Operación: {cod_op}")
                        print(f"[CENTRAL]    Campos: {campos}")
                        print(f"[CENTRAL] ========================================")
                    # Manejo de tramas específicas desde el CP
                    if cod_op == 'AUTH_RESP' and len(campos) >= 2:
                        # Esperado: AUTH_RESP#<driver_id>#<OK|KO>#<mensaje?>
                        try:
                            driver_id = campos[0]
                            resultado = campos[1].upper()
                            mensaje = campos[2] if len(campos) >= 3 else ''
                            if resultado == 'OK':
                                registrar_evento(f"[CONTROL] Confirmación síncrona de {cp_id}: AUTH_ACK#OK.")
                                # DEPRECADO: NO notificar "AUTORIZADO" aquí - se notificará tras confirmar inicio
                                # El driver debe esperar a que el operador del Engine inicie el suministro
                                print(f"[CENTRAL] {cp_id} confirmó AUTH_REQ. Esperando acción del operador del Engine...")
                                # NO cambiar estado aquí - mantener ESPERANDO_OPERADOR_ENGINE que se puso al enviar AUTH_REQ
                            else:
                                registrar_evento(f"[CONTROL] Confirmación síncrona de {cp_id}: AUTH_ACK#KO ({mensaje}).")
                                notificar_driver(driver_id, 'DENEGADO', {
                                    'cp_id': cp_id,
                                    'motivo': mensaje or 'CP denegó la autorización'
                                })
                                # Volver a ACTIVADO si denegado
                                try:
                                    cambiar_estado_cp(cp_id, 'ACTIVADO', db_connection)
                                except Exception:
                                    pass
                        except Exception as e:
                            print(f"[CENTRAL] Error procesando AUTH_RESP: {e}")
                    
                    # ====== NUEVO BLOQUE AÑADIDO: MANEJO DE FIN ====== 
                    elif cod_op == 'FIN' and len(campos) >= 4:
                        # FIN puede traer campos extra: [cp_id, driver_id, energia, importe, dur_s?, motivo?, tx_id?]
                        cp_fin = campos[0]
                        driver_id = campos[1]
                        energia = campos[2]
                        importe = campos[3]
                        dur_s = campos[4] if len(campos) > 4 else None
                        motivo = campos[5] if len(campos) > 5 else 'Consumo completado'
                        tx_id = campos[6] if len(campos) > 6 else None

                        registrar_evento(f"[CONTROL] Fin de carga recibido de {cp_fin}: {energia} kWh, {importe} €")

                        detalle_ticket = {
                            'cp_id': cp_fin,
                            'energia_kwh': energia,
                            'importe_eur': importe,
                        }
                        if dur_s is not None:
                            detalle_ticket['duracion_seg'] = dur_s
                        if motivo is not None:
                            detalle_ticket['motivo'] = motivo
                        if tx_id is not None:
                            detalle_ticket['tx_id'] = tx_id

                        # Enviar ticket al driver ANTES de limpiar sesión
                        notificar_driver(driver_id, 'TICKET_FINAL', detalle_ticket)
                        
                        print(f"[CENTRAL] ✅ Ticket enviado a {driver_id}. CP {cp_fin} listo para nuevo servicio.")
                        registrar_evento(f"✅ Ticket enviado a {driver_id}: {energia} kWh, {importe} €", "ok")

                        # Limpiar sesión actual ANTES de procesar la cola
                        with CP_SESION_DRIVER_ID_LOCK:
                            if cp_fin in CP_SESION_DRIVER_ID:
                                del CP_SESION_DRIVER_ID[cp_fin]
                                print(f"[CENTRAL] Sesión de {driver_id} en {cp_fin} limpiada")
                        with CP_SESION_OBJETIVO_KWH_LOCK:
                            if cp_fin in CP_SESION_OBJETIVO_KWH:
                                del CP_SESION_OBJETIVO_KWH[cp_fin]
                    
                    # Procesar siguiente driver en cola si existe
                    cola_procesada = False
                    try:
                        with CP_COLA_ESPERA_LOCK:
                            if cp_fin in CP_COLA_ESPERA and not CP_COLA_ESPERA[cp_fin].empty():
                                from queue import Empty
                                try:
                                    next_driver, next_kw, timestamp_cola = CP_COLA_ESPERA[cp_fin].get_nowait()
                                    print(f"[CENTRAL] 🔄 Procesando siguiente en cola: {next_driver} para {cp_fin}")
                                    cola_procesada = True
                                    
                                    # Autorizar al siguiente driver
                                    with CP_SESION_DRIVER_ID_LOCK:
                                        CP_SESION_DRIVER_ID[cp_fin] = next_driver
                                    with CP_SESION_OBJETIVO_KWH_LOCK:
                                        CP_SESION_OBJETIVO_KWH[cp_fin] = next_kw
                                    
                                    # NO enviar AUTH_REQ aún: seguir el flujo interactivo.
                                    # Estado: PENDIENTE_CONFIRMACION_CENTRAL para que Central pulse "PREPARAR SUMINISTRO"
                                    try:
                                        cambiar_estado_cp(cp_fin, 'PENDIENTE_CONFIRMACION_CENTRAL', db_connection)
                                    except Exception:
                                        pass

                                    # Publicar telemetría para que aparezca el botón en el dashboard
                                    try:
                                        with TELEMETRIA_ACTUAL_LOCK:
                                            telemetria_actual = TELEMETRIA_ACTUAL.get(cp_fin, {})
                                        # Resetear contadores para nueva sesión
                                        telemetria_actualizada = {
                                            **telemetria_actual,
                                            'cp_id': cp_fin,
                                            'estado_carga': 'PENDIENTE_CONFIRMACION_CENTRAL',
                                            'estado': 'PENDIENTE_CONFIRMACION_CENTRAL',
                                            'timestamp': time.time(),
                                            'tiene_sesion_activa': True,
                                            'driver_id_sesion': next_driver,
                                            'objetivo_kwh': next_kw,
                                            # Resetear contadores
                                            'kw_entregados': 0.0,
                                            'energia_total': 0.0,
                                            'potencia_actual': 0.0,
                                            'tiempo_carga_s': 0
                                        }
                                        with TELEMETRIA_ACTUAL_LOCK:
                                            TELEMETRIA_ACTUAL[cp_fin] = telemetria_actualizada
                                        if KAFKA_PRODUCER:
                                            KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_actualizada)
                                            KAFKA_PRODUCER.flush(timeout=1)
                                            print(f"[CENTRAL] ✓ Telemetría PENDIENTE_CONFIRMACION_CENTRAL publicada para {cp_fin} (driver: {next_driver}, contadores reseteados)")
                                    except Exception as e:
                                        print(f"[CENTRAL] No se pudo publicar telemetría (cola→pendiente): {e}")

                                    # Notificar al driver que su turno está pendiente de confirmación de Central
                                    notificar_driver(next_driver, 'EN_ESPERA_CONFIRMACION', {
                                        'mensaje': f'Solicitud en cola ahora pendiente de confirmación del operador de Central.',
                                        'cp_id': cp_fin,
                                        'kw_disponibles': next_kw
                                    })
                                    print(f"[CENTRAL] ✅ Driver {next_driver} notificado: EN_ESPERA_CONFIRMACION")

                                    registrar_evento(f"✅ Driver {next_driver} pasado de cola a pendiente de confirmación en {cp_fin}", "ok")
                                    
                                except Empty:
                                    pass
                    except Exception as e:
                        print(f"[CENTRAL] ✗ Error procesando cola de {cp_fin}: {e}")
                    
                    # Solo cambiar a ACTIVADO si NO se procesó nadie de la cola
                    if not cola_procesada:
                        cambiar_estado_cp(cp_fin, 'ACTIVADO', db_connection)
                        print(f"[CENTRAL] {cp_fin} sin cola pendiente. Estado: ACTIVADO")
                    
                    # Limpiar estado manual si estaba PARADO
                    try:
                        with CP_ESTADO_MANUAL_LOCK:
                            if cp_fin in CP_ESTADO_MANUAL:
                                del CP_ESTADO_MANUAL[cp_fin]
                    except Exception:
                        pass
                    
                    # Limpezas y publicación ACTIVADO solo si NO hay siguiente en cola
                    if not cola_procesada:
                        # Limpiar información de sesión del driver
                        try:
                            with CP_SESION_OBJETIVO_KWH_LOCK:
                                if cp_fin in CP_SESION_OBJETIVO_KWH:
                                    del CP_SESION_OBJETIVO_KWH[cp_fin]
                        except Exception:
                            pass
                        try:
                            with CP_SESION_DRIVER_ID_LOCK:
                                if cp_fin in CP_SESION_DRIVER_ID:
                                    del CP_SESION_DRIVER_ID[cp_fin]
                        except Exception:
                            pass
                        
                        # Publicar telemetría actualizada: CP en ACTIVADO, sin sesión, contadores en 0
                        try:
                            with TELEMETRIA_ACTUAL_LOCK:
                                telemetria_actual = TELEMETRIA_ACTUAL.get(cp_fin, {})
                            telemetria_actualizada = {
                                **telemetria_actual,
                                'cp_id': cp_fin,
                                'estado_carga': 'ACTIVADO',
                                'estado': 'ACTIVADO',
                                'timestamp': time.time(),
                                'tiene_sesion_activa': False,
                                'driver_id_sesion': None,
                                'kw_entregados': 0.0,
                                'potencia_actual': 0.0,
                                'tiempo_carga_s': 0
                            }
                            with TELEMETRIA_ACTUAL_LOCK:
                                TELEMETRIA_ACTUAL[cp_fin] = telemetria_actualizada
                            if KAFKA_PRODUCER:
                                KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_actualizada)
                                KAFKA_PRODUCER.flush(timeout=1)
                                print(f"[CENTRAL] CP {cp_fin} resetado y listo para nuevo servicio (ACTIVADO)")
                        except Exception as e:
                            print(f"[CENTRAL] Error publicando estado tras FIN: {e}")

                # NUEVO: Manejar READY_TO_START desde Monitor/Engine
                elif cod_op == 'READY_TO_START' and len(campos) >= 2:
                    try:
                        engine_cp_id = campos[0]
                        driver_id = campos[1]
                        print(f"[CENTRAL] 📩 READY_TO_START recibido de {engine_cp_id} (Driver: {driver_id})")
                        registrar_evento(f"[FLUJO] {engine_cp_id} listo para iniciar. Driver: {driver_id}. Esperando confirmación del operador de Central.", "info")
                        
                        # No degradar si ya está CARGANDO/SUMINISTRANDO
                        try:
                            with CP_ESTADO_LOCK:
                                estado_actual = CP_ESTADO.get(engine_cp_id, '')
                            if str(estado_actual).upper() in ("CARGANDO", "SUMINISTRANDO"):
                                print(f"[CENTRAL] Ignorando READY_TO_START para {engine_cp_id}: ya está {estado_actual}")
                                # Aun así, notificar al driver como autorizado si hiciera falta
                                notificar_driver(driver_id, 'AUTORIZADO', {
                                    'cp_id': engine_cp_id,
                                    'mensaje': 'CP en carga; READY_TO_START ignorado'
                                })
                                break
                        except Exception:
                            pass

                        # AHORA SÍ notificar al driver como AUTORIZADO (el Engine está listo)
                        notificar_driver(driver_id, 'AUTORIZADO', {
                            'cp_id': engine_cp_id,
                            'mensaje': 'CP listo para iniciar. Esperando confirmación final de Central.'
                        })
                        
                        # Marcar CP como pendiente de confirmación
                        with CP_PENDIENTE_CONFIRMACION_LOCK:
                            CP_PENDIENTE_CONFIRMACION[engine_cp_id] = 'LISTO_PARA_INICIAR'
                        
                        # Cambiar estado en BD y telemetría
                        try:
                            cambiar_estado_cp(engine_cp_id, 'LISTO_PARA_INICIAR', db_connection)
                        except Exception:
                            pass
                        
                        # Publicar telemetría actualizada
                        try:
                            with TELEMETRIA_ACTUAL_LOCK:
                                telemetria_actual = TELEMETRIA_ACTUAL.get(engine_cp_id, {})
                            telemetria_actualizada = {
                                **telemetria_actual,
                                'cp_id': engine_cp_id,
                                'estado_carga': 'LISTO_PARA_INICIAR',
                                'estado': 'LISTO_PARA_INICIAR',
                                'timestamp': time.time(),
                                'tiene_sesion_activa': True,
                                'driver_id_sesion': driver_id
                            }
                            with TELEMETRIA_ACTUAL_LOCK:
                                TELEMETRIA_ACTUAL[engine_cp_id] = telemetria_actualizada
                            if KAFKA_PRODUCER:
                                KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_actualizada)
                                KAFKA_PRODUCER.flush(timeout=1)
                        except Exception as e:
                            print(f"[CENTRAL] Error publicando telemetría: {e}")
                        
                    except Exception as e:
                        print(f"[CENTRAL] Error procesando READY_TO_START: {e}")
                
                # NUEVO: Manejar REQUEST_STOP desde Monitor/Engine
                elif cod_op == 'REQUEST_STOP' and len(campos) >= 4:
                    try:
                        engine_cp_id = campos[0]
                        driver_id = campos[1]
                        kw_actual = campos[2]
                        segundos = campos[3]
                        print(f"[CENTRAL] 📩 REQUEST_STOP recibido de {engine_cp_id} (Driver: {driver_id}, {kw_actual} kWh)")
                        registrar_evento(f"[FLUJO] {engine_cp_id} solicita fin. Driver: {driver_id}, {kw_actual} kWh. Esperando confirmación del operador de Central.", "info")
                        
                        # Marcar CP como pendiente de confirmación de fin
                        with CP_PENDIENTE_CONFIRMACION_LOCK:
                            CP_PENDIENTE_CONFIRMACION[engine_cp_id] = 'ESPERANDO_CONFIRMACION_FIN'
                        
                        # Cambiar estado en BD y telemetría
                        try:
                            cambiar_estado_cp(engine_cp_id, 'ESPERANDO_CONFIRMACION_FIN', db_connection)
                        except Exception:
                            pass
                        
                        # Publicar telemetría actualizada
                        try:
                            with TELEMETRIA_ACTUAL_LOCK:
                                telemetria_actual = TELEMETRIA_ACTUAL.get(engine_cp_id, {})
                            telemetria_actualizada = {
                                **telemetria_actual,
                                'cp_id': engine_cp_id,
                                'estado_carga': 'ESPERANDO_CONFIRMACION_FIN',
                                'estado': 'ESPERANDO_CONFIRMACION_FIN',
                                'timestamp': time.time(),
                                'kw_entregados': float(kw_actual),
                                'tiempo_carga_s': int(segundos)
                            }
                            with TELEMETRIA_ACTUAL_LOCK:
                                TELEMETRIA_ACTUAL[engine_cp_id] = telemetria_actualizada
                            if KAFKA_PRODUCER:
                                KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_actualizada)
                                KAFKA_PRODUCER.flush(timeout=1)
                        except Exception as e:
                            print(f"[CENTRAL] Error publicando telemetría: {e}")
                        
                    except Exception as e:
                        print(f"[CENTRAL] Error procesando REQUEST_STOP: {e}")
                
                # [Lógica para manejar AVR, Suministro síncrono, etc.]
                elif cod_op == 'AVR' and len(campos) >= 2:
                    try:
                        motivo = campos[0]
                        codigo = campos[1]
                        with CP_ALERTA_LOCK:
                            CP_ALERTA[cp_id] = True
                        registrar_evento(f"⚠️ Avería reportada por {cp_id}: {motivo} ({codigo})")
                        try:
                            cambiar_estado_cp(cp_id, 'AVERÍA', db_connection, motivo=f"{motivo} ({codigo})")
                        except Exception:
                            pass
                        
                        # Si hay una sesión activa en ESTE CP, cerrar la sesión y enviar ticket al driver
                        with CP_SESION_DRIVER_ID_LOCK:
                            driver_id_sesion = CP_SESION_DRIVER_ID.get(cp_id)
                        
                        # Validar que realmente hay una sesión activa en este CP específico
                        if driver_id_sesion and driver_id_sesion != 'UNKNOWN':
                            # Verificar también en la telemetría que el driver corresponde a este CP
                            with TELEMETRIA_ACTUAL_LOCK:
                                telemetria_actual = TELEMETRIA_ACTUAL.get(cp_id, {})
                            
                            # Validar que la telemetría es del CP correcto y tiene sesión activa
                            telemetria_cp_id = telemetria_actual.get('cp_id', '')
                            telemetria_driver_id = telemetria_actual.get('driver_id_sesion')
                            tiene_sesion_activa = telemetria_actual.get('tiene_sesion_activa', False)
                            
                            # Solo proceder si:
                            # 1. El CP de la telemetría coincide con el CP de la avería
                            # 2. Hay sesión activa según la telemetría
                            # 3. El driver de la telemetría coincide con el de la sesión (o no hay driver en telemetría pero sí en sesión)
                            if (telemetria_cp_id == cp_id or not telemetria_cp_id) and \
                               (tiene_sesion_activa or telemetria_driver_id == driver_id_sesion or not telemetria_driver_id):
                                
                                registrar_evento(f"⚠️ Avería detectada durante suministro activo. Cerrando sesión de {driver_id_sesion} en {cp_id}")
                                
                                # Calcular energía entregada
                                energia = (
                                    telemetria_actual.get('energia_total')
                                    if 'energia_total' in telemetria_actual
                                    else telemetria_actual.get('kw_entregados', 0.0)
                                )
                                try:
                                    energia_val = float(energia)
                                except Exception:
                                    energia_val = 0.0
                                
                                # Calcular duración
                                tiempo_carga_s = telemetria_actual.get('tiempo_carga_s', 0)
                                try:
                                    duracion_seg = int(tiempo_carga_s)
                                except Exception:
                                    duracion_seg = 0
                                
                                # Calcular importe usando precio del CP
                                with CP_PRECIO_KWH_LOCK:
                                    precio_kwh = CP_PRECIO_KWH.get(cp_id, 0.48)  # Precio por defecto 0.48
                                
                                try:
                                    precio_val = float(precio_kwh)
                                except Exception:
                                    precio_val = 0.48
                                
                                importe = round(energia_val * precio_val, 2)
                                
                                # Generar tx_id
                                tx_id = f"TX-{cp_id}-{int(time.time())}"
                                
                                # Crear ticket
                                detalle_ticket = {
                                    'cp_id': cp_id,
                                    'energia_kwh': energia_val,
                                    'importe_eur': importe,
                                    'duracion_seg': duracion_seg,
                                    'motivo': f'Avería: {motivo}',
                                    'tx_id': tx_id
                                }
                                
                                # IMPORTANTE: Enviar ticket al driver ANTES de cerrar la sesión
                                notificar_driver(driver_id_sesion, 'TICKET_FINAL', detalle_ticket)
                                registrar_evento(f"✅ Ticket enviado a {driver_id_sesion} por avería en {cp_id}: {energia_val} kWh, {importe} €", "ok")
                                print(f"[CENTRAL] ✅ Ticket enviado a {driver_id_sesion} por avería en {cp_id}. Energía: {energia_val} kWh, Importe: {importe} €")
                                
                                # Enviar STOP al CP para cerrar la sesión
                                try:
                                    _enviar_comando_cp(cp_id, 'STOP')
                                    registrar_evento(f"🛑 Comando STOP enviado a {cp_id} debido a avería")
                                except Exception as e:
                                    registrar_evento(f"⚠️ Error enviando STOP a {cp_id}: {e}", "warn")
                                
                                # Limpiar sesión DESPUÉS de enviar el ticket
                                with CP_SESION_DRIVER_ID_LOCK:
                                    if cp_id in CP_SESION_DRIVER_ID:
                                        del CP_SESION_DRIVER_ID[cp_id]
                                with CP_SESION_OBJETIVO_KWH_LOCK:
                                    if cp_id in CP_SESION_OBJETIVO_KWH:
                                        del CP_SESION_OBJETIVO_KWH[cp_id]
                                
                                print(f"[CENTRAL] Sesión de {driver_id_sesion} en {cp_id} cerrada debido a avería")
                            else:
                                # Hay sesión registrada pero no coincide con la telemetría - no enviar ticket
                                print(f"[CENTRAL] ⚠️ Avería en {cp_id} pero sesión no válida o no activa. Driver sesión: {driver_id_sesion}, Telemetría CP: {telemetria_cp_id}, Driver telemetría: {telemetria_driver_id}, Sesión activa: {tiene_sesion_activa}")
                                registrar_evento(f"⚠️ Avería en {cp_id} pero sesión no válida - no se enviará ticket", "warn")
                    except Exception as e:
                        registrar_evento(f"⚠️ Avería reportada por {cp_id}")
                        print(f"[CENTRAL] Error procesando AVR con sesión activa: {e}")
                        import traceback
                        traceback.print_exc()
                
                elif cod_op == 'AVR_CLR':
                    try:
                        motivo = campos[1] if len(campos) > 1 else 'RECUPERADA'
                        with CP_ALERTA_LOCK:
                            CP_ALERTA[cp_id] = False
                        cambiar_estado_cp(cp_id, 'ACTIVADO', db_connection, motivo=motivo)
                        
                        # IMPORTANTE: Resetear contadores de telemetría tras recuperación de avería
                        # Esto evita que energía residual de la sesión anterior aparezca en nuevas sesiones
                        with TELEMETRIA_ACTUAL_LOCK:
                            telemetria_actual = TELEMETRIA_ACTUAL.get(cp_id, {})
                            TELEMETRIA_ACTUAL[cp_id] = {
                                **telemetria_actual,
                                'cp_id': cp_id,
                                'estado': 'ACTIVADO',
                                'estado_carga': 'ACTIVADO',
                                'kw_entregados': 0.0,
                                'energia_total': 0.0,
                                'potencia_actual': 0.0,
                                'tiempo_carga_s': 0,
                                'tiene_sesion_activa': False,
                                'driver_id_sesion': None,
                                'timestamp': time.time()
                            }
                        
                        # Publicar telemetría reseteada a Kafka
                        if KAFKA_PRODUCER:
                            try:
                                KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=TELEMETRIA_ACTUAL[cp_id])
                                KAFKA_PRODUCER.flush(timeout=1)
                                print(f"[CENTRAL] ✓ Telemetría reseteada para {cp_id} tras recuperación de avería")
                            except Exception as e_kafka:
                                print(f"[CENTRAL] ⚠️ Error publicando telemetría reseteada: {e_kafka}")
                        
                        registrar_evento(f"✅ {cp_id} recuperado de avería: {motivo}")
                        print(f"[CENTRAL] {cp_id} marcado como ACTIVADO tras AVR_CLR")
                    except Exception as e:
                        print(f"[CENTRAL] Error procesando AVR_CLR: {e}")
                
                # ====== NUEVO BLOQUE AÑADIDO: MANEJO DE STATE ====== 
                elif cod_op == 'STATE' and len(campos) >= 2:
                    cp_state = campos[0]
                    nuevo_estado = campos[1]
                    registrar_evento(f"[CONTROL] Estado reportado por {cp_state}: {nuevo_estado}")
                    
                    try:
                        # No degradar estados interactivos por STATE "inocuos" del monitor
                        estado_actual = None
                        with CP_ESTADO_LOCK:
                            estado_actual = CP_ESTADO.get(cp_state)
                        estados_interactivos = {
                            'PENDIENTE_CONFIRMACION_CENTRAL',
                            'ESPERANDO_OPERADOR_ENGINE',
                            'LISTO_PARA_INICIAR',
                            'ESPERANDO_CONFIRMACION_FIN'
                        }
                        degradantes = {'ACTIVADO', 'PARADO', 'PRE-SUMINISTRO'}
                        if estado_actual and estado_actual.upper() in estados_interactivos and str(nuevo_estado).upper() in degradantes:
                            registrar_evento(f"[IGNORADO] STATE {cp_state}: {estado_actual} mantiene prioridad sobre {nuevo_estado}")
                        else:
                            cambiar_estado_cp(cp_state, nuevo_estado, db_connection)
                    except Exception as e:
                        registrar_evento(f"[ERROR] No se pudo actualizar el estado de {cp_state}: {e}")

            else:
                print(f"[CENTRAL] Trama inválida de {cp_id}.")

    except ConnectionResetError:
        print(f"[CENTRAL] Conexión con {cp_id} perdida inesperadamente (Reset).")
    except Exception as e:
        print(f"[CENTRAL] Error en bucle de cliente {cp_id}: {e}")
    finally:
        if cp_id != "Desconocido":
            registrar_evento(f"Monitor desconectado: {cp_id}")
            
            # Verificar si hay un suministro activo antes de desconectar
            with TELEMETRIA_ACTUAL_LOCK:
                telemetria_actual = TELEMETRIA_ACTUAL.get(cp_id, {})
            estado_telemetria = telemetria_actual.get('estado', '').upper()
            tiene_sesion_activa = telemetria_actual.get('tiene_sesion_activa', False)
            
            # Si hay suministro activo, finalizarlo y enviar ticket al driver
            if tiene_sesion_activa or estado_telemetria in ('SUMINISTRANDO', 'CARGANDO'):
                print(f"[CENTRAL] ⚠️ Monitor de {cp_id} desconectado inesperadamente durante suministro activo. Finalizando suministro...")
                
                # Obtener información del driver y energía suministrada
                with CP_SESION_DRIVER_ID_LOCK:
                    driver_id = CP_SESION_DRIVER_ID.get(cp_id)
                
                if driver_id and driver_id != 'UNKNOWN':
                    # Calcular energía entregada desde telemetría
                    energia = (
                        telemetria_actual.get('energia_total')
                        if 'energia_total' in telemetria_actual
                        else telemetria_actual.get('kw_entregados', 0.0)
                    )
                    try:
                        energia_val = float(energia)
                    except Exception:
                        energia_val = 0.0
                    
                    # Calcular duración
                    tiempo_carga_s = telemetria_actual.get('tiempo_carga_s', 0)
                    try:
                        duracion_seg = int(tiempo_carga_s)
                    except Exception:
                        duracion_seg = 0
                    
                    # Calcular importe usando precio del CP
                    with CP_PRECIO_KWH_LOCK:
                        precio_kwh = CP_PRECIO_KWH.get(cp_id, 0.48)
                    try:
                        precio_val = float(precio_kwh)
                    except Exception:
                        precio_val = 0.48
                    
                    importe = round(energia_val * precio_val, 2)
                    
                    # Generar tx_id
                    tx_id = f"TX-{cp_id}-{int(time.time())}"
                    
                    # Crear ticket
                    detalle_ticket = {
                        'cp_id': cp_id,
                        'energia_kwh': energia_val,
                        'importe_eur': importe,
                        'duracion_seg': duracion_seg,
                        'motivo': 'Monitor desconectado - suministro finalizado',
                        'tx_id': tx_id
                    }
                    
                    # Enviar ticket al driver
                    notificar_driver(driver_id, 'TICKET_FINAL', detalle_ticket)
                    registrar_evento(f"✅ Ticket enviado a {driver_id} por desconexión inesperada de Monitor en {cp_id}: {energia_val} kWh, {importe} €", "ok")
                    print(f"[CENTRAL] ✅ Ticket enviado a {driver_id} por desconexión inesperada de Monitor. Energía: {energia_val} kWh, Importe: {importe} €")
                    
                    # Limpiar sesión
                    with CP_SESION_DRIVER_ID_LOCK:
                        if cp_id in CP_SESION_DRIVER_ID:
                            del CP_SESION_DRIVER_ID[cp_id]
                    with CP_SESION_OBJETIVO_KWH_LOCK:
                        if cp_id in CP_SESION_OBJETIVO_KWH:
                            del CP_SESION_OBJETIVO_KWH[cp_id]
                    
                    # Resetear telemetría de sesión
                    telemetria_actual['tiene_sesion_activa'] = False
                    telemetria_actual['driver_id_sesion'] = None
                    telemetria_actual['kw_entregados'] = 0.0
                    telemetria_actual['energia_total'] = 0.0
                    telemetria_actual['tiempo_carga_s'] = 0
                    
                    registrar_evento(f"🛑 Suministro finalizado en {cp_id} debido a desconexión inesperada del Monitor", "warn")
            
            # Marcar el CP como DESCONECTADO (no AVERIADO, porque es el Monitor quien se desconectó, no el Engine)
            if _verificar_conexion(db_connection):
                actualizar_estado_cp(db_connection, cp_id, "Desconectado")
            try:
                cambiar_estado_cp(cp_id, 'DESCONECTADO', db_connection, motivo='Desconexión inesperada del Monitor')
            except Exception:
                pass
            
            # Publicar telemetría actualizada
            telemetria_actualizada = {
                **telemetria_actual,
                'cp_id': cp_id,
                'estado': 'DESCONECTADO',
                'estado_carga': 'DESCONECTADO',
                'timestamp': time.time()
            }
            with TELEMETRIA_ACTUAL_LOCK:
                TELEMETRIA_ACTUAL[cp_id] = telemetria_actualizada
            if KAFKA_PRODUCER:
                try:
                    KAFKA_PRODUCER.send(TELEMETRIA_TOPIC, value=telemetria_actualizada)
                    KAFKA_PRODUCER.flush(timeout=1)
                    print(f"[CENTRAL] ✓ Telemetría DESCONECTADO publicada para {cp_id}")
                except Exception:
                    pass
        
        if cp_id in CONEXIONES_ACTIVAS:
            with CONEXIONES_ACTIVAS_LOCK:
                del CONEXIONES_ACTIVAS[cp_id]
                print(f"[CENTRAL] Socket de {cp_id} eliminado. Total: {len(CONEXIONES_ACTIVAS)}")
        
        # ====== OPCIONAL: MARCAR CP PARA RECONEXIÓN ======
        if cp_id != "Desconocido":
            registrar_evento(f"[INFO] {cp_id} podrá reconectarse automáticamente al reiniciar su Monitor.")
        
        conn.close()
        print(f"[CENTRAL] Hilo de conexión con {addr[0]}:{addr[1]} finalizado.")

def cambiar_estado_cp(cp_id: str, nuevo_estado: str, db_connection = None, motivo: str | None = None) -> None:
    """Actualiza el estado interno y la BD, y registra en el log/TUI.
    Estados esperados: DESCONECTADO, ACTIVADO, PRE-SUMINISTRO, SUMINISTRANDO, PARADO, AVERÍA.
    """
    nuevo_estado_norm = nuevo_estado.strip().upper() if isinstance(nuevo_estado, str) else str(nuevo_estado)
    with CP_ESTADO_LOCK, CP_ALERTA_LOCK:
        anterior = CP_ESTADO.get(cp_id)
        # Regla: si está en AVERÍA, no permitir cambios a estados distintos de AVERÍA, salvo recuperación explícita
        if anterior and anterior.upper() in ['AVERÍA', 'AVERIA'] and nuevo_estado_norm not in ['AVERÍA', 'AVERIA']:
            # Permitir solo si la alerta ha sido limpiada (AVR_CLR ya gestionó CP_ALERTA=False)
            alerta = CP_ALERTA.get(cp_id, False)
            if alerta:
                # Ignorar cambio mientras persista avería
                registrar_evento(f"[IGNORADO] {cp_id}: en AVERÍA → se ignora cambio a {nuevo_estado_norm}")
                return
        CP_ESTADO[cp_id] = nuevo_estado_norm
    detalle = f" (antes: {anterior})" if anterior and anterior != nuevo_estado_norm else ""
    extra = f" Motivo: {motivo}" if motivo else ""
    registrar_evento(f"[ESTADO] {cp_id} -> {nuevo_estado_norm}{detalle}.{extra}")
    # Persistir en BD si está disponible
    try:
        if _verificar_conexion(db_connection):
            # Mapear a nombres en BD (usar Title case como en funciones existentes)
            mapa_bd = {
                'DESCONECTADO': 'Desconectado',
                'ACTIVADO': 'Activado',
                'PRE-SUMINISTRO': 'Pre-Suministro',
                'PENDIENTE_CONFIRMACION_CENTRAL': 'Pendiente Confirmacion Central',
                'ESPERANDO_OPERADOR_ENGINE': 'Esperando Operador Engine',
                'LISTO_PARA_INICIAR': 'Listo Para Iniciar',
                'SUMINISTRANDO': 'Suministrando',
                'CARGANDO': 'Suministrando',
                'ESPERANDO_CONFIRMACION_FIN': 'Esperando Confirmacion Fin',
                'PARADO': 'Parado',
                'AVERÍA': 'Averiado',
                'AVERIA': 'Averiado',
                'FUERA_DE_SERVICIO': 'Fuera De Servicio',
            }
            estado_bd = mapa_bd.get(nuevo_estado_norm, nuevo_estado_norm.title())
            actualizar_estado_cp(db_connection, cp_id, estado_bd)
    except Exception as e:
        print(f"[CENTRAL] No se pudo persistir estado de {cp_id}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Proceso EV_Central")
    parser.add_argument("--port", type=int, required=True, help="Puerto de escucha")
    parser.add_argument("--kafka", type=str, required=True, help="Broker Kafka (IP:puerto)")
    parser.add_argument("--db", type=str, help="Ruta/URL de la base de datos")
    parser.add_argument("--no-tui", action="store_true", help="Desactiva la TUI y usa modo consola simple")
    args = parser.parse_args()

    print("="*40)
    print("[EV_Central] INICIADO")
    print(f"Puerto de escucha: {args.port}")
    print(f"Broker Kafka: {args.kafka}")
    print(f"Base de datos: {args.db if args.db else 'Ninguna'}")
    print("="*40)
    print("Comandos disponibles:")
    print("  1 -> Refrescar estado")
    print("  2 START CP001  o  2 STOP CP001 -> Enviar orden al CP")
    print("  EXIT CONFIRM -> Cerrar el sistema (requiere confirmación)")

    # Inicialización de la base de datos
    db_connection = None
    if args.db:
        try:
            db_connection = conectar_bd(args.db)
            print("[EV_Central] Base de datos conectada correctamente")
        except Exception as e:
            print(f"[EV_Central] ADVERTENCIA: No se pudo conectar a BD: {e}")
            print("[EV_Central] NOTA: El sistema funcionará sin persistencia de datos.")
            print("[EV_Central] Las funcionalidades básicas (comunicación con CPs, Kafka) seguirán funcionando.")
            print("[EV_Central] Las claves de cifrado se guardarán en archivo local como respaldo.")
            print("[EV_Central] Continuando sin persistencia de datos...")
            db_connection = None
            # Cargar claves desde archivo si BD no está disponible
            _inicializar_claves_desde_archivo()
    else:
        print("[EV_Central] ADVERTENCIA: No se proporcionó configuración de BD")
        print("[EV_Central] Continuando sin persistencia de datos...")
        # Cargar claves desde archivo si no hay BD
        _inicializar_claves_desde_archivo()

    # Hacer accesible la conexión BD y configuración para el consumidor de telemetría (histórico)
    globals()['_DB_CONN_FOR_CONSUMER'] = db_connection
    globals()['DB_CONFIG_STR'] = args.db

    # Al iniciar, marcar todos los CPs en BD como Desconectado
    # Solo se marcarán como activos cuando se reconecten
    try:
        if _verificar_conexion(db_connection):
            cursor = db_connection.cursor()
            # Marcar todos los CPs como desconectados (inicio limpio)
            cursor.execute("UPDATE charging_points SET estado = 'Desconectado'")
            db_connection.commit()
            num_cps = cursor.rowcount
            if num_cps > 0:
                registrar_evento(f"[INICIO] {num_cps} CP(s) marcados como Desconectado. Esperando conexiones...", "info")
            cursor.close()
    except Exception as e:
        registrar_evento(f"[ERROR] No se pudo inicializar estado de CPs: {e}", "error")

    # Inicialización del productor Kafka para notificaciones
    inicializar_kafka_producer(args.kafka)

    # Inicialización del servidor de Sockets
    try:
        # Iniciar API REST en hilo separado (puerto 5001 por defecto, o siguiente al socket)
        api_port = int(os.getenv('API_PORT', args.port + 1))
        api_thread = threading.Thread(
            target=iniciar_api_rest,
            args=(api_port, db_connection),
            daemon=True
        )
        api_thread.start()
        print(f"[CENTRAL] ✓ API REST iniciada en puerto {api_port}")
        
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Permite reutilizar el puerto

        server_socket.bind(('', args.port)) 
        server_socket.listen(5)
        # Timeout corto para aceptar conexiones y poder revisar el flag de apagado
        server_socket.settimeout(1.0)
        
        # Forzar modo consola simple siempre (compat) y lanzar TUI Rich
        console_input_thread = threading.Thread(target=interfaz_consola_central, daemon=True)
        console_input_thread.start()
        tui_thread = threading.Thread(target=iniciar_interfaz_visual, daemon=True)
        tui_thread.start()

        # Hilo de procesamiento de comandos (común a ambos modos)
        cmd_thread = threading.Thread(target=bucle_procesador_comandos, daemon=True)
        cmd_thread.start()

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
        # Hilo consumidor de Kafka para comandos de control desde web
        control_commands_thread = threading.Thread(
            target=consumir_comandos_control_kafka,
            args=(args.kafka,),
            daemon=True
        )
        control_commands_thread.start()
        # Lanzar monitor de actividad (heartbeat)
        threading.Thread(target=monitorizar_actividad_cps, args=(db_connection,), daemon=True).start()
        print(f"[EV_Central] Servidor escuchando en TCP (:{args.port})...")

        # Bucle principal con manejo robusto de errores
        while True:
            try:
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
                except Exception as e:
                    print(f"[EV_Central] Error aceptando conexión: {e}")
                    import traceback
                    traceback.print_exc()
                    time.sleep(1)  # Esperar un poco antes de reintentar
                    continue
                
                # Iniciar un nuevo hilo para manejar la conexión de forma concurrente
                try:
                    client_thread = threading.Thread(target=manejar_cliente, args=(conn, addr, db_connection))
                    client_thread.start()
                    with CLIENT_THREADS_LOCK:
                        CLIENT_THREADS.append(client_thread)
                except Exception as e:
                    print(f"[EV_Central] Error iniciando hilo de cliente: {e}")
                    import traceback
                    traceback.print_exc()
                    try:
                        conn.close()
                    except:
                        pass
                    continue
            except KeyboardInterrupt:
                print("\n[EV_Central] Apagando por interrupción de usuario...")
                break
            except Exception as e:
                print("\n" + "="*60)
                print("[EV_Central] ERROR en bucle principal:")
                print("="*60)
                print(f"Error: {e}")
                import traceback
                traceback.print_exc()
                print("="*60)
                # Continuar el bucle en lugar de terminar
                time.sleep(1)  # Esperar un poco antes de reintentar
                continue

    
    except KeyboardInterrupt:
        print("\n[EV_Central] Apagando por interrupción de usuario...")
    except Exception as e:
        print("\n" + "="*60)
        print("[EV_Central] ERROR CRÍTICO - La aplicación se cerrará:")
        print("="*60)
        print(f"Error: {e}")
        print("\nTraceback completo:")
        import traceback
        traceback.print_exc()
        print("="*60)
    finally:
        try:
            # Cerrar todas las conexiones activas
            print("[EV_Central] Cerrando todas las conexiones activas...")
            with CONEXIONES_ACTIVAS_LOCK:
                for cp_id, conn in CONEXIONES_ACTIVAS.items():
                    try:
                        conn.close()
                        print(f"[EV_Central] Conexión con {cp_id} cerrada.")
                    except Exception as e:
                        print(f"[EV_Central] Error cerrando conexión con {cp_id}: {e}")
            CONEXIONES_ACTIVAS.clear()
            registrar_evento("Central cerrando...")
            # Esperar a que terminen los hilos de clientes (con timeout)
            with CLIENT_THREADS_LOCK:
                for t in CLIENT_THREADS:
                    try:
                        t.join(timeout=2.0)
                    except Exception as e:
                        print(f"[EV_Central] Error esperando hilo de cliente: {e}")
                CLIENT_THREADS.clear()
            
            # Cerrar el servidor socket
            if 'server_socket' in locals():
                try:
                    server_socket.close()
                    print("[EV_Central] Servidor socket cerrado.")
                except Exception as e:
                    print(f"[EV_Central] Error cerrando servidor socket: {e}")
            
            # Cerrar conexión a BD
            if _verificar_conexion(db_connection):
                try:
                    db_connection.close()
                    print("[EV_Central] Conexión a BD cerrada.")
                except Exception as e:
                    print(f"[EV_Central] Error cerrando conexión a BD: {e}")
            
            print("[EV_Central] Apagado completado.")
        except Exception as e:
            print("\n" + "="*60)
            print("[EV_Central] ERROR durante el cierre de la aplicación:")
            print("="*60)
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            print("="*60)

if __name__ == "__main__":
    main()