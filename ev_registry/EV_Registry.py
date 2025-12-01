#!/usr/bin/env python3
"""
EV_Registry - Módulo de Registro de Puntos de Carga
Permite registrar, dar de baja y autenticar CPs en el sistema.

Uso:
    python EV_Registry.py --db-host 127.0.0.1 --db-port 3306 --db-user root --db-password root --db-name evcharging --port 6000
"""

import mysql.connector
from mysql.connector import Error
import argparse
import hashlib
import secrets
import threading
from datetime import datetime
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
REGISTRY_PORT = 6000

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
            database=DB_CONFIG['database']
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
                    return jsonify({
                        'status': 'error',
                        'message': f'CP {cp_id} ya está registrado y activo'
                    }), 409
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

@app.route('/api/unregister/<cp_id>', methods=['DELETE'])
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
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        
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
        
        try:
            context.load_cert_chain(cert_path, key_path)
            print(f"[EV_Registry] ✓ Certificados SSL cargados:")
            print(f"  - Certificado: {cert_path}")
            print(f"  - Clave privada: {key_path}")
            app.run(host='0.0.0.0', port=REGISTRY_PORT, ssl_context=context, debug=False, threaded=True)
        except Exception as e:
            print(f"[EV_Registry] ❌ ERROR cargando certificados SSL: {e}")
            print(f"[EV_Registry] Verifica que los archivos de certificado sean válidos")
            return
    else:
        print("[EV_Registry] ⚠️ SSL deshabilitado. Usando HTTP (no seguro)")
        app.run(host='0.0.0.0', port=REGISTRY_PORT, debug=False, threaded=True)

if __name__ == "__main__":
    main()

