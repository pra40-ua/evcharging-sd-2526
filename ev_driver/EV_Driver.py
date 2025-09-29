import argparse

def main():
    parser = argparse.ArgumentParser(description="Proceso EV_Driver (Cliente/Conductor)")
    parser.add_argument("--kafka", type=str, required=True, help="Broker Kafka (IP:puerto)")
    parser.add_argument("--driver_id", type=str, required=True, help="Identificador del conductor")
    parser.add_argument("--file", type=str, help="Ruta a fichero de peticiones del conductor")
    args = parser.parse_args()

    print("="*40)
    print("[EV_Driver] INICIADO")
    print(f"Broker Kafka: {args.kafka}")
    print(f"ID del conductor: {args.driver_id}")
    if args.file:
        print(f"Archivo de peticiones: {args.file}")
    print("="*40)

if __name__ == "__main__":
    main()