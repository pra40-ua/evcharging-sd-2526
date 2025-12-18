#!/usr/bin/env python3
"""
EV_Registry - Módulo de Registro de Puntos de Carga
Permite registrar, dar de baja y autenticar CPs en el sistema.

Uso:
    python EV_Registry.py --db-host 127.0.0.1 --db-port 3306 --db-user root --db-password root --db-name evcharging --port 8000
"""

import mysql.connector
from mysql.connector import Error
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

# =================================================================
#                    CONFIGURACIÓN GLOBAL
# =================================================================

app = Flask(__name__)
CORS(app)

# Configuración de base de datos
DB_CONFIG = {}

# Puerto del servidor
REGISTRY_PORT = 8000

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
            
            # Registrar auditoría de intento no autorizado
            registrar_auditoria(
                accion="ACCESO_NO_AUTORIZADO",
                cp_id=None,
                origen_ip=request.remote_addr,
                descripcion=f"Intento de acceso con API key inválida",
                resultado="DENEGADO"
            )
            
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
    try:
        connection = mysql.connector.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            ssl_disabled=True  # Deshabilitar SSL para evitar errores con Docker MySQL
        )
        return connection
    except Error as e:
        print(f"[EV_Registry] ❌ Error conectando a BD: {e}")
        return None

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
#                    FUNCIONES DE AUDITORÍA
# =================================================================

def registrar_auditoria(accion: str, cp_id: str = None, origen_ip: str = None, 
                        descripcion: str = None, resultado: str = "OK") -> None:
    """
    Registra un evento de auditoría en la base de datos.
    
    Args:
        accion: Tipo de acción (ej: "REGISTRO_CP", "BAJA_CP", "AUTENTICACION", etc.)
        cp_id: ID del CP (opcional)
        origen_ip: IP de origen (opcional)
        descripcion: Descripción detallada del evento
        resultado: Resultado de la acción ("OK", "ERROR", "DENEGADO", etc.)
    """
    try:
        connection = obtener_conexion_bd()
        if connection and connection.is_connected():
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO audit_log (fecha_hora, origen_ip, cp_id, accion, descripcion, resultado)
                VALUES (NOW(), %s, %s, %s, %s, %s)
            """, (origen_ip, cp_id, accion, descripcion, resultado))
            connection.commit()
            cursor.close()
            connection.close()
    except Exception as e:
        # No fallar si hay error en auditoría, solo log
        print(f"[EV_Registry] ⚠️ Error registrando auditoría: {e}")

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
        if not connection:
            return jsonify({
                'status': 'error',
                'message': 'Error de conexión a base de datos'
            }), 500
        
        try:
            cursor = connection.cursor(dictionary=True)
            
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
                    
                    # Registrar auditoría
                    registrar_auditoria(
                        accion="REGENERACION_CREDENCIALES",
                        cp_id=cp_id,
                        origen_ip=request.remote_addr,
                        descripcion=f"Credenciales regeneradas para CP {cp_id} ya registrado",
                        resultado="OK"
                    )
                    
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
                        
                        # Registrar auditoría
                        registrar_auditoria(
                            accion="REACTIVACION_CP",
                            cp_id=cp_id,
                            origen_ip=request.remote_addr,
                            descripcion=f"CP {cp_id} reactivado y credenciales generadas",
                            resultado="OK"
                        )
                        
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
            
            # Registrar auditoría
            registrar_auditoria(
                accion="REGISTRO_CP",
                cp_id=cp_id,
                origen_ip=request.remote_addr,
                descripcion=f"CP {cp_id} registrado correctamente. Ubicación: {ubicacion}",
                resultado="OK"
            )
            
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
            cursor = connection.cursor(dictionary=True)
            
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
    try:
        connection = obtener_conexion_bd()
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
            
            # Registrar auditoría
            registrar_auditoria(
                accion="BAJA_CP",
                cp_id=cp_id,
                origen_ip=request.remote_addr,
                descripcion=f"CP {cp_id} dado de baja correctamente",
                resultado="OK"
            )
            
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
        if not connection:
            return jsonify({
                'status': 'error',
                'message': 'Error de conexión a base de datos'
            }), 500
        
        try:
            cursor = connection.cursor(dictionary=True)
            
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
                
                # Registrar auditoría de intento fallido
                registrar_auditoria(
                    accion="AUTENTICACION",
                    cp_id=None,
                    origen_ip=request.remote_addr,
                    descripcion=f"Intento de autenticación fallido: usuario no encontrado (username: {username[:10]}...)",
                    resultado="DENEGADO"
                )
                
                return jsonify({
                    'status': 'error',
                    'message': 'Credenciales inválidas'
                }), 401
            
            # Verificar que el CP esté activo
            if not creds['cp_activo']:
                cursor.close()
                connection.close()
                print(f"[EV_Registry] ❌ Intento de autenticación fallido: CP inactivo")
                
                # Registrar auditoría de intento fallido
                registrar_auditoria(
                    accion="AUTENTICACION",
                    cp_id=creds.get('cp_id'),
                    origen_ip=request.remote_addr,
                    descripcion=f"Intento de autenticación fallido: CP inactivo (dado de baja)",
                    resultado="DENEGADO"
                )
                
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
                
                # Registrar auditoría
                registrar_auditoria(
                    accion="AUTENTICACION",
                    cp_id=cp_id,
                    origen_ip=request.remote_addr,
                    descripcion=f"Autenticación exitosa para CP {cp_id}",
                    resultado="OK"
                )
                
                return jsonify({
                    'status': 'ok',
                    'cp_id': cp_id,
                    'message': 'Autenticación exitosa'
                }), 200
            else:
                cursor.close()
                connection.close()
                print(f"[EV_Registry] ❌ Intento de autenticación fallido: password incorrecto")
                
                # Registrar auditoría de intento fallido
                registrar_auditoria(
                    accion="AUTENTICACION",
                    cp_id=creds.get('cp_id') if creds else None,
                    origen_ip=request.remote_addr,
                    descripcion=f"Intento de autenticación fallido: password incorrecto (username: {username[:10]}...)",
                    resultado="DENEGADO"
                )
                
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
            cursor = connection.cursor(dictionary=True)
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
    parser.add_argument("--db-host", type=str, default="192.168.1.43",
                        help="Host de la base de datos")
    parser.add_argument("--db-port", type=int, default=3306,
                        help="Puerto de la base de datos")
    parser.add_argument("--db-user", type=str, default="root",
                        help="Usuario de la base de datos")
    parser.add_argument("--db-password", type=str, default="root",
                        help="Contraseña de la base de datos")
    parser.add_argument("--db-name", type=str, default="evcharging",
                        help="Nombre de la base de datos")
    parser.add_argument("--port", type=int, default=8000,
                        help="Puerto del servidor (default: 8000)")
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

