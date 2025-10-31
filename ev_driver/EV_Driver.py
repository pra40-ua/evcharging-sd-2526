import json
import time
from kafka import KafkaProducer, KafkaConsumer
import argparse
from kafka import KafkaProducer

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
    for intento in range(3):
        try:
            producer = KafkaProducer(
                bootstrap_servers=[broker],
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            producer.send(TOPIC_REQUESTS, value=solicitud)
            producer.flush()
            print(f"[{solicitud['id_driver']}] Solicitud enviada correctamente (intento {intento+1})")
            print(f"[DRIVER {solicitud['id_driver']}] Esperando respuesta de la Central...")
            producer.close()
            break
        except Exception as e:
            print(f"ERROR enviando a Kafka (intento {intento+1}/3): {e}")
            time.sleep(2)

def consumir_notificaciones_driver(driver_id: str, broker: str, procesar_ticket_callback=None):
    """Escucha el tópico driver_status_<driver_id> y muestra mensajes, incluyendo TICKET_FINAL."""
    topic = f"{EVENT_PREFIX}{driver_id}"
    try:
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=[broker],
            auto_offset_reset='latest',
            enable_auto_commit=True,
            group_id=f'driver-{driver_id}-group',
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
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
            elif evento == 'AUTORIZADO':
                print(f"[DRIVER {driver_id}] Autorizado por Central. Iniciando sesión de carga...")
            elif evento == 'DENEGADA':
                print(f"[DRIVER {driver_id}] Solicitud denegada: {detalle}")
            if evento == 'TICKET_FINAL' and procesar_ticket_callback:
                try:
                    procesar_ticket_callback(detalle)
                except Exception:
                    pass
    except Exception as e:
        print(f"[DRIVER {driver_id}] Error consumiendo notificaciones: {e}")

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
            try:
                cp = ticket.get('cp_id')
                energia = ticket.get('energia_kwh')
                importe = ticket.get('importe_eur')
                print(f"[DRIVER {args.id}] Ticket final: CP={cp}, E={energia} kWh, €={importe}")
                with open("tickets_driver.txt", "a", encoding="utf-8") as f:
                    f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | Driver={args.id} | CP={cp} | Energía={energia} kWh | Importe={importe} €\n")
            except Exception:
                print(f"[DRIVER {args.id}] Ticket final: {ticket}")
            # Si estuviera procesando por fichero, esperar 4s y continuar
            time.sleep(4)
            print(f"[DRIVER {args.id}] Listo para solicitar siguiente servicio (si procede).")

        consumir_notificaciones_driver(args.id, broker, procesar_ticket_callback=mostrar_ticket)