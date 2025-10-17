import json
import time
from kafka import KafkaProducer
import argparse
from kafka import KafkaProducer

# --- CONFIGURACIÓN ---
KAFKA_SERVER = 'localhost:9092'
TOPIC_REQUESTS = 'driver_requests'

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
    try:
        # Crea el objeto productor de Kafka
        # value_serializer convierte el diccionario a bytes JSON
        producer = KafkaProducer(
            bootstrap_servers=[broker],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

        # Envía el mensaje al topic
        future = producer.send(TOPIC_REQUESTS, value=solicitud)
        
        # Espera a que el envío se complete (opcional, para confirmar la entrega)
        record_metadata = future.get(timeout=10)
        
        print(f"[{solicitud['id_driver']}] Solicitud enviada a Kafka:")
        print(f"  Topic: {record_metadata.topic}, Partition: {record_metadata.partition}, Offset: {record_metadata.offset}")
        print(f"  Datos: {json.dumps(solicitud)}")

        producer.close()
        
    except Exception as e:
        print(f"ERROR al conectar o enviar a Kafka: {e}")
        print("Asegúrate de que tu Broker de Kafka está corriendo en localhost:9092.")

# --- 3. EJECUCIÓN (Simulación del Driver) ---
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='EV Charging Driver Simulator.')
    parser.add_argument('--kafka', type=str, default='localhost:9092', help='Servidores Kafka.')
    parser.add_argument('--id', type=str, required=True, help='ID del conductor (DRIVER_XXX).')
    parser.add_argument('--cp', type=str, required=True, help='ID del punto de carga deseado (CP_XXX).')
    parser.add_argument('--mat', type=str, default='ABC-1234', help='Matrícula del vehículo.')
    parser.add_argument('--kw', type=float, required=True, help='Potencia deseada en kW.')

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
    # Simulación 1: Driver A solicita carga en CP001
    solicitud_A = generar_solicitud(
        id_driver="DRIVER_456",
        id_charging_point="CP_001",
        matricula="ABC-1234",
        kw_deseados=2.0 
    )
    enviar_solicitud(solicitud_A, broker)

    time.sleep(2)

    # Simulación 2: Driver B solicita carga en CP002
    solicitud_B = generar_solicitud(
        id_driver="DRIVER_789",
        id_charging_point="CP_002",
        matricula="DEF-5678",
        kw_deseados=1.0 
    )
    enviar_solicitud(solicitud_B, broker)