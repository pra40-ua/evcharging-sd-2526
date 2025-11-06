import json
import time
import sys
from kafka import KafkaProducer, KafkaConsumer
import argparse

# --- CONFIGURACIÓN ---
KAFKA_SERVER = 'localhost:9092'
TOPIC_REQUESTS = 'driver_requests'
EVENT_PREFIX = 'driver_status_'

# --- 1. DEFINICIÓN DEL MENSAJE (Estructura de la Solicitud) ---
def generar_solicitud(id_driver, id_charging_point, matricula, kw_deseados):
    """
    Crea un diccionario con los datos de la solicitud de carga.
    """
    solicitud = {
        'id_driver': id_driver,
        'id_charging_point': id_charging_point,
        'matricula': matricula,
        'kw_deseados': kw_deseados,
        'timestamp_solicitud': time.time()
    }
    return solicitud

# --- 2. FUNCIÓN PRODUCTORA ---
def enviar_solicitud(solicitud, broker):
    """
    Envía la solicitud de carga al broker Kafka con reintentos en caso de error.
    """
    for intento in range(3):
        try:
            producer = KafkaProducer(
                bootstrap_servers=[broker],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                api_version=(2, 8, 0)
            )
            producer.send(TOPIC_REQUESTS, value=solicitud)
            producer.flush()
            print(f"[{solicitud['id_driver']}] ✓ Solicitud enviada correctamente (intento {intento+1})")
            cp_solicitado = solicitud.get('id_charging_point', '?')
            print(f"[DRIVER {solicitud['id_driver']}] 📡 Esperando respuesta de la Central para {cp_solicitado}...")
            producer.close()
            break
        except Exception as e:
            print(f"ERROR enviando a Kafka (intento {intento+1}/3): {e}")
            if intento < 2:
                time.sleep(2)

def consumir_notificaciones_driver(driver_id: str, broker: str, procesar_ticket_callback=None, leer_desde_inicio=False):
    """Escucha el tópico driver_status_<driver_id> y muestra mensajes, incluyendo TICKET_FINAL.
    
    Args:
        driver_id: ID del driver
        broker: Broker de Kafka
        procesar_ticket_callback: Función para procesar tickets
        leer_desde_inicio: Si True, lee desde el principio del topic para recuperar mensajes perdidos
    """
    topic = f"{EVENT_PREFIX}{driver_id}"
    try:
        # Si leer_desde_inicio es True, usar 'earliest' para leer todos los mensajes pendientes
        # Esto permite recuperar tickets que se enviaron mientras el driver estaba desconectado
        offset_reset = 'earliest' if leer_desde_inicio else 'latest'
        
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=[broker],
            auto_offset_reset=offset_reset,
            enable_auto_commit=True,
            group_id=f'driver-{driver_id}-group',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            api_version=(2, 8, 0),
            consumer_timeout_ms=5000 if leer_desde_inicio else None  # Timeout para leer mensajes antiguos
        )
        
        if leer_desde_inicio:
            print(f"[DRIVER {driver_id}] 🔄 Recuperando mensajes pendientes desde el principio del topic '{topic}'...")
            # Leer todos los mensajes pendientes primero
            mensajes_pendientes = []
            try:
                for msg in consumer:
                    mensajes_pendientes.append(msg.value)
            except Exception:
                pass  # Timeout esperado cuando no hay más mensajes
            
            if mensajes_pendientes:
                print(f"[DRIVER {driver_id}] 📨 Se encontraron {len(mensajes_pendientes)} mensaje(s) pendiente(s)")
                # Procesar mensajes pendientes en orden
                for payload in mensajes_pendientes:
                    evento = payload.get('evento')
                    detalle = payload.get('detalle')
                    ts = payload.get('timestamp')
                    print(f"[DRIVER {driver_id}] [PENDIENTE] Evento={evento} @ {ts} -> {detalle}")
                    
                    if evento == 'TICKET_FINAL':
                        # Procesar ticket pendiente
                        if procesar_ticket_callback:
                            try:
                                procesar_ticket_callback(detalle)
                            except Exception as e:
                                print(f"[DRIVER {driver_id}] Error procesando ticket pendiente: {e}")
                        print(f"[DRIVER {driver_id}] ✅ Ticket pendiente procesado. Terminando proceso.")
                        consumer.close()
                        return True
            else:
                print(f"[DRIVER {driver_id}] ✓ No hay mensajes pendientes")
            
            # Cerrar el consumer anterior y crear uno nuevo para escuchar mensajes nuevos
            consumer.close()
            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=[broker],
                auto_offset_reset='latest',
                enable_auto_commit=True,
                group_id=f'driver-{driver_id}-group',
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                api_version=(2, 8, 0)
            )
        
        print(f"[DRIVER {driver_id}] Escuchando notificaciones en '{topic}'...")
        for msg in consumer:
            payload = msg.value
            evento = payload.get('evento')
            detalle = payload.get('detalle')
            ts = payload.get('timestamp')
            print(f"[DRIVER {driver_id}] Evento={evento} @ {ts} -> {detalle}")
            if evento == 'RECIBIDA':
                print(f"[DRIVER {driver_id}] Solicitud recibida por Central. Validando CP...")
            elif evento == 'CP_REASIGNADO':
                cp_original = detalle.get('cp_id_original', '?')
                cp_nuevo = detalle.get('cp_id_nuevo', '?')
                mensaje = detalle.get('mensaje', '')
                print(f"[DRIVER {driver_id}] 🔄 {mensaje}")
                print(f"[DRIVER {driver_id}] CP reasignado: {cp_original} → {cp_nuevo}")
            elif evento == 'AUTORIZADO':
                cp_id = detalle.get('cp_id', '?')
                print(f"[DRIVER {driver_id}] ✅ Autorizado por Central para {cp_id}!")
                print(f"[DRIVER {driver_id}] Iniciando sesión de carga...")
            elif evento == 'AUTORIZACION_EN_PROCESO':
                print(f"[DRIVER {driver_id}] ⏳ Autorizando... {detalle.get('mensaje', '')}")
            elif evento == 'DENEGADA':
                print(f"[DRIVER {driver_id}] Solicitud denegada: {detalle}")
                print(f"[DRIVER {driver_id}] ❌ Terminando proceso (solicitud denegada).")
                consumer.close()
                return False  # Retornar False para indicar fallo
            elif evento == 'TICKET_FINAL':
                # Procesar ticket y TERMINAR el driver
                if procesar_ticket_callback:
                    try:
                        procesar_ticket_callback(detalle)
                    except Exception as e:
                        print(f"[DRIVER {driver_id}] Error procesando ticket: {e}")
                print(f"[DRIVER {driver_id}] ✅ Ticket recibido. Terminando proceso.")
                consumer.close()
                return True  # Retornar True para indicar éxito
    except Exception as e:
        print(f"[DRIVER {driver_id}] Error consumiendo notificaciones: {e}")
        return False

# --- 3. EJECUCIÓN (Simulación del Driver) ---
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='EV Charging Driver Simulator.')
    parser.add_argument('--kafka', type=str, default='localhost:9092', help='Servidores Kafka.')
    parser.add_argument('--id', type=str, required=True, help='ID del conductor (DRIVER_XXX).')
    parser.add_argument('--cp', type=str, required=True, help='ID del punto de carga deseado (CP_XXX).')
    parser.add_argument('--mat', type=str, default='ABC-1234', help='Matrícula del vehículo.')
    parser.add_argument('--kw', type=float, required=True, help='Potencia deseada en kW.')
    parser.add_argument('--listen', action='store_true', help='Escuchar tickets/notificaciones del driver')

    args = parser.parse_args()

    # Broker a utilizar (de argumentos o por defecto)
    broker = args.kafka or KAFKA_SERVER

    solicitud = generar_solicitud(
        id_driver=args.id,
        id_charging_point=args.cp,
        matricula=args.mat,
        kw_deseados=args.kw
    )
    
    enviar_solicitud(solicitud, broker)

    if args.listen:
        def mostrar_ticket(ticket):
            """Procesa y muestra el ticket final."""
            try:
                cp = ticket.get('cp_id')
                energia = ticket.get('energia_kwh')
                importe = ticket.get('importe_eur')
                duracion = ticket.get('duracion_seg', 'N/D')
                tx_id = ticket.get('tx_id', 'N/D')
                
                print("\n" + "="*60)
                print(f"           🧾 TICKET FINAL - DRIVER {args.id}")
                print("="*60)
                print(f"  Punto de Carga:  {cp}")
                print(f"  Energía:         {energia} kWh")
                print(f"  Importe:         {importe} €")
                print(f"  Duración:        {duracion} segundos")
                print(f"  ID Transacción:  {tx_id}")
                print(f"  Fecha/Hora:      {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print("="*60)
                
                # Guardar en archivo
                with open("tickets_driver.txt", "a", encoding="utf-8") as f:
                    f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | Driver={args.id} | CP={cp} | Energía={energia} kWh | Importe={importe} € | TX={tx_id}\n")
                
                print(f"\n[DRIVER {args.id}] ✅ Ticket guardado en 'tickets_driver.txt'")
            except Exception as e:
                print(f"[DRIVER {args.id}] Error mostrando ticket: {e}")
                print(f"[DRIVER {args.id}] Ticket raw: {ticket}")

        # Consumir notificaciones hasta recibir el ticket (o error)
        # Leer desde el principio para recuperar mensajes perdidos si el driver se desconectó
        exito = consumir_notificaciones_driver(args.id, broker, procesar_ticket_callback=mostrar_ticket, leer_desde_inicio=True)
        
        # Terminar con código de salida apropiado
        if exito:
            print(f"\n[DRIVER {args.id}] 🚗 Servicio completado exitosamente. Adiós!\n")
            sys.exit(0)
        else:
            print(f"\n[DRIVER {args.id}] ❌ Servicio no completado.\n")
            sys.exit(1)
    else:
        print(f"[DRIVER {args.id}] Solicitud enviada. Use --listen para recibir el ticket.")
        sys.exit(0)