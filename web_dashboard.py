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

# =================================================================
#                    CONSUMIDOR KAFKA (TELEMETRÍA)
# =================================================================

def consumir_telemetria(broker: str):
    """Consume telemetría de Kafka y actualiza el estado global."""
    print(f"[DASHBOARD] Iniciando consumidor de telemetría en {broker}...")
    
    try:
        consumer = KafkaConsumer(
            'telemetria_cp',
            bootstrap_servers=[broker],
            auto_offset_reset='latest',
            enable_auto_commit=True,
            group_id='dashboard-telemetry-group',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            api_version=(2, 5, 0)
        )
        
        print("[DASHBOARD] Consumidor de telemetría conectado.")
        
        for message in consumer:
            telemetria = message.value
            cp_id = telemetria.get('cp_id', 'UNKNOWN')
            
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
                
                estado_carga = telemetria.get('estado_carga', telemetria.get('estado', 'DESCONOCIDO'))
                CPS_STATE[cp_id].update({
                    'estado': estado_carga,
                    'ultima_actualizacion': time.time()
                })
            
            # Registrar evento
            registrar_evento(f"Telemetría {cp_id}: {estado_carga}")
            
            # Actualizar estadísticas
            actualizar_estadisticas()
    
    except Exception as e:
        print(f"[DASHBOARD] Error en consumidor de telemetría: {e}")


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
                                    if cp.get('estado', '').upper() in ['ACTIVADO', 'SUMINISTRANDO'])
        STATS['cps_suministrando'] = sum(1 for cp in CPS_STATE.values() 
                                          if cp.get('estado', '').upper() in ['SUMINISTRANDO', 'CARGANDO'])
        STATS['cps_averiados'] = sum(1 for cp in CPS_STATE.values() 
                                      if cp.get('estado', '').upper() in ['AVERIADO', 'AVERÍA'])
        
        # Energía total entregada
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
    
    # Enriquecer con telemetría
    with TELEMETRIA_LOCK:
        for cp in cps_list:
            cp_id = cp['cp_id']
            if cp_id in TELEMETRIA:
                cp['telemetria'] = TELEMETRIA[cp_id]
    
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
                else:
                    cp_info['energia_kwh'] = 0
                    cp_info['potencia_kw'] = 0
                    cp_info['tiempo_carga_s'] = 0
                    cp_info['timestamp_telemetria'] = '-'
            
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
        
        # TODO: Implementar envío real de comando a Central vía socket
        # Por ahora, solo simulamos
        
        registrar_evento(f"Comando {command} enviado a {cp_id}", 'command')
        
        return jsonify({
            'status': 'ok',
            'message': f'Comando {command} enviado a {cp_id}',
            'cp_id': cp_id,
            'command': command
        })
        
    except Exception as e:
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
        .status-parado { background: #ffc107; color: #333; }
        .status-averiado { background: #dc3545; color: white; }
        .status-desconectado { background: #6c757d; color: white; }
        .status-cargando { background: #007bff; color: white; }
        .status-reposo { background: #6c757d; color: white; }
        
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
            html += '</tr></thead><tbody>';
            
            cps.forEach(cp => {
                const tel = cp.telemetria || {};
                const estado = (cp.estado || 'DESCONOCIDO').toUpperCase();
                const estadoClass = 'status-' + estado.toLowerCase().replace('í', 'i');
                
                html += '<tr>';
                html += `<td><strong>${cp.cp_id}</strong></td>`;
                html += `<td><span class="status-badge ${estadoClass}">${estado}</span></td>`;
                html += `<td>${(tel.kw_entregados || tel.energia_total || 0).toFixed(2)}</td>`;
                html += `<td>${(tel.potencia_actual || 0).toFixed(2)}</td>`;
                html += `<td>${tel.tiempo_carga_s || 0}</td>`;
                html += `<td>${tel.timestamp_str || '-'}</td>`;
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
    
    args = parser.parse_args()
    
    # Configurar
    CONFIG['kafka_broker'] = args.kafka
    CONFIG['central_ip'] = args.central_ip
    CONFIG['central_port'] = args.central_port
    
    print("="*70)
    print("  EV CENTRAL - DASHBOARD WEB")
    print("="*70)
    print(f"  Puerto web:    {args.port}")
    print(f"  Kafka:         {args.kafka}")
    print(f"  Central:       {args.central_ip}:{args.central_port}")
    print("="*70)
    print()
    
    # Crear templates
    crear_templates()
    
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


