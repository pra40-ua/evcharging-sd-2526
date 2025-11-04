#!/usr/bin/env python3
"""
Script de diagnóstico para verificar el estado del Dashboard y la conexión con Kafka.
"""

import sys
import json
import requests
from kafka import KafkaConsumer, KafkaProducer, KafkaAdminClient
from kafka.admin import NewTopic
import time

def verificar_dashboard(url="http://localhost:8080"):
    """Verifica que el dashboard esté respondiendo."""
    print("\n" + "="*70)
    print("1. VERIFICANDO DASHBOARD WEB")
    print("="*70)
    
    try:
        response = requests.get(f"{url}/api/debug", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Dashboard respondiendo correctamente")
            print(f"  - CPs en estado: {data.get('num_cps', 0)}")
            print(f"  - Telemetría recibida: {data.get('num_telemetria', 0)}")
            print(f"  - BD configurada: {data.get('config', {}).get('db_configured', False)}")
            print(f"  - Kafka broker: {data.get('config', {}).get('kafka_broker', 'N/D')}")
            
            if data.get('num_cps', 0) > 0:
                print(f"\n  CPs detectados:")
                for cp_id, cp_data in data.get('cps_state', {}).items():
                    print(f"    - {cp_id}: {cp_data.get('estado', 'N/D')}")
            else:
                print(f"\n  ⚠ No hay CPs detectados en el dashboard")
            
            return True
        else:
            print(f"✗ Dashboard respondió con código: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"✗ No se puede conectar al dashboard en {url}")
        print(f"  Asegúrate de que el dashboard esté ejecutándose")
        return False
    except Exception as e:
        print(f"✗ Error verificando dashboard: {e}")
        return False


def verificar_kafka(broker="localhost:9092"):
    """Verifica la conexión con Kafka y lista los topics."""
    print("\n" + "="*70)
    print("2. VERIFICANDO KAFKA")
    print("="*70)
    
    try:
        # Verificar topics existentes
        admin = KafkaAdminClient(bootstrap_servers=[broker])
        topics = admin.list_topics()
        
        print(f"✓ Conectado a Kafka en {broker}")
        print(f"  Topics disponibles ({len(topics)}):")
        
        for topic in sorted(topics):
            print(f"    - {topic}")
        
        # Verificar topic de telemetría
        if 'telemetria_cp' in topics:
            print(f"\n  ✓ Topic 'telemetria_cp' existe")
        else:
            print(f"\n  ✗ Topic 'telemetria_cp' NO existe")
            return False
        
        admin.close()
        return True
        
    except Exception as e:
        print(f"✗ Error conectando a Kafka: {e}")
        return False


def escuchar_telemetria(broker="localhost:9092", timeout_seg=10):
    """Escucha el topic de telemetría por unos segundos."""
    print("\n" + "="*70)
    print(f"3. ESCUCHANDO TELEMETRÍA (por {timeout_seg} segundos)")
    print("="*70)
    
    try:
        consumer = KafkaConsumer(
            'telemetria_cp',
            bootstrap_servers=[broker],
            auto_offset_reset='latest',
            group_id='diagnostico-temp-group',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            consumer_timeout_ms=timeout_seg * 1000
        )
        
        print(f"✓ Consumidor conectado al topic 'telemetria_cp'")
        print(f"  Esperando mensajes por {timeout_seg} segundos...")
        print(f"  (Si hay CPs conectados, deberían enviar heartbeats cada ~10 segundos)")
        print()
        
        mensaje_count = 0
        cps_vistos = set()
        
        for message in consumer:
            mensaje_count += 1
            telemetria = message.value
            cp_id = telemetria.get('cp_id', 'UNKNOWN')
            estado = telemetria.get('estado', telemetria.get('estado_carga', 'N/D'))
            
            cps_vistos.add(cp_id)
            print(f"  → Mensaje #{mensaje_count}: CP={cp_id}, Estado={estado}")
        
        consumer.close()
        
        if mensaje_count > 0:
            print(f"\n✓ Se recibieron {mensaje_count} mensaje(s) de telemetría")
            print(f"  CPs detectados: {', '.join(sorted(cps_vistos))}")
            return True
        else:
            print(f"\n⚠ NO se recibieron mensajes de telemetría")
            print(f"  Posibles causas:")
            print(f"    - No hay CPs conectados al Central")
            print(f"    - El Central no está publicando telemetría")
            print(f"    - El Central no tiene Kafka Producer configurado")
            return False
        
    except Exception as e:
        print(f"✗ Error escuchando telemetría: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print()
    print("╔" + "="*68 + "╗")
    print("║" + " "*10 + "DIAGNÓSTICO DEL DASHBOARD EV_CENTRAL" + " "*22 + "║")
    print("╚" + "="*68 + "╝")
    
    # Obtener parámetros
    dashboard_url = input("\nURL del Dashboard [http://localhost:8080]: ").strip() or "http://localhost:8080"
    kafka_broker = input("Kafka Broker [localhost:9092]: ").strip() or "localhost:9092"
    
    # Ejecutar diagnósticos
    dashboard_ok = verificar_dashboard(dashboard_url)
    kafka_ok = verificar_kafka(kafka_broker)
    telemetria_ok = escuchar_telemetria(kafka_broker, timeout_seg=15)
    
    # Resumen
    print("\n" + "="*70)
    print("RESUMEN DEL DIAGNÓSTICO")
    print("="*70)
    print(f"  Dashboard Web:     {'✓ OK' if dashboard_ok else '✗ FALLÓ'}")
    print(f"  Kafka:             {'✓ OK' if kafka_ok else '✗ FALLÓ'}")
    print(f"  Telemetría:        {'✓ OK' if telemetria_ok else '✗ NO SE RECIBIÓ'}")
    print()
    
    if not telemetria_ok:
        print("RECOMENDACIONES:")
        print("  1. Verifica que EV_Central esté ejecutándose")
        print("  2. Verifica que haya CPs (Monitor + Engine) conectados")
        print("  3. Verifica los logs de EV_Central para ver si publica telemetría")
        print("  4. Ejecuta: docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic telemetria_cp --from-beginning")
        print()
    
    if dashboard_ok and kafka_ok and telemetria_ok:
        print("✓ Todo funciona correctamente. El dashboard debería mostrar los CPs.")
        print("  Si no los ves, intenta:")
        print("    1. Refrescar la página del navegador (Ctrl+F5)")
        print("    2. Verificar la consola del navegador (F12) por errores JavaScript")
        print()
    
    input("Presiona Enter para salir...")


if __name__ == "__main__":
    main()

