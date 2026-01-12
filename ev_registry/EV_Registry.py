#!/usr/bin/env python3
"""
EV_Registry - Módulo de Registro de Puntos de Carga
Permite registrar, dar de baja y autenticar CPs en el sistema.

Uso:
    python EV_Registry.py --db-host 127.0.0.1 --db-port 3306 --db-user root --db-password root --db-name evcharging --port 6000
"""

try:
    import pymysql
    import pymysql.cursors
    from pymysql import Error
    PYMySQL_AVAILABLE = True
    MySQLCursorDict = None  # No se usa con PyMySQL
except ImportError:
    import mysql.connector
    from mysql.connector import Error
    try:
        from mysql.connector.cursor import MySQLCursorDict
    except ImportError:
        # Fallback para versiones antiguas de mysql.connector
        from mysql.connector.cursor import MySQLCursor
        MySQLCursorDict = MySQLCursor
    PYMySQL_AVAILABLE = False
import argparse
import hashlib
import secrets
import threading
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
import ssl
import os
import json

# =================================================================
#                    CONFIGURACIÓN GLOBAL
# =================================================================

app = Flask(__name__)
CORS(app)

# Configuración de base de datos
DB_CONFIG = {}

# Puerto del servidor
REGISTRY_PORT = 6000

# Archivos para fallback cuando BD no está disponible
REGISTRY_DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
REGISTRY_CP_FILE = os.path.join(REGISTRY_DATA_DIR, 'cp_registry.json')
REGISTRY_CREDS_FILE = os.path.join(REGISTRY_DATA_DIR, 'cp_credentials.json')

# Flag para indicar si BD está disponible
BD_DISPONIBLE = False

# API Key compartida para autenticación de aplicaciones externas (Monitores)
# Se puede configurar mediante variable de entorno REGISTRY_API_KEY
# Por defecto, usa una clave predefinida (en producción debería ser más segura)
SHARED_API_KEY = os.getenv('REGISTRY_API_KEY', 'ev-registry-api-key-2024-secure')

# =================================================================
#                    MIDDLEWARE DE AUTENTICACIÓN
# =================================================================

def require_api_key(f):
    """
    Decorador que valida el header X-API-Key en las peticiones.
    Protege los endpoints de registro y baja de peticiones no autorizadas.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            return jsonify({
                'status': 'error',
                'message': 'X-API-Key header requerido'
            }), 401
        
        if api_key != SHARED_API_KEY:
            print(f"[EV_Registry] ❌ Intento de acceso no autorizado con API key inválida")
            return jsonify({
                'status': 'error',
                'message': 'API key inválida'
            }), 401
        
        return f(*args, **kwargs)
    
    return decorated_function

# =================================================================
#                    FUNCIONES DE BASE DE DATOS
# =================================================================

def obtener_conexion_bd():
    """Obtiene una conexión a la base de datos."""
    global BD_DISPONIBLE
    try:
        if PYMySQL_AVAILABLE:
            # Usar PyMySQL (más compatible con MySQL 8)
            connection = pymysql.connect(
                host=DB_CONFIG['host'],
                port=DB_CONFIG['port'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                database=DB_CONFIG['database'],
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True,
                connect_timeout=10
            )
        else:
            # Fallback a mysql.connector
            connection = mysql.connector.connect(
                host=DB_CONFIG['host'],
                port=DB_CONFIG['port'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                database=DB_CONFIG['database'],
                charset='utf8mb4',
                collation='utf8mb4_general_ci',
                use_unicode=True,
                ssl_disabled=True
            )
        BD_DISPONIBLE = True
        return connection
    except Error as e:
        print(f"[EV_Registry] ⚠️ Error conectando a BD: {e}")
        print(f"[EV_Registry] Usando almacenamiento en archivos locales como fallback")
        BD_DISPONIBLE = False
        return None
    except Exception as e:
        print(f"[EV_Registry] ⚠️ Error inesperado conectando a BD: {e}")
        print(f"[EV_Registry] Usando almacenamiento en archivos locales como fallback")
        BD_DISPONIBLE = False
        return None

def obtener_cursor_dict(connection):
    """Obtiene un cursor que devuelve resultados como diccionarios.
    Compatible con pymysql y mysql.connector."""
    if PYMySQL_AVAILABLE:
        # PyMySQL ya está configurado con DictCursor en la conexión
        return connection.cursor()
    else:
        # mysql.connector: usar dictionary=True directamente
        return connection.cursor(dictionary=True)

# =================================================================
#                    FUNCIONES DE FALLBACK (ARCHIVOS)
# =================================================================

def _cargar_registros_desde_archivo() -> dict:
    """Carga los registros de CPs desde archivo JSON."""
    try:
        os.makedirs(REGISTRY_DATA_DIR, exist_ok=True)
        if os.path.exists(REGISTRY_CP_FILE):
            with open(REGISTRY_CP_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"[EV_Registry] ⚠️ Error cargando registros desde archivo: {e}")
    return {}

def _guardar_registros_en_archivo(registros: dict):
    """Guarda los registros de CPs en archivo JSON."""
    try:
        os.makedirs(REGISTRY_DATA_DIR, exist_ok=True)
        with open(REGISTRY_CP_FILE, 'w', encoding='utf-8') as f:
            json.dump(registros, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[EV_Registry] ⚠️ Error guardando registros en archivo: {e}")

def _cargar_credenciales_desde_archivo() -> dict:
    """Carga las credenciales desde archivo JSON."""
    try:
        os.makedirs(REGISTRY_DATA_DIR, exist_ok=True)
        if os.path.exists(REGISTRY_CREDS_FILE):
            with open(REGISTRY_CREDS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"[EV_Registry] ⚠️ Error cargando credenciales desde archivo: {e}")
    return {}

def _guardar_credenciales_en_archivo(credenciales: dict):
    """Guarda las credenciales en archivo JSON."""
    try:
        os.makedirs(REGISTRY_DATA_DIR, exist_ok=True)
        with open(REGISTRY_CREDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(credenciales, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[EV_Registry] ⚠️ Error guardando credenciales en archivo: {e}")

def _registrar_cp_archivo(cp_id: str, ubicacion: str):
    """Registra un CP usando archivos (fallback cuando BD no está disponible)."""
    registros = _cargar_registros_desde_archivo()
    credenciales = _cargar_credenciales_desde_archivo()
    
    ahora = datetime.now().isoformat()
    
    if cp_id in registros:
        if registros[cp_id].get('activo', True):
            # CP ya registrado: regenerar credenciales
            username, password = generar_credenciales()
            password_hash, salt = generar_password_hash(password)
            
            registros[cp_id]['ubicacion'] = ubicacion
            registros[cp_id]['fecha_ultima_actualizacion'] = ahora
            
            credenciales[cp_id] = {
                'username': username,
                'password_hash': password_hash,
                'salt': salt,
                'activo': True,
                'fecha_creacion': ahora,
                'fecha_ultima_actualizacion': ahora
            }
            
            _guardar_registros_en_archivo(registros)
            _guardar_credenciales_en_archivo(credenciales)
            
            print(f"[EV_Registry] ✓ Credenciales regeneradas para CP {cp_id} (archivo)")
            return jsonify({
                'status': 'ok',
                'cp_id': cp_id,
                'username': username,
                'password': password,
                'message': f'CP {cp_id} ya registrado. Credenciales regeneradas.'
            }), 200
        else:
            # Reactivar CP
            registros[cp_id]['activo'] = True
            registros[cp_id]['ubicacion'] = ubicacion
            registros[cp_id]['fecha_ultima_actualizacion'] = ahora
            
            username, password = generar_credenciales()
            password_hash, salt = generar_password_hash(password)
            
            credenciales[cp_id] = {
                'username': username,
                'password_hash': password_hash,
                'salt': salt,
                'activo': True,
                'fecha_creacion': ahora,
                'fecha_ultima_actualizacion': ahora
            }
            
            _guardar_registros_en_archivo(registros)
            _guardar_credenciales_en_archivo(credenciales)
            
            print(f"[EV_Registry] ✓ CP {cp_id} reactivado (archivo)")
            return jsonify({
                'status': 'ok',
                'cp_id': cp_id,
                'username': username,
                'password': password,
                'message': f'CP {cp_id} reactivado y credenciales generadas'
            }), 200
    
    # Nuevo CP
    registros[cp_id] = {
        'cp_id': cp_id,
        'ubicacion': ubicacion,
        'fecha_registro': ahora,
        'fecha_ultima_actualizacion': ahora,
        'activo': True
    }
    
    username, password = generar_credenciales()
    password_hash, salt = generar_password_hash(password)
    
    credenciales[cp_id] = {
        'username': username,
        'password_hash': password_hash,
        'salt': salt,
        'activo': True,
        'fecha_creacion': ahora,
        'fecha_ultima_actualizacion': ahora
    }
    
    _guardar_registros_en_archivo(registros)
    _guardar_credenciales_en_archivo(credenciales)
    
    print(f"[EV_Registry] ✓ CP {cp_id} registrado correctamente (archivo)")
    return jsonify({
        'status': 'ok',
        'cp_id': cp_id,
        'username': username,
        'password': password,
        'message': f'CP {cp_id} registrado correctamente'
    }), 201

def _dar_baja_cp_archivo(cp_id: str):
    """Da de baja un CP usando archivos (fallback cuando BD no está disponible)."""
    registros = _cargar_registros_desde_archivo()
    credenciales = _cargar_credenciales_desde_archivo()
    
    if cp_id not in registros:
        return jsonify({
            'status': 'error',
            'message': f'CP {cp_id} no encontrado'
        }), 404
    
    registros[cp_id]['activo'] = False
    registros[cp_id]['fecha_ultima_actualizacion'] = datetime.now().isoformat()
    
    if cp_id in credenciales:
        credenciales[cp_id]['activo'] = False
        credenciales[cp_id]['fecha_ultima_actualizacion'] = datetime.now().isoformat()
    
    _guardar_registros_en_archivo(registros)
    _guardar_credenciales_en_archivo(credenciales)
    
    print(f"[EV_Registry] ✓ CP {cp_id} dado de baja (archivo)")
    return jsonify({
        'status': 'ok',
        'cp_id': cp_id,
        'message': f'CP {cp_id} dado de baja correctamente'
    }), 200

def _autenticar_cp_archivo(cp_id: str, username: str, password: str):
    """Autentica un CP usando archivos (fallback cuando BD no está disponible)."""
    registros = _cargar_registros_desde_archivo()
    credenciales = _cargar_credenciales_desde_archivo()
    
    if cp_id not in registros or not registros[cp_id].get('activo', False):
        return jsonify({
            'status': 'error',
            'message': f'CP {cp_id} no registrado o inactivo'
        }), 401
    
    if cp_id not in credenciales or not credenciales[cp_id].get('activo', False):
        return jsonify({
            'status': 'error',
            'message': f'CP {cp_id} no tiene credenciales activas'
        }), 401
    
    cred = credenciales[cp_id]
    if cred['username'] != username:
        return jsonify({
            'status': 'error',
            'message': 'Credenciales inválidas'
        }), 401
    
    if not verificar_password(password, cred['password_hash'], cred['salt']):
        return jsonify({
            'status': 'error',
            'message': 'Credenciales inválidas'
        }), 401
    
    print(f"[EV_Registry] ✓ CP {cp_id} autenticado correctamente (archivo)")
    return jsonify({
        'status': 'ok',
        'cp_id': cp_id,
        'message': 'Autenticación exitosa'
    }), 200

def limpiar_base_datos():
    """Limpia todas las tablas de CPs y credenciales."""
    connection = obtener_conexion_bd()
    if not connection:
        print("[EV_Registry] ⚠️ No se pudo conectar a BD para limpiar datos")
        return False
    
    try:
        cursor = connection.cursor()
        
        # Eliminar todos los registros de credenciales
        cursor.execute("DELETE FROM cp_credentials")
        
        # Eliminar todos los registros de CPs
        cursor.execute("DELETE FROM cp_registry")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        print("[EV_Registry] ✓ Base de datos limpiada correctamente")
        return True
    except Error as e:
        if connection:
            connection.rollback()
            connection.close()
        print(f"[EV_Registry] ⚠️ Error limpiando BD: {e}")
        return False
    except Exception as e:
        if connection:
            connection.close()
        print(f"[EV_Registry] ⚠️ Error inesperado limpiando BD: {e}")
        return False

def inicializar_tablas():
    """Inicializa las tablas necesarias en la base de datos."""
    connection = obtener_conexion_bd()
    if not connection:
        print("[EV_Registry] ❌ No se pudo conectar a BD para inicializar tablas")
        return False
    
    try:
        cursor = connection.cursor()
        
        # Tabla de registro de CPs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cp_registry (
                id INT AUTO_INCREMENT PRIMARY KEY,
                cp_id VARCHAR(50) UNIQUE NOT NULL,
                ubicacion VARCHAR(255),
                fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
                fecha_ultima_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                activo BOOLEAN DEFAULT TRUE,
                INDEX idx_cp_id (cp_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        
        # Tabla de credenciales de autenticación
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cp_credentials (
                id INT AUTO_INCREMENT PRIMARY KEY,
                cp_id VARCHAR(50) UNIQUE NOT NULL,
                username VARCHAR(100) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                salt VARCHAR(255) NOT NULL,
                fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
                fecha_ultima_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                activo BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (cp_id) REFERENCES cp_registry(cp_id) ON DELETE CASCADE,
                INDEX idx_cp_id (cp_id),
                INDEX idx_username (username)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        
        # Agregar columna salt si no existe (para migración)
        try:
            cursor.execute("ALTER TABLE cp_credentials ADD COLUMN salt VARCHAR(255) NOT NULL DEFAULT ''")
        except Error:
            # La columna ya existe, ignorar
            pass
        
        connection.commit()
        cursor.close()
        connection.close()
        
        print("[EV_Registry] ✓ Tablas inicializadas correctamente")
        return True
        
    except Error as e:
        print(f"[EV_Registry] ❌ Error inicializando tablas: {e}")
        if connection:
            connection.close()
        return False

# =================================================================
#                    FUNCIONES DE SEGURIDAD
# =================================================================

def generar_password_hash(password: str, salt: str = None) -> tuple:
    """
    Genera un hash seguro de una contraseña usando SHA-256 con salt.
    
    Returns:
        (hash_hex, salt)
    """
    if salt is None:
        salt = secrets.token_hex(16)
    
    # Combinar password + salt y generar hash
    combined = f"{password}{salt}".encode('utf-8')
    hash_obj = hashlib.sha256(combined)
    hash_hex = hash_obj.hexdigest()
    
    return hash_hex, salt

def verificar_password(password: str, hash_almacenado: str, salt: str) -> bool:
    """Verifica si una contraseña coincide con el hash almacenado."""
    hash_calculado, _ = generar_password_hash(password, salt)
    return hash_calculado == hash_almacenado

def generar_credenciales() -> tuple:
    """
    Genera credenciales únicas para un CP.
    
    Returns:
        (username, password)
    """
    username = f"CP_{secrets.token_urlsafe(16)}"
    password = secrets.token_urlsafe(24)
    return username, password

# =================================================================
#                    API REST - REGISTRO DE CPs
# =================================================================

@app.route('/api/register', methods=['POST'])
@require_api_key
def registrar_cp():
    """
    Registra un nuevo CP en el sistema.
    
    Body JSON:
        {
            "cp_id": "CP001",
            "ubicacion": "C/Mayor, 45, Madrid"
        }
    
    Returns:
        {
            "status": "ok",
            "cp_id": "CP001",
            "username": "...",
            "password": "...",
            "message": "CP registrado correctamente"
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
        ubicacion = data.get('ubicacion', '')
        
        if not cp_id:
            return jsonify({
                'status': 'error',
                'message': 'cp_id es requerido'
            }), 400
        
        # Verificar si el CP ya está registrado
        connection = obtener_conexion_bd()
        
        # Si no hay BD, usar archivos
        if not connection and not BD_DISPONIBLE:
            return _registrar_cp_archivo(cp_id, ubicacion)
        
        try:
            cursor = obtener_cursor_dict(connection)
            
            # Verificar si existe
            cursor.execute("SELECT * FROM cp_registry WHERE cp_id = %s", (cp_id,))
            existente = cursor.fetchone()
            
            if existente:
                if existente['activo']:
                    # CP ya registrado y activo: regenerar credenciales y devolverlas
                    # Esto permite que un CP que se reinicie pueda obtener nuevas credenciales
                    print(f"[EV_Registry] CP {cp_id} ya registrado. Regenerando credenciales...")
                    
                    # Actualizar ubicación si se proporcionó una nueva
                    cursor.execute("""
                        UPDATE cp_registry 
                        SET ubicacion = %s, fecha_ultima_actualizacion = NOW()
                        WHERE cp_id = %s
                    """, (ubicacion, cp_id))
                    
                    # Generar nuevas credenciales
                    username, password = generar_credenciales()
                    password_hash, salt = generar_password_hash(password)
                    
                    cursor.execute("""
                        INSERT INTO cp_credentials (cp_id, username, password_hash, salt, activo)
                        VALUES (%s, %s, %s, %s, TRUE)
                        ON DUPLICATE KEY UPDATE
                            username = VALUES(username),
                            password_hash = VALUES(password_hash),
                            salt = VALUES(salt),
                            activo = TRUE,
                            fecha_ultima_actualizacion = NOW()
                    """, (cp_id, username, password_hash, salt))
                    
                    connection.commit()
                    cursor.close()
                    connection.close()
                    
                    print(f"[EV_Registry] ✓ Credenciales regeneradas para CP {cp_id}")
                    
                    return jsonify({
                        'status': 'ok',
                        'cp_id': cp_id,
                        'username': username,
                        'password': password,
                        'message': f'CP {cp_id} ya registrado. Credenciales regeneradas.'
                    }), 200
                else:
                    # Reactivar CP existente
                    cursor.execute("""
                        UPDATE cp_registry 
                        SET activo = TRUE, ubicacion = %s, fecha_ultima_actualizacion = NOW()
                        WHERE cp_id = %s
                    """, (ubicacion, cp_id))
                    
                    # Verificar si tiene credenciales
                    cursor.execute("SELECT * FROM cp_credentials WHERE cp_id = %s", (cp_id,))
                    creds = cursor.fetchone()
                    
                    if creds and creds['activo']:
                        # Usar credenciales existentes
                        username = creds['username']
                        # No devolver password, debe regenerarse
                        return jsonify({
                            'status': 'ok',
                            'cp_id': cp_id,
                            'message': f'CP {cp_id} reactivado. Use /api/regenerate_credentials para nuevas credenciales.',
                            'username': username
                        }), 200
                    else:
                        # Generar nuevas credenciales
                        username, password = generar_credenciales()
                        password_hash, salt = generar_password_hash(password)
                        
                        cursor.execute("""
                            INSERT INTO cp_credentials (cp_id, username, password_hash, salt, activo)
                            VALUES (%s, %s, %s, %s, TRUE)
                            ON DUPLICATE KEY UPDATE
                                username = VALUES(username),
                                password_hash = VALUES(password_hash),
                                salt = VALUES(salt),
                                activo = TRUE,
                                fecha_ultima_actualizacion = NOW()
                        """, (cp_id, username, password_hash, salt))
                        
                        connection.commit()
                        cursor.close()
                        connection.close()
                        
                        print(f"[EV_Registry] ✓ CP {cp_id} reactivado con nuevas credenciales")
                        return jsonify({
                            'status': 'ok',
                            'cp_id': cp_id,
                            'username': username,
                            'password': password,
                            'message': f'CP {cp_id} reactivado y credenciales generadas'
                        }), 200
            
            # Registrar nuevo CP
            cursor.execute("""
                INSERT INTO cp_registry (cp_id, ubicacion, activo)
                VALUES (%s, %s, TRUE)
            """, (cp_id, ubicacion))
            
            # Generar credenciales
            username, password = generar_credenciales()
            password_hash, salt = generar_password_hash(password)
            
            cursor.execute("""
                INSERT INTO cp_credentials (cp_id, username, password_hash, salt, activo)
                VALUES (%s, %s, %s, %s, TRUE)
            """, (cp_id, username, password_hash, salt))
            
            connection.commit()
            cursor.close()
            connection.close()
            
            print(f"[EV_Registry] ✓ CP {cp_id} registrado correctamente")
            
            return jsonify({
                'status': 'ok',
                'cp_id': cp_id,
                'username': username,
                'password': password,
                'message': f'CP {cp_id} registrado correctamente'
            }), 201
            
        except Error as e:
            if connection:
                connection.rollback()
                connection.close()
            print(f"[EV_Registry] ❌ Error en BD: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Error en base de datos: {str(e)}'
            }), 500
        
    except Exception as e:
        print(f"[EV_Registry] ❌ Error registrando CP: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': f'Error interno: {str(e)}'
        }), 500

# =================================================================
#                    ENDPOINTS SEGÚN GUÍA (Release 2)
# =================================================================

@app.route('/register/cp', methods=['POST', 'PUT'])
@require_api_key
def registrar_cp_guia():
    """
    Registra un nuevo CP en el sistema (endpoint según guía).
    Alias de /api/register para cumplir con la guía de implementación.
    """
    return registrar_cp()

@app.route('/register/cp/<cp_id>', methods=['DELETE'])
@require_api_key
def dar_baja_cp_guia(cp_id):
    """
    Da de baja un CP del sistema (endpoint según guía).
    Alias de /api/unregister/<cp_id> para cumplir con la guía de implementación.
    """
    return dar_baja_cp(cp_id)

@app.route('/register/cp/<cp_id>', methods=['GET'])
def consultar_cp(cp_id):
    """
    Consulta el estado/datos de un CP (opcional según guía).
    
    Returns:
        {
            "status": "ok",
            "cp_id": "CP001",
            "ubicacion": "...",
            "activo": true,
            "fecha_registro": "...",
            "username": "..."
        }
    """
    try:
        connection = obtener_conexion_bd()
        if not connection:
            return jsonify({
                'status': 'error',
                'message': 'Error de conexión a base de datos'
            }), 500
        
        try:
            cursor = obtener_cursor_dict(connection)
            
            # Obtener información del CP
            cursor.execute("""
                SELECT r.cp_id, r.ubicacion, r.fecha_registro, r.activo,
                       c.username, c.activo as credenciales_activas
                FROM cp_registry r
                LEFT JOIN cp_credentials c ON r.cp_id = c.cp_id
                WHERE r.cp_id = %s
            """, (cp_id,))
            
            cp_data = cursor.fetchone()
            cursor.close()
            connection.close()
            
            if not cp_data:
                return jsonify({
                    'status': 'error',
                    'message': f'CP {cp_id} no encontrado'
                }), 404
            
            return jsonify({
                'status': 'ok',
                'cp_id': cp_data['cp_id'],
                'ubicacion': cp_data['ubicacion'],
                'activo': bool(cp_data['activo']),
                'fecha_registro': cp_data['fecha_registro'].isoformat() if cp_data['fecha_registro'] else None,
                'username': cp_data['username'],
                'credenciales_activas': bool(cp_data['credenciales_activas'])
            }), 200
            
        except Error as e:
            if connection:
                connection.close()
            print(f"[EV_Registry] ❌ Error en BD: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Error en base de datos: {str(e)}'
            }), 500
        
    except Exception as e:
        print(f"[EV_Registry] ❌ Error consultando CP: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error interno: {str(e)}'
        }), 500

# =================================================================
#                    ENDPOINTS ORIGINALES (compatibilidad)
# =================================================================

@app.route('/api/unregister/<cp_id>', methods=['DELETE'])
@require_api_key
def dar_baja_cp(cp_id):
    """
    Da de baja un CP del sistema.
    
    Returns:
        {
            "status": "ok",
            "message": "CP dado de baja correctamente"
        }
    """
    # Si no hay BD, usar archivos
    connection = obtener_conexion_bd()
    if not connection and not BD_DISPONIBLE:
        return _dar_baja_cp_archivo(cp_id)
    
    try:
        if not connection:
            return jsonify({
                'status': 'error',
                'message': 'Error de conexión a base de datos'
            }), 500
        
        try:
            cursor = connection.cursor()
            
            # Verificar si existe
            cursor.execute("SELECT * FROM cp_registry WHERE cp_id = %s", (cp_id,))
            existente = cursor.fetchone()
            
            if not existente:
                cursor.close()
                connection.close()
                return jsonify({
                    'status': 'error',
                    'message': f'CP {cp_id} no encontrado'
                }), 404
            
            # Dar de baja (marcar como inactivo)
            cursor.execute("""
                UPDATE cp_registry 
                SET activo = FALSE, fecha_ultima_actualizacion = NOW()
                WHERE cp_id = %s
            """, (cp_id,))
            
            # También desactivar credenciales
            cursor.execute("""
                UPDATE cp_credentials 
                SET activo = FALSE, fecha_ultima_actualizacion = NOW()
                WHERE cp_id = %s
            """, (cp_id,))
            
            connection.commit()
            cursor.close()
            connection.close()
            
            print(f"[EV_Registry] ✓ CP {cp_id} dado de baja")
            
            return jsonify({
                'status': 'ok',
                'cp_id': cp_id,
                'message': f'CP {cp_id} dado de baja correctamente'
            }), 200
            
        except Error as e:
            if connection:
                connection.rollback()
                connection.close()
            print(f"[EV_Registry] ❌ Error en BD: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Error en base de datos: {str(e)}'
            }), 500
        
    except Exception as e:
        print(f"[EV_Registry] ❌ Error dando de baja CP: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error interno: {str(e)}'
        }), 500

@app.route('/api/authenticate', methods=['POST'])
def autenticar_cp():
    """
    Autentica un CP con sus credenciales.
    
    Body JSON:
        {
            "username": "...",
            "password": "..."
        }
    
    Returns:
        {
            "status": "ok",
            "cp_id": "CP001",
            "message": "Autenticación exitosa"
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No se proporcionó JSON en el body'
            }), 400
        
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({
                'status': 'error',
                'message': 'username y password son requeridos'
            }), 400
        
        connection = obtener_conexion_bd()
        
        # Si no hay BD, usar archivos
        if not connection and not BD_DISPONIBLE:
            # Buscar cp_id por username en archivos
            credenciales = _cargar_credenciales_desde_archivo()
            cp_id = None
            for cp, cred in credenciales.items():
                if cred.get('username') == username:
                    cp_id = cp
                    break
            
            if not cp_id:
                return jsonify({
                    'status': 'error',
                    'message': 'Credenciales inválidas'
                }), 401
            
            return _autenticar_cp_archivo(cp_id, username, password)
        
        if not connection:
            return jsonify({
                'status': 'error',
                'message': 'Error de conexión a base de datos'
            }), 500
        
        try:
            cursor = obtener_cursor_dict(connection)
            
            # Buscar credenciales
            cursor.execute("""
                SELECT c.*, r.activo as cp_activo
                FROM cp_credentials c
                JOIN cp_registry r ON c.cp_id = r.cp_id
                WHERE c.username = %s AND c.activo = TRUE
            """, (username,))
            
            creds = cursor.fetchone()
            
            if not creds:
                cursor.close()
                connection.close()
                print(f"[EV_Registry] ❌ Intento de autenticación fallido: usuario no encontrado")
                return jsonify({
                    'status': 'error',
                    'message': 'Credenciales inválidas'
                }), 401
            
            # Verificar que el CP esté activo
            if not creds['cp_activo']:
                cursor.close()
                connection.close()
                print(f"[EV_Registry] ❌ Intento de autenticación fallido: CP inactivo")
                return jsonify({
                    'status': 'error',
                    'message': 'CP dado de baja'
                }), 403
            
            # Obtener salt almacenado
            salt = creds.get('salt', '')
            
            if not salt:
                # Si no hay salt (registros antiguos), rechazar autenticación
                cursor.close()
                connection.close()
                print(f"[EV_Registry] ❌ Intento de autenticación fallido: credenciales sin salt (requiere regeneración)")
                return jsonify({
                    'status': 'error',
                    'message': 'Credenciales inválidas o requieren regeneración'
                }), 401
            
            # Verificar password con salt
            if verificar_password(password, creds['password_hash'], salt):
                cp_id = creds['cp_id']
                cursor.close()
                connection.close()
                
                print(f"[EV_Registry] ✓ Autenticación exitosa para {cp_id}")
                
                return jsonify({
                    'status': 'ok',
                    'cp_id': cp_id,
                    'message': 'Autenticación exitosa'
                }), 200
            else:
                cursor.close()
                connection.close()
                print(f"[EV_Registry] ❌ Intento de autenticación fallido: password incorrecto")
                return jsonify({
                    'status': 'error',
                    'message': 'Credenciales inválidas'
                }), 401
            
        except Error as e:
            if connection:
                connection.close()
            print(f"[EV_Registry] ❌ Error en BD: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Error en base de datos: {str(e)}'
            }), 500
        
    except Exception as e:
        print(f"[EV_Registry] ❌ Error autenticando CP: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error interno: {str(e)}'
        }), 500

@app.route('/api/cps', methods=['GET'])
def listar_cps():
    """Lista todos los CPs registrados."""
    try:
        connection = obtener_conexion_bd()
        if not connection:
            return jsonify({
                'status': 'error',
                'message': 'Error de conexión a base de datos'
            }), 500
        
        try:
            cursor = obtener_cursor_dict(connection)
            cursor.execute("""
                SELECT r.cp_id, r.ubicacion, r.fecha_registro, r.activo,
                       c.username, c.activo as credenciales_activas
                FROM cp_registry r
                LEFT JOIN cp_credentials c ON r.cp_id = c.cp_id
                ORDER BY r.fecha_registro DESC
            """)
            
            cps = cursor.fetchall()
            cursor.close()
            connection.close()
            
            return jsonify({
                'status': 'ok',
                'count': len(cps),
                'cps': cps
            }), 200
            
        except Error as e:
            if connection:
                connection.close()
            return jsonify({
                'status': 'error',
                'message': f'Error en base de datos: {str(e)}'
            }), 500
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error interno: {str(e)}'
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Endpoint de salud del servicio."""
    try:
        connection = obtener_conexion_bd()
        if connection:
            connection.close()
            return jsonify({
                'status': 'ok',
                'message': 'EV_Registry funcionando correctamente'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'No se pudo conectar a la base de datos'
            }), 503
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# =================================================================
#                    MAIN
# =================================================================

def main():
    global DB_CONFIG, REGISTRY_PORT
    
    parser = argparse.ArgumentParser(description="EV_Registry - Registro de Puntos de Carga")
    parser.add_argument("--db-host", type=str, default="127.0.0.1",
                        help="Host de la base de datos")
    parser.add_argument("--db-port", type=int, default=3306,
                        help="Puerto de la base de datos")
    parser.add_argument("--db-user", type=str, default="root",
                        help="Usuario de la base de datos")
    parser.add_argument("--db-password", type=str, default="root",
                        help="Contraseña de la base de datos")
    parser.add_argument("--db-name", type=str, default="evcharging",
                        help="Nombre de la base de datos")
    parser.add_argument("--port", type=int, default=6000,
                        help="Puerto del servidor (default: 6000)")
    parser.add_argument("--ssl", action='store_true',
                        help="Habilitar HTTPS (requiere certificados)")
    parser.add_argument("--ssl-cert", type=str, default="certificados/registry_cert.pem",
                        help="Ruta al archivo de certificado SSL (default: certificados/registry_cert.pem)")
    parser.add_argument("--ssl-key", type=str, default="certificados/registry_key.pem",
                        help="Ruta al archivo de clave privada SSL (default: certificados/registry_key.pem)")
    
    args = parser.parse_args()
    
    DB_CONFIG = {
        'host': args.db_host,
        'port': args.db_port,
        'user': args.db_user,
        'password': args.db_password,
        'database': args.db_name
    }
    REGISTRY_PORT = args.port
    
    print("="*70)
    print("  EV_Registry - Registro de Puntos de Carga")
    print("="*70)
    print(f"  BD: {args.db_host}:{args.db_port}/{args.db_name}")
    print(f"  Puerto: {REGISTRY_PORT}")
    print(f"  SSL: {'Habilitado' if args.ssl else 'Deshabilitado'}")
    print(f"  API Key: {SHARED_API_KEY[:20]}... (configurada)")
    print("="*70)
    print()
    
    # Inicializar tablas
    if not inicializar_tablas():
        print("[EV_Registry] ❌ Error inicializando tablas. Verifique la conexión a BD.")
        return
    
    # Limpiar base de datos al iniciar
    print("[EV_Registry] Limpiando base de datos...")
    limpiar_base_datos()
    
    # Iniciar hilo para mostrar terminal con listado de CPs
    def mostrar_listado_cps():
        """Muestra y actualiza periódicamente el listado de CPs registrados."""
        import time
        while True:
            try:
                connection = obtener_conexion_bd()
                if connection:
                    cursor = obtener_cursor_dict(connection)
                    cursor.execute("""
                        SELECT r.cp_id, r.ubicacion, r.fecha_registro, r.activo,
                               c.username, c.activo as credenciales_activas
                        FROM cp_registry r
                        LEFT JOIN cp_credentials c ON r.cp_id = c.cp_id
                        ORDER BY r.fecha_registro DESC
                    """)
                    cps = cursor.fetchall()
                    cursor.close()
                    connection.close()
                    
                    # Limpiar pantalla (Windows)
                    import os
                    os.system('cls' if os.name == 'nt' else 'clear')
                    
                    print("="*70)
                    print("  EV_Registry - Listado de Charging Points Registrados")
                    print("="*70)
                    print(f"  Total de CPs: {len(cps)}")
                    print(f"  Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    print("="*70)
                    print()
                    
                    if not cps:
                        print("  No hay CPs registrados aún.")
                    else:
                        print(f"{'CP ID':<12} {'Ubicación':<25} {'Estado':<12} {'Username':<30} {'Credenciales':<12}")
                        print("-"*70)
                        for cp in cps:
                            estado = "ACTIVO" if cp['activo'] else "INACTIVO"
                            creds_activas = "SÍ" if cp['credenciales_activas'] else "NO"
                            username = cp['username'] or "N/A"
                            ubicacion = (cp['ubicacion'] or "N/A")[:25]
                            print(f"{cp['cp_id']:<12} {ubicacion:<25} {estado:<12} {username[:30]:<30} {creds_activas:<12}")
                    
                    print()
                    print("="*70)
                    print("  Presiona Ctrl+C para salir")
                    print("="*70)
                else:
                    print("[EV_Registry] ⚠️ No se pudo conectar a BD para mostrar listado")
            except Exception as e:
                print(f"[EV_Registry] ⚠️ Error mostrando listado: {e}")
            
            time.sleep(5)  # Actualizar cada 5 segundos
    
    # Iniciar hilo para mostrar listado
    listado_thread = threading.Thread(target=mostrar_listado_cps, daemon=True)
    listado_thread.start()
    print("[EV_Registry] Terminal de listado de CPs iniciada (se actualiza cada 5 segundos)")
    
    # Iniciar servidor Flask
    print(f"[EV_Registry] Iniciando servidor en puerto {REGISTRY_PORT}...")
    
    if args.ssl:
        # Configurar SSL
        try:
            # Intentar usar PROTOCOL_TLS_SERVER (Python 3.7+)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        except AttributeError:
            # Fallback para versiones anteriores de Python
            try:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS)
            except AttributeError:
                context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        
        # Verificar que existen los archivos de certificado
        cert_path = args.ssl_cert
        key_path = args.ssl_key
        
        if not os.path.exists(cert_path):
            print(f"[EV_Registry] ❌ ERROR: No se encuentra el certificado: {cert_path}")
            print(f"[EV_Registry] Ejecuta generar_certificados_ssl.bat o generar_certificados_ssl.ps1 para generar certificados")
            return
        
        if not os.path.exists(key_path):
            print(f"[EV_Registry] ❌ ERROR: No se encuentra la clave privada: {key_path}")
            print(f"[EV_Registry] Ejecuta generar_certificados_ssl.bat o generar_certificados_ssl.ps1 para generar certificados")
            return
        
        # Verificar que los archivos no estén vacíos
        if os.path.getsize(cert_path) == 0:
            print(f"[EV_Registry] ❌ ERROR: El archivo de certificado está vacío: {cert_path}")
            return
        
        if os.path.getsize(key_path) == 0:
            print(f"[EV_Registry] ❌ ERROR: El archivo de clave privada está vacío: {key_path}")
            return
        
        try:
            # Cargar certificado y clave privada
            context.load_cert_chain(cert_path, key_path)
            
            # Configuraciones adicionales de seguridad
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE  # Para certificados autofirmados
            
            print(f"[EV_Registry] ✓ Certificados SSL cargados correctamente:")
            print(f"  - Certificado: {cert_path} ({os.path.getsize(cert_path)} bytes)")
            print(f"  - Clave privada: {key_path} ({os.path.getsize(key_path)} bytes)")
            print(f"[EV_Registry] Iniciando servidor HTTPS en puerto {REGISTRY_PORT}...")
            app.run(host='0.0.0.0', port=REGISTRY_PORT, ssl_context=context, debug=False, threaded=True)
        except ssl.SSLError as e:
            print(f"[EV_Registry] ❌ ERROR SSL: {e}")
            print(f"[EV_Registry] Verifica que los certificados sean válidos y estén en formato PEM")
            print(f"[EV_Registry] Puedes regenerarlos con: generar_certificados_ssl.bat")
            import traceback
            traceback.print_exc()
            return
        except Exception as e:
            print(f"[EV_Registry] ❌ ERROR cargando certificados SSL: {e}")
            print(f"[EV_Registry] Verifica que los archivos de certificado sean válidos")
            import traceback
            traceback.print_exc()
            return
    else:
        print("[EV_Registry] ⚠️ SSL deshabilitado. Usando HTTP (no seguro)")
        app.run(host='0.0.0.0', port=REGISTRY_PORT, debug=False, threaded=True)

if __name__ == "__main__":
    main()

