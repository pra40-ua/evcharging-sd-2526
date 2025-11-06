#!/usr/bin/env python3
"""
Dashboard Web para EV_Central - Sistema de Carga de Vehículos Eléctricos
Interfaz visual para monitorizar y controlar la red de puntos de carga.

Uso:
    python web_dashboard.py --central-ip 127.0.0.1 --kafka 127.0.0.1:9092
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from kafka import KafkaConsumer, KafkaProducer
import json
import threading
import time
from datetime import datetime
from collections import defaultdict
import argparse
import mysql.connector

app = Flask(__name__)
CORS(app)

# =================================================================
#                    ESTADO GLOBAL DEL DASHBOARD
# =================================================================

# Estado de todos los CPs conocidos
CPS_STATE = {}
CPS_STATE_LOCK = threading.Lock()

# Telemetría más reciente
TELEMETRIA = {}
TELEMETRIA_LOCK = threading.Lock()

# Registro de eventos (últimos 100)
EVENTOS = []
EVENTOS_LOCK = threading.Lock()

# Estadísticas generales
STATS = {
    'total_cps': 0,
    'cps_activos': 0,
    'cps_suministrando': 0,
    'cps_averiados': 0,
    'energia_total': 0.0,
    'sesiones_activas': 0
}
STATS_LOCK = threading.Lock()

# Configuración global
CONFIG = {
    'kafka_broker': 'localhost:9092',
    'db_config': None,
    'central_ip': '127.0.0.1',
    'central_port': 5000
}

# Productor Kafka para enviar comandos
KAFKA_PRODUCER = None
KAFKA_PRODUCER_LOCK = threading.Lock()

# =================================================================
#                    CONSUMIDOR KAFKA (TELEMETRÍA)
# =================================================================

def cargar_estado_inicial_bd():
    """Carga el estado inicial de CPs desde la base de datos."""
    if not CONFIG.get('db_config'):
        print("[DASHBOARD] No hay configuración de BD, omitiendo carga inicial")
        return 0
    
    try:
        # Parsear configuración de BD
        parts = CONFIG['db_config'].split(':')
        if len(parts) != 5:
            print("[DASHBOARD] Formato de BD incorrecto")
            return 0
        
        host, port, user, password, database = parts
        
        # Conectar a BD
        connection = mysql.connector.connect(
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=database
        )
        
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT cp_id, estado, ubicacion, precio_kwh, fecha_ultima_conexion FROM charging_points")
            
            cps = cursor.fetchall()
            cps_nuevos = 0
            
            with CPS_STATE_LOCK:
                for cp in cps:
                    cp_id = cp['cp_id']
                    
                    # Solo añadir si no existe o actualizar datos complementarios
                    if cp_id not in CPS_STATE:
                        CPS_STATE[cp_id] = {
                            'cp_id': cp_id,
                            'estado': cp['estado'] or 'DESCONOCIDO',
                            'ultima_actualizacion': time.time(),
                            'ubicacion': cp['ubicacion'],
                            'precio_kwh': cp['precio_kwh']
                        }
                        print(f"[DASHBOARD] ✓ CP cargado desde BD: {cp_id} - {cp['estado']}")
                        cps_nuevos += 1
                    else:
                        # Actualizar solo ubicacion y precio si no están
                        if not CPS_STATE[cp_id].get('ubicacion'):
                            CPS_STATE[cp_id]['ubicacion'] = cp['ubicacion']
                        if not CPS_STATE[cp_id].get('precio_kwh'):
                            CPS_STATE[cp_id]['precio_kwh'] = cp['precio_kwh']
            
            cursor.close()
            connection.close()
            
            if cps_nuevos > 0:
                print(f"[DASHBOARD] ✓ {cps_nuevos} CP(s) nuevos cargados desde BD (Total: {len(cps)})")
                actualizar_estadisticas()
            
            return len(cps)
            
    except Exception as e:
        print(f"[DASHBOARD] ✗ Error cargando estado desde BD: {e}")
        return 0


def sincronizar_cps_desde_bd():
    """Sincroniza periódicamente el estado de CPs desde la base de datos."""
    print("[DASHBOARD] Iniciando hilo de sincronización con BD...")
    
    while True:
        try:
            time.sleep(10)  # Sincronizar cada 10 segundos
            
            num_cps = cargar_estado_inicial_bd()
            
            if num_cps > 0:
                with CPS_STATE_LOCK:
                    num_total = len(CPS_STATE)
                print(f"[DASHBOARD] 🔄 Sincronización BD: {num_total} CPs en estado")
        
        except Exception as e:
            print(f"[DASHBOARD] Error en sincronización BD: {e}")
            time.sleep(30)  # Esperar más si hay error


def consumir_telemetria(broker: str):
    """Consume telemetría de Kafka y actualiza el estado global con reconexión automática."""
    print(f"[DASHBOARD] Iniciando consumidor de telemetría en {broker}...")
    print(f"[DASHBOARD] Topic: telemetria_cp")
    print(f"[DASHBOARD] Group ID: dashboard-telemetry-group")
    
    mensaje_count = 0
    ultimo_log = time.time()
    reintentos = 0
    max_reintentos = 10
    
    while True:
        consumer = None
        try:
            print(f"[DASHBOARD] Conectando a Kafka... (intento {reintentos + 1}/{max_reintentos})")
            consumer = KafkaConsumer(
                'telemetria_cp',
                bootstrap_servers=[broker],
                auto_offset_reset='latest',
                enable_auto_commit=True,
                group_id='web-dashboard-telemetry-group',  # Diferente del Central para recibir TODOS los mensajes
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                api_version=(2, 5, 0),
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000,
                max_poll_interval_ms=300000,
                request_timeout_ms=40000
            )
            
            print("[DASHBOARD] ✓ Consumidor de telemetría conectado correctamente")
            print("[DASHBOARD] Esperando telemetría de CPs...")
            reintentos = 0  # Reset contador de reintentos tras conexión exitosa
            
            # Bucle de consumo usando poll() para mejor control
            while True:
                try:
                    # Poll con timeout corto para permitir reconexión si hay error
                    records = consumer.poll(timeout_ms=1000, max_records=10)
                    
                    if not records:
                        # Sin mensajes, continuar esperando
                        continue
                    
                    # Procesar mensajes recibidos
                    for topic_partition, messages in records.items():
                        for message in messages:
                            mensaje_count += 1
                            telemetria = message.value
                            cp_id = telemetria.get('cp_id', 'UNKNOWN')
                            
                            # Log cada mensaje recibido con datos detallados
                            kw = telemetria.get('kw_entregados', 0) or telemetria.get('energia_total', 0)
                            potencia = telemetria.get('potencia_actual', 0)
                            tiempo = telemetria.get('tiempo_carga_s', 0)
                            estado = telemetria.get('estado_carga', telemetria.get('estado', 'N/D'))
                            print(f"[DASHBOARD] ← Mensaje #{mensaje_count} | CP={cp_id} | Estado={estado} | kW={kw} | P={potencia} | t={tiempo}s")
                            
                            # Actualizar telemetría
                            with TELEMETRIA_LOCK:
                                TELEMETRIA[cp_id] = {
                                    **telemetria,
                                    'timestamp': telemetria.get('timestamp', time.time()),
                                    'timestamp_str': datetime.now().strftime('%H:%M:%S')
                                }
                            
                            # Actualizar estado del CP
                            with CPS_STATE_LOCK:
                                if cp_id not in CPS_STATE:
                                    CPS_STATE[cp_id] = {
                                        'cp_id': cp_id,
                                        'estado': 'DESCONOCIDO',
                                        'ultima_actualizacion': time.time()
                                    }
                                    # Registrar evento solo si es un CP nuevo
                                    registrar_evento(f"Nuevo CP detectado: {cp_id}", 'info')
                                    print(f"[DASHBOARD] ✓ Nuevo CP añadido al estado: {cp_id}")
                                
                                estado_carga = telemetria.get('estado_carga', telemetria.get('estado', 'DESCONOCIDO'))
                                estado_anterior = CPS_STATE[cp_id].get('estado', 'DESCONOCIDO')
                                
                                # Extraer datos clave de telemetría para debug
                                kw_entregados = telemetria.get('kw_entregados', 0)
                                potencia = telemetria.get('potencia_actual', 0)
                                tiempo = telemetria.get('tiempo_carga_s', 0)
                                
                                CPS_STATE[cp_id].update({
                                    'estado': estado_carga,
                                    'ultima_actualizacion': time.time(),
                                    'ubicacion': telemetria.get('ubicacion', CPS_STATE[cp_id].get('ubicacion', '-')),
                                    'precio_kwh': telemetria.get('precio_kwh', CPS_STATE[cp_id].get('precio_kwh', 0.0))
                                })
                                
                                # Registrar evento solo si el estado cambió
                                if estado_anterior != estado_carga:
                                    registrar_evento(f"{cp_id}: {estado_anterior} → {estado_carga}", 'info')
                                    print(f"[DASHBOARD] Estado actualizado: {cp_id} → {estado_carga} (kW={kw_entregados}, P={potencia}, t={tiempo}s)")
                            
                            # Actualizar estadísticas
                            actualizar_estadisticas()
                    
                    # Log periódico de actividad cada 30 segundos
                    ahora = time.time()
                    if ahora - ultimo_log > 30:
                        with CPS_STATE_LOCK:
                            num_cps = len(CPS_STATE)
                        print(f"[DASHBOARD] Estado actual: {num_cps} CPs registrados, {mensaje_count} mensajes procesados")
                        ultimo_log = ahora
                
                except Exception as poll_error:
                    print(f"[DASHBOARD] ⚠️ Error en poll de Kafka: {poll_error}")
                    # Romper el bucle interno para intentar reconectar
                    break
        
        except Exception as e:
            reintentos += 1
            print(f"[DASHBOARD] ✗ Error en consumidor de telemetría: {e}")
            
            if reintentos >= max_reintentos:
                print(f"[DASHBOARD] ✗ Máximo de reintentos alcanzado ({max_reintentos}). Deteniendo consumidor.")
                return
            
            # Espera progresiva antes de reintentar (backoff exponencial)
            espera = min(2 ** reintentos, 30)  # Máximo 30 segundos
            print(f"[DASHBOARD] Reintentando en {espera} segundos...")
            time.sleep(espera)
        
        finally:
            # Cerrar el consumidor si existe
            if consumer is not None:
                try:
                    consumer.close()
                    print("[DASHBOARD] Consumidor cerrado correctamente")
                except:
                    pass


def registrar_evento(mensaje: str, tipo: str = 'info'):
    """Registra un evento en el log del dashboard."""
    with EVENTOS_LOCK:
        evento = {
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'mensaje': mensaje,
            'tipo': tipo
        }
        EVENTOS.append(evento)
        
        # Mantener solo los últimos 100 eventos
        if len(EVENTOS) > 100:
            EVENTOS.pop(0)


def actualizar_estadisticas():
    """Recalcula las estadísticas globales."""
    with STATS_LOCK, CPS_STATE_LOCK, TELEMETRIA_LOCK:
        STATS['total_cps'] = len(CPS_STATE)
        STATS['cps_activos'] = sum(1 for cp in CPS_STATE.values() 
                                    if cp.get('estado', '').upper() in ['ACTIVADO', 'REPOSO', 'SUMINISTRANDO', 'CARGANDO', 'PRE-SUMINISTRO', 
                                                                         'PENDIENTE_CONFIRMACION_CENTRAL', 'ESPERANDO_OPERADOR_ENGINE', 
                                                                         'LISTO_PARA_INICIAR'])
        STATS['cps_suministrando'] = sum(1 for cp in CPS_STATE.values() 
                                          if cp.get('estado', '').upper() in ['SUMINISTRANDO', 'CARGANDO'])
        STATS['cps_averiados'] = sum(1 for cp in CPS_STATE.values() 
                                      if cp.get('estado', '').upper() in ['AVERIADO', 'AVERÍA'])
        
        # Energía total entregada (acumulada de todas las sesiones ACTIVAS)
        energia_total = 0.0
        for cp_id, tel in TELEMETRIA.items():
            kw = tel.get('kw_entregados', 0) or tel.get('energia_total', 0)
            try:
                energia_total += float(kw)
            except:
                pass
        STATS['energia_total'] = round(energia_total, 2)
        
        STATS['sesiones_activas'] = STATS['cps_suministrando']


# =================================================================
#                    RUTAS DE LA API REST
# =================================================================

@app.route('/')
def index():
    """Página principal del dashboard."""
    return render_template('dashboard.html')


@app.route('/api/status')
def api_status():
    """Devuelve el estado general del sistema."""
    with STATS_LOCK:
        stats_copy = STATS.copy()
    
    with CPS_STATE_LOCK:
        cps_list = list(CPS_STATE.values())
    
    # Enriquecer con telemetría (extraer campos para el frontend)
    with TELEMETRIA_LOCK:
        for cp in cps_list:
            cp_id = cp['cp_id']
            if cp_id in TELEMETRIA:
                tel = TELEMETRIA[cp_id]
                cp['telemetria'] = tel  # Mantener el objeto completo para debug
                # Extraer campos individuales para el frontend
                cp['energia_kwh'] = tel.get('kw_entregados', 0) or tel.get('energia_total', 0)
                cp['potencia_kw'] = tel.get('potencia_actual', 0)
                cp['tiempo_carga_s'] = tel.get('tiempo_carga_s', 0)
                cp['timestamp_telemetria'] = tel.get('timestamp_str', '-')
                cp['tiene_sesion_activa'] = tel.get('tiene_sesion_activa', False)
                cp['driver_id_sesion'] = tel.get('driver_id_sesion', None)
            else:
                # Sin telemetría, valores por defecto
                cp['energia_kwh'] = 0
                cp['potencia_kw'] = 0
                cp['tiempo_carga_s'] = 0
                cp['timestamp_telemetria'] = '-'
                cp['tiene_sesion_activa'] = False
                cp['driver_id_sesion'] = None
    
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'stats': stats_copy,
        'cps': cps_list
    })


@app.route('/api/cps')
def api_cps():
    """Devuelve la lista de todos los CPs con su estado y telemetría."""
    with CPS_STATE_LOCK:
        cps_list = []
        for cp_id, cp_data in CPS_STATE.items():
            cp_info = cp_data.copy()
            
            # Agregar telemetría si existe
            with TELEMETRIA_LOCK:
                if cp_id in TELEMETRIA:
                    tel = TELEMETRIA[cp_id]
                    cp_info['energia_kwh'] = tel.get('kw_entregados', 0) or tel.get('energia_total', 0)
                    cp_info['potencia_kw'] = tel.get('potencia_actual', 0)
                    cp_info['tiempo_carga_s'] = tel.get('tiempo_carga_s', 0)
                    cp_info['timestamp_telemetria'] = tel.get('timestamp_str', '-')
                    cp_info['tiene_sesion_activa'] = tel.get('tiene_sesion_activa', False)
                    cp_info['driver_id_sesion'] = tel.get('driver_id_sesion', None)
                    
                    # Debug: log de telemetría enviada
                    print(f"[API /api/cps] {cp_id}: kW={cp_info['energia_kwh']}, P={cp_info['potencia_kw']}, t={cp_info['tiempo_carga_s']}s, sesion={cp_info['tiene_sesion_activa']}")
                else:
                    cp_info['energia_kwh'] = 0
                    cp_info['potencia_kw'] = 0
                    cp_info['tiempo_carga_s'] = 0
                    cp_info['timestamp_telemetria'] = '-'
                    cp_info['tiene_sesion_activa'] = False
                    cp_info['driver_id_sesion'] = None
                    print(f"[API /api/cps] {cp_id}: SIN TELEMETRÍA en diccionario")
            
            cps_list.append(cp_info)
    
    # Ordenar por CP_ID
    cps_list.sort(key=lambda x: x['cp_id'])
    
    return jsonify({
        'status': 'ok',
        'count': len(cps_list),
        'cps': cps_list
    })


@app.route('/api/events')
def api_events():
    """Devuelve el log de eventos recientes."""
    with EVENTOS_LOCK:
        eventos_copy = EVENTOS.copy()
    
    # Devolver en orden inverso (más recientes primero)
    eventos_copy.reverse()
    
    return jsonify({
        'status': 'ok',
        'count': len(eventos_copy),
        'events': eventos_copy[:50]  # Últimos 50
    })


@app.route('/api/stats')
def api_stats():
    """Devuelve estadísticas agregadas del sistema."""
    with STATS_LOCK:
        stats_copy = STATS.copy()
    
    # Calcular estadísticas adicionales
    with CPS_STATE_LOCK:
        estados_count = defaultdict(int)
        for cp in CPS_STATE.values():
            estado = cp.get('estado', 'DESCONOCIDO').upper()
            estados_count[estado] += 1
    
    stats_copy['estados_distribucion'] = dict(estados_count)
    
    return jsonify({
        'status': 'ok',
        'stats': stats_copy
    })


@app.route('/api/debug')
def api_debug():
    """Endpoint de diagnóstico para verificar el estado interno del dashboard."""
    with CPS_STATE_LOCK:
        cps_state_debug = {cp_id: dict(cp_data) for cp_id, cp_data in CPS_STATE.items()}
    
    with TELEMETRIA_LOCK:
        telemetria_debug = {cp_id: dict(tel_data) for cp_id, tel_data in TELEMETRIA.items()}
    
    with EVENTOS_LOCK:
        eventos_recientes = EVENTOS[-10:] if EVENTOS else []
    
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'config': {
            'kafka_broker': CONFIG.get('kafka_broker'),
            'central_ip': CONFIG.get('central_ip'),
            'central_port': CONFIG.get('central_port'),
            'db_configured': CONFIG.get('db_config') is not None
        },
        'cps_state': cps_state_debug,
        'telemetria': telemetria_debug,
        'eventos_recientes': eventos_recientes,
        'num_cps': len(cps_state_debug),
        'num_telemetria': len(telemetria_debug)
    })


@app.route('/api/reload_from_db', methods=['POST'])
def api_reload_from_db():
    """Fuerza una recarga de CPs desde la base de datos."""
    try:
        num_cps = cargar_estado_inicial_bd()
        
        if num_cps > 0:
            registrar_evento(f"Recarga manual desde BD: {num_cps} CPs", 'info')
            with CPS_STATE_LOCK:
                total = len(CPS_STATE)
            
            return jsonify({
                'status': 'ok',
                'message': f'{num_cps} CPs cargados desde BD',
                'total_cps': total
            })
        else:
            return jsonify({
                'status': 'warn',
                'message': 'No se encontraron CPs en BD o no hay configuración de BD',
                'total_cps': 0
            })
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/command', methods=['POST'])
def api_command():
    """
    Endpoint para enviar comandos a CPs.
    
    Body JSON:
        {
            "cp_id": "CP001",
            "command": "START" | "STOP"
        }
    """
    try:
        data = request.get_json()
        cp_id = data.get('cp_id')
        command = data.get('command', '').upper()
        
        if not cp_id or command not in ['START', 'STOP']:
            return jsonify({
                'status': 'error',
                'message': 'Parámetros inválidos. Se requiere cp_id y command (START/STOP)'
            }), 400
        
        # Enviar comando a través de Kafka al Central
        try:
            with KAFKA_PRODUCER_LOCK:
                if KAFKA_PRODUCER is None:
                    return jsonify({
                        'status': 'error',
                        'message': 'Productor Kafka no disponible'
                    }), 503
                
                comando_msg = {
                    'cp_id': cp_id,
                    'command': command,
                    'timestamp': datetime.now().isoformat(),
                    'source': 'web_dashboard'
                }
                
                KAFKA_PRODUCER.send('central_commands', value=comando_msg)
                KAFKA_PRODUCER.flush(timeout=2)
                
                registrar_evento(f"Comando {command} enviado a {cp_id}", 'command')
                
                return jsonify({
                    'status': 'ok',
                    'message': f'Comando {command} enviado a {cp_id}',
                    'cp_id': cp_id,
                    'command': command
                })
                
        except Exception as kafka_error:
            registrar_evento(f"Error enviando comando a Kafka: {kafka_error}", 'error')
            return jsonify({
                'status': 'error',
                'message': f'Error enviando comando: {str(kafka_error)}'
            }), 500
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/preparar_suministro/<cp_id>', methods=['POST'])
def api_preparar_suministro(cp_id):
    """
    PASO 1: Operador de Central prepara el suministro enviando AUTH_REQ al Engine.
    Esto hace que aparezca el botón en la web del Engine.
    """
    try:
        print(f"[DASHBOARD] Preparación de suministro solicitada para {cp_id}")
        
        # Enviar comando PREPARE_SUPPLY a través de Kafka
        with KAFKA_PRODUCER_LOCK:
            if KAFKA_PRODUCER is None:
                return jsonify({
                    'status': 'error',
                    'message': 'Productor Kafka no disponible'
                }), 503
            
            comando_msg = {
                'cp_id': cp_id,
                'command': 'PREPARE_SUPPLY',
                'timestamp': datetime.now().isoformat(),
                'source': 'web_dashboard_paso1'
            }
            
            KAFKA_PRODUCER.send('central_commands', value=comando_msg)
            KAFKA_PRODUCER.flush(timeout=2)
            
            registrar_evento(f"✅ Preparación de suministro para {cp_id} (enviando a Engine)", 'command')
            
            return jsonify({
                'status': 'ok',
                'message': f'Solicitud enviada a Engine. Esperando confirmación del operador del Engine...',
                'cp_id': cp_id
            })
    
    except Exception as e:
        registrar_evento(f"Error preparando suministro para {cp_id}: {e}", 'error')
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/confirmar_inicio/<cp_id>', methods=['POST'])
def api_confirmar_inicio(cp_id):
    """
    PASO 2: Confirma el inicio de suministro para un CP que está LISTO_PARA_INICIAR.
    (El Engine ya confirmó que está listo)
    """
    try:
        print(f"[DASHBOARD] Confirmación FINAL de inicio solicitada para {cp_id}")
        
        # Enviar comando START a través de Kafka
        with KAFKA_PRODUCER_LOCK:
            if KAFKA_PRODUCER is None:
                return jsonify({
                    'status': 'error',
                    'message': 'Productor Kafka no disponible'
                }), 503
            
            comando_msg = {
                'cp_id': cp_id,
                'command': 'START',
                'timestamp': datetime.now().isoformat(),
                'source': 'web_dashboard_confirmacion_final'
            }
            
            KAFKA_PRODUCER.send('central_commands', value=comando_msg)
            KAFKA_PRODUCER.flush(timeout=2)
            
            registrar_evento(f"✅ Inicio de suministro CONFIRMADO para {cp_id}", 'command')
            
            return jsonify({
                'status': 'ok',
                'message': f'Inicio confirmado para {cp_id}. Suministro iniciándose...',
                'cp_id': cp_id
            })
    
    except Exception as e:
        registrar_evento(f"Error confirmando inicio para {cp_id}: {e}", 'error')
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/confirmar_fin/<cp_id>', methods=['POST'])
def api_confirmar_fin(cp_id):
    """
    Confirma el fin de suministro para un CP que está ESPERANDO_CONFIRMACION_FIN.
    """
    try:
        print(f"[DASHBOARD] Confirmación de fin solicitada para {cp_id}")
        
        # Enviar comando STOP a través de Kafka
        with KAFKA_PRODUCER_LOCK:
            if KAFKA_PRODUCER is None:
                return jsonify({
                    'status': 'error',
                    'message': 'Productor Kafka no disponible'
                }), 503
            
            comando_msg = {
                'cp_id': cp_id,
                'command': 'STOP',
                'timestamp': datetime.now().isoformat(),
                'source': 'web_dashboard_confirmacion'
            }
            
            KAFKA_PRODUCER.send('central_commands', value=comando_msg)
            KAFKA_PRODUCER.flush(timeout=2)
            
            registrar_evento(f"✅ Fin de suministro CONFIRMADO para {cp_id}", 'command')
            
            return jsonify({
                'status': 'ok',
                'message': f'Fin confirmado para {cp_id}. Generando ticket...',
                'cp_id': cp_id
            })
    
    except Exception as e:
        registrar_evento(f"Error confirmando fin para {cp_id}: {e}", 'error')
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# =================================================================
#                    TEMPLATES HTML
# =================================================================

def crear_templates():
    """Crea el template HTML del dashboard."""
    import os
    
    # Crear directorio templates si no existe
    os.makedirs('templates', exist_ok=True)
    
    html_content = '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EV Central Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        header {
            background: white;
            padding: 20px 30px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        h1 {
            color: #667eea;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            text-align: center;
        }
        
        .stat-card h3 {
            font-size: 14px;
            color: #666;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .stat-card .value {
            font-size: 36px;
            font-weight: bold;
            color: #667eea;
        }
        
        .content-grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
        }
        
        .panel {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .panel h2 {
            margin-bottom: 15px;
            color: #667eea;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        
        .cps-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .cps-table th {
            background: #f8f9fa;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #dee2e6;
        }
        
        .cps-table td {
            padding: 12px;
            border-bottom: 1px solid #dee2e6;
        }
        
        .cps-table tr:hover {
            background: #f8f9fa;
        }
        
        .status-badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            display: inline-block;
        }
        
        .status-activado { background: #28a745; color: white; }
        .status-suministrando { background: #17a2b8; color: white; }
        .status-cargando { background: #007bff; color: white; }
        .status-parado { background: #ffc107; color: #333; }
        .status-averiado { background: #dc3545; color: white; }
        .status-desconectado { background: #6c757d; color: white; }
        .status-reposo { background: #6c757d; color: white; }
        .status-pre-suministro { background: #fd7e14; color: white; }
        .status-esperando-operador-engine { background: #ffc107; color: #333; }
        .status-listo-para-iniciar { background: #28a745; color: white; }
        .status-esperando-confirmacion-fin { background: #dc3545; color: white; }
        .status-esperando-driver { background: #17a2b8; color: white; }
        .status-pendiente-confirmacion-central { background: #007bff; color: white; animation: pulse 2s infinite; }
        
        .btn-control {
            padding: 6px 12px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 600;
            margin: 0 2px;
            transition: all 0.2s;
        }
        
        .btn-start {
            background: #28a745;
            color: white;
        }
        
        .btn-start:hover {
            background: #218838;
        }
        
        .btn-stop {
            background: #dc3545;
            color: white;
        }
        
        .btn-stop:hover {
            background: #c82333;
        }
        
        .btn-control:disabled {
            background: #6c757d;
            cursor: not-allowed;
            opacity: 0.5;
        }
        
        .toast {
            position: fixed;
            top: 20px;
            right: 20px;
            background: white;
            padding: 15px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            z-index: 1000;
            display: none;
            min-width: 250px;
        }
        
        .toast.show {
            display: block;
            animation: slideIn 0.3s ease;
        }
        
        .toast.success {
            border-left: 4px solid #28a745;
        }
        
        .toast.error {
            border-left: 4px solid #dc3545;
        }
        
        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        
        .events-log {
            max-height: 400px;
            overflow-y: auto;
            font-size: 13px;
        }
        
        .event-item {
            padding: 8px;
            border-left: 3px solid #667eea;
            margin-bottom: 8px;
            background: #f8f9fa;
            border-radius: 4px;
        }
        
        .event-time {
            color: #666;
            font-size: 11px;
            font-weight: 600;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        
        .refresh-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #28a745;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        
        @media (max-width: 768px) {
            .content-grid {
                grid-template-columns: 1fr;
            }
            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>
                <span>⚡</span>
                EV Central Dashboard
                <span class="refresh-indicator"></span>
            </h1>
            <div style="text-align: right;">
                <div style="font-size: 12px; color: #666;">Sistema de Carga de Vehículos Eléctricos</div>
                <div style="font-size: 11px; color: #999;" id="last-update">Actualizando...</div>
                <button class="btn-reload" onclick="recargarDesdeDB()" style="margin-top: 8px; padding: 6px 12px; background: #667eea; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 11px; font-weight: 600;">
                    🔄 Recargar desde BD
                </button>
            </div>
        </header>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Total CPs</h3>
                <div class="value" id="stat-total">0</div>
            </div>
            <div class="stat-card">
                <h3>Activos</h3>
                <div class="value" style="color: #28a745;" id="stat-activos">0</div>
            </div>
            <div class="stat-card">
                <h3>Suministrando</h3>
                <div class="value" style="color: #17a2b8;" id="stat-suministrando">0</div>
            </div>
            <div class="stat-card">
                <h3>Averiados</h3>
                <div class="value" style="color: #dc3545;" id="stat-averiados">0</div>
            </div>
            <div class="stat-card">
                <h3>Energía Total</h3>
                <div class="value" style="color: #ffc107; font-size: 24px;" id="stat-energia">0.00 kWh</div>
            </div>
            <div class="stat-card">
                <h3>Sesiones Activas</h3>
                <div class="value" style="color: #007bff;" id="stat-sesiones">0</div>
            </div>
        </div>
        
        <div class="content-grid">
            <div class="panel">
                <h2>🔌 Puntos de Carga</h2>
                <div id="cps-container" class="loading">Cargando datos...</div>
            </div>
            
            <div class="panel">
                <h2>📋 Eventos Recientes</h2>
                <div id="events-container" class="events-log loading">Cargando eventos...</div>
            </div>
        </div>
    </div>
    
    <script>
        // Actualización automática cada 2 segundos
        let updateInterval;
        
        function actualizarDashboard() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    // Actualizar estadísticas
                    document.getElementById('stat-total').textContent = data.stats.total_cps;
                    document.getElementById('stat-activos').textContent = data.stats.cps_activos;
                    document.getElementById('stat-suministrando').textContent = data.stats.cps_suministrando;
                    document.getElementById('stat-averiados').textContent = data.stats.cps_averiados;
                    document.getElementById('stat-energia').textContent = data.stats.energia_total.toFixed(2) + ' kWh';
                    document.getElementById('stat-sesiones').textContent = data.stats.sesiones_activas;
                    
                    // Actualizar tabla de CPs
                    actualizarTablaCPs(data.cps);
                    
                    // Actualizar timestamp
                    const now = new Date();
                    document.getElementById('last-update').textContent = 
                        'Última actualización: ' + now.toLocaleTimeString('es-ES');
                })
                .catch(error => console.error('Error actualizando dashboard:', error));
            
            // Actualizar eventos
            fetch('/api/events')
                .then(response => response.json())
                .then(data => {
                    actualizarEventos(data.events);
                })
                .catch(error => console.error('Error actualizando eventos:', error));
        }
        
        function actualizarTablaCPs(cps) {
            if (!cps || cps.length === 0) {
                document.getElementById('cps-container').innerHTML = 
                    '<p style="text-align: center; color: #999;">No hay puntos de carga conectados</p>';
                return;
            }
            
            let html = '<table class="cps-table"><thead><tr>';
            html += '<th>CP ID</th>';
            html += '<th>Estado</th>';
            html += '<th>Energía (kWh)</th>';
            html += '<th>Potencia (kW)</th>';
            html += '<th>Tiempo (s)</th>';
            html += '<th>Última Act.</th>';
            html += '<th>Acciones</th>';
            html += '</tr></thead><tbody>';
            
            cps.forEach(cp => {
                const estadoRaw = (cp.estado || 'DESCONOCIDO').toUpperCase();
                // Regla UX: mostrar REPOSO como ACTIVADO (conectado y disponible)
                const estado = (estadoRaw === 'REPOSO') ? 'ACTIVADO' : estadoRaw;
                const estadoClass = 'status-' + estado.toLowerCase().replace('í', 'i').replace('-', '-');
                const tieneSesion = cp.tiene_sesion_activa || false;
                
                html += '<tr>';
                html += `<td><strong>${cp.cp_id}</strong></td>`;
                html += `<td><span class="status-badge ${estadoClass}">${estado}</span></td>`;
                html += `<td>${(cp.energia_kwh || 0).toFixed(2)}</td>`;
                html += `<td>${(cp.potencia_kw || 0).toFixed(2)}</td>`;
                html += `<td>${cp.tiempo_carga_s || 0}</td>`;
                html += `<td>${cp.timestamp_telemetria || '-'}</td>`;
                html += '<td>';
                
                // Botones de control según el NUEVO FLUJO INTERACTIVO (3 PASOS)
                if (estado === 'DESCONECTADO' || estado === 'AVERIADO' || estado === 'AVERÍA') {
                    html += '<button class="btn-control" disabled>Sin Conexión</button>';
                } else if (estado === 'PENDIENTE_CONFIRMACION_CENTRAL' || estado === 'PENDIENTE CONFIRMACION CENTRAL') {
                    // PASO 1: Driver solicitó, operador de Central debe preparar
                    const driver = cp.driver_id_sesion || 'Driver';
                    const objetivo = cp.telemetria?.objetivo_kwh || '?';
                    html += `<button class="btn-control btn-start" onclick="prepararSuministro('${cp.cp_id}')" style="background: #007bff; animation: pulse 2s infinite;">🚀 PREPARAR SUMINISTRO (${driver})</button>`;
                } else if (estado === 'ESPERANDO_OPERADOR_ENGINE' || estado === 'ESPERANDO OPERADOR ENGINE') {
                    // PASO 2: Central preparó, esperando que Engine confirme
                    html += '<span style="color: #ffc107; font-size: 12px;">⏳ Esperando confirmación de Engine...</span>';
                } else if (estado === 'LISTO_PARA_INICIAR' || estado === 'LISTO PARA INICIAR') {
                    // PASO 3: Engine confirmó - Mostrar botón de confirmación FINAL
                    html += `<button class="btn-control btn-start" onclick="confirmarInicio('${cp.cp_id}')" style="background: #28a745; animation: pulse 2s infinite;">✓ CONFIRMAR INICIO</button>`;
                } else if (estado === 'ESPERANDO_CONFIRMACION_FIN' || estado === 'ESPERANDO CONFIRMACION FIN') {
                    // Engine envió REQUEST_STOP - Mostrar botón de confirmación
                    html += `<button class="btn-control btn-stop" onclick="confirmarFin('${cp.cp_id}')" style="background: #dc3545; animation: pulse 2s infinite;">✓ CONFIRMAR FIN</button>`;
                } else if (estado === 'SUMINISTRANDO' || estado === 'CARGANDO') {
                    // Durante carga: NO permitir detener (debe ser desde Engine)
                    html += '<span style="color: #17a2b8; font-size: 12px;">⚡ Suministrando...</span>';
                } else if (estado === 'ACTIVADO') {
                    // Si hay una sesión marcada pero el estado figura como ACTIVADO (p.ej. por telemetría/heartbeat),
                    // ofrecer la acción de PREPARAR SUMINISTRO igualmente
                    if (tieneSesion) {
                        const driver = cp.driver_id_sesion || 'Driver';
                        html += `<button class="btn-control btn-start" onclick="prepararSuministro('${cp.cp_id}')" style="background: #007bff; animation: pulse 2s infinite;">🚀 PREPARAR SUMINISTRO (${driver})</button>`;
                    } else {
                        // CP disponible
                        html += '<span style="color: #999; font-size: 12px;">💤 Disponible</span>';
                    }
                } else {
                    html += '<span style="color: #999; font-size: 12px;">-</span>';
                }
                
                html += '</td>';
                html += '</tr>';
            });
            
            html += '</tbody></table>';
            document.getElementById('cps-container').innerHTML = html;
        }
        
        function actualizarEventos(eventos) {
            if (!eventos || eventos.length === 0) {
                document.getElementById('events-container').innerHTML = 
                    '<p style="text-align: center; color: #999;">No hay eventos recientes</p>';
                return;
            }
            
            let html = '';
            eventos.slice(0, 20).forEach(evento => {
                html += `<div class="event-item">`;
                html += `<span class="event-time">${evento.timestamp}</span> `;
                html += `<span>${evento.mensaje}</span>`;
                html += `</div>`;
            });
            
            document.getElementById('events-container').innerHTML = html;
        }
        
        // Función para preparar suministro (PASO 1: Central → Engine)
        function prepararSuministro(cpId) {
            if (!confirm(`¿Preparar suministro para ${cpId}?\n\nSe enviará señal al Engine para que muestre el botón de inicio.`)) return;
            
            fetch(`/api/preparar_suministro/${cpId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'ok') {
                    mostrarNotificacion(`✓ ${data.message}`, 'success');
                } else {
                    mostrarNotificacion(`Error: ${data.message}`, 'error');
                }
                actualizarDashboard();
            })
            .catch(error => {
                mostrarNotificacion(`Error: ${error}`, 'error');
                console.error('Error preparando suministro:', error);
            });
        }
        
        // Función para confirmar inicio de suministro (PASO 3: Central confirma tras Engine)
        function confirmarInicio(cpId) {
            if (!confirm(`¿Confirmar INICIO FINAL de suministro para ${cpId}?\n\nEl suministro comenzará inmediatamente.`)) return;
            
            fetch(`/api/confirmar_inicio/${cpId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'ok') {
                    mostrarNotificacion(`✓ Inicio confirmado para ${cpId}`, 'success');
                } else {
                    mostrarNotificacion(`Error: ${data.message}`, 'error');
                }
                actualizarDashboard();
            })
            .catch(error => {
                mostrarNotificacion(`Error: ${error}`, 'error');
                console.error('Error confirmando inicio:', error);
            });
        }
        
        // Función para confirmar fin de suministro (NUEVO FLUJO)
        function confirmarFin(cpId) {
            if (!confirm(`¿Confirmar FIN de suministro para ${cpId}?`)) return;
            
            fetch(`/api/confirmar_fin/${cpId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'ok') {
                    mostrarNotificacion(`✓ Fin confirmado para ${cpId}`, 'success');
                } else {
                    mostrarNotificacion(`Error: ${data.message}`, 'error');
                }
                actualizarDashboard();
            })
            .catch(error => {
                mostrarNotificacion(`Error: ${error}`, 'error');
                console.error('Error confirmando fin:', error);
            });
        }
        
        // Función para enviar comandos a los CPs (DEPRECADA - usar confirmarInicio/confirmarFin)
        function enviarComando(cpId, comando) {
            // Deshabilitar el botón temporalmente
            event.target.disabled = true;
            event.target.textContent = '⏳ Enviando...';
            
            fetch('/api/command', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    cp_id: cpId,
                    command: comando
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'ok') {
                    mostrarNotificacion(`Comando ${comando} enviado a ${cpId}`, 'success');
                } else {
                    mostrarNotificacion(`Error: ${data.message}`, 'error');
                }
                // Actualizar inmediatamente el dashboard
                actualizarDashboard();
            })
            .catch(error => {
                mostrarNotificacion(`Error de conexión: ${error}`, 'error');
                console.error('Error enviando comando:', error);
                // Restaurar el botón
                setTimeout(() => {
                    actualizarDashboard();
                }, 1000);
            });
        }
        
        // Función para mostrar notificaciones
        function mostrarNotificacion(mensaje, tipo) {
            // Crear elemento de notificación si no existe
            let toast = document.getElementById('toast');
            if (!toast) {
                toast = document.createElement('div');
                toast.id = 'toast';
                toast.className = 'toast';
                document.body.appendChild(toast);
            }
            
            toast.textContent = mensaje;
            toast.className = `toast ${tipo} show`;
            
            // Ocultar después de 3 segundos
            setTimeout(() => {
                toast.classList.remove('show');
            }, 3000);
        }
        
        // Función para forzar recarga desde BD
        function recargarDesdeDB() {
            fetch('/api/reload_from_db', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'ok') {
                    mostrarNotificacion(`✓ ${data.message}`, 'success');
                    // Actualizar dashboard inmediatamente
                    actualizarDashboard();
                } else {
                    mostrarNotificacion(`⚠ ${data.message}`, 'error');
                }
            })
            .catch(error => {
                mostrarNotificacion(`Error: ${error}`, 'error');
                console.error('Error recargando desde BD:', error);
            });
        }
        
        // Iniciar actualización automática
        actualizarDashboard();
        updateInterval = setInterval(actualizarDashboard, 2000);
    </script>
</body>
</html>'''
    
    with open('templates/dashboard.html', 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print("[DASHBOARD] Template HTML creado en templates/dashboard.html")


# =================================================================
#                    MAIN
# =================================================================

def inicializar_kafka_producer(broker: str):
    """Inicializa el productor Kafka para enviar comandos."""
    global KAFKA_PRODUCER
    with KAFKA_PRODUCER_LOCK:
        try:
            KAFKA_PRODUCER = KafkaProducer(
                bootstrap_servers=[broker],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                api_version=(2, 5, 0)
            )
            print("[DASHBOARD] Productor Kafka inicializado.")
        except Exception as e:
            print(f"[DASHBOARD] Error inicializando productor Kafka: {e}")
            KAFKA_PRODUCER = None


def main():
    parser = argparse.ArgumentParser(description="Dashboard Web para EV_Central")
    parser.add_argument("--port", type=int, default=8080,
                        help="Puerto del servidor web (default: 8080)")
    parser.add_argument("--kafka", type=str, required=True,
                        help="Broker Kafka (IP:puerto)")
    parser.add_argument("--central-ip", type=str, default="127.0.0.1",
                        help="IP de EV_Central")
    parser.add_argument("--central-port", type=int, default=5000,
                        help="Puerto de EV_Central")
    parser.add_argument("--db", type=str,
                        help="Configuración de BD (formato: host:port:user:password:database)")
    
    args = parser.parse_args()
    
    # Configurar
    CONFIG['kafka_broker'] = args.kafka
    CONFIG['central_ip'] = args.central_ip
    CONFIG['central_port'] = args.central_port
    CONFIG['db_config'] = args.db
    
    print("="*70)
    print("  EV CENTRAL - DASHBOARD WEB")
    print("="*70)
    print(f"  Puerto web:    {args.port}")
    print(f"  Kafka:         {args.kafka}")
    print(f"  Central:       {args.central_ip}:{args.central_port}")
    print(f"  Base de datos: {args.db if args.db else 'No configurada'}")
    print("="*70)
    print()
    
    # Crear templates
    crear_templates()
    
    # Cargar estado inicial desde BD si está disponible
    if args.db:
        print("[DASHBOARD] Cargando estado inicial desde la base de datos...")
        cargar_estado_inicial_bd()
        
        # Iniciar hilo de sincronización periódica con BD
        bd_sync_thread = threading.Thread(
            target=sincronizar_cps_desde_bd,
            daemon=True
        )
        bd_sync_thread.start()
        print("[DASHBOARD] ✓ Sincronización automática con BD activada")
    
    # Inicializar productor Kafka para enviar comandos
    inicializar_kafka_producer(args.kafka)
    
    # Iniciar consumidor de Kafka en hilo separado
    kafka_thread = threading.Thread(
        target=consumir_telemetria,
        args=(args.kafka,),
        daemon=True
    )
    kafka_thread.start()
    
    print(f"\n[DASHBOARD] Iniciando servidor web en http://0.0.0.0:{args.port}")
    print(f"[DASHBOARD] Accede desde tu navegador a: http://localhost:{args.port}")
    print()
    
    # Iniciar servidor Flask
    app.run(host='0.0.0.0', port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()



