import argparse

def main():
    parser = argparse.ArgumentParser(description="Proceso EV_CP_E (Charging Point Engine)")
    parser.add_argument("--kafka", type=str, required=True, help="Broker Kafka (IP:puerto)")
    parser.add_argument("--monitor_ip", type=str, required=True, help="IP del monitor asociado")
    parser.add_argument("--monitor_port", type=int, required=True, help="Puerto del monitor asociado")
    args = parser.parse_args()

    print("="*40)
    print("[EV_CP_E] INICIADO")
    print(f"Broker Kafka: {args.kafka}")
    print(f"Monitor en: {args.monitor_ip}:{args.monitor_port}")
    print("="*40)

if __name__ == "__main__":
    main()