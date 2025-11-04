#!/usr/bin/env python3
"""
Script para lanzar múltiples Drivers (EV_Driver) simultáneamente.
Cada Driver solicita servicio a un CP y escucha su ticket.

Uso:
    python launch_multiple_drivers.py --num 8 --kafka 192.168.1.100:9092 --cps 10
"""

import argparse
import subprocess
import time
import sys
import random
from pathlib import Path

def lanzar_driver(driver_num: int, kafka_broker: str, cp_id: str, kw_deseados: float = None):
    """
    Lanza un Driver.
    
    Args:
        driver_num: Número del driver (1, 2, 3, ...)
        kafka_broker: Dirección del broker Kafka
        cp_id: ID del CP al que solicitar servicio
        kw_deseados: kW deseados (aleatorio si es None)
    
    Returns:
        proceso del driver
    """
    driver_id = f"DRIVER_{driver_num:03d}"  # DRIVER_001, DRIVER_002, ...
    
    # kW aleatorios entre 10 y 50 si no se especifica
    if kw_deseados is None:
        kw_deseados = round(random.uniform(10.0, 50.0), 2)
    
    # Matrículas simuladas
    matriculas = [
        f"{random.randint(1000,9999)}-ABC",
        f"{random.randint(1000,9999)}-XYZ",
        f"{random.randint(1000,9999)}-DEF",
        f"{random.randint(1000,9999)}-GHI"
    ]
    matricula = random.choice(matriculas)
    
    print(f"[LAUNCHER] Lanzando {driver_id} -> {cp_id} ({kw_deseados} kWh, mat: {matricula})...")
    
    # Comando para Driver
    driver_cmd = [
        sys.executable,
        "ev_driver/EV_Driver.py",
        "--kafka", kafka_broker,
        "--id", driver_id,
        "--cp", cp_id,
        "--mat", matricula,
        "--kw", str(kw_deseados),
        "--listen"  # Escuchar notificaciones
    ]
    
    try:
        driver_process = subprocess.Popen(
            driver_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        print(f"[LAUNCHER] ✓ {driver_id} lanzado (PID: {driver_process.pid})")
        return driver_process
        
    except Exception as e:
        print(f"[LAUNCHER] ✗ Error lanzando {driver_id}: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Lanzador de múltiples Drivers para pruebas de carga",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Lanzar 5 Drivers aleatorios a 10 CPs disponibles
  python launch_multiple_drivers.py --num 5 --kafka 127.0.0.1:9092 --cps 10
  
  # Lanzar 8 Drivers con distribución uniforme
  python launch_multiple_drivers.py --num 8 --kafka 192.168.1.100:9092 --cps 5 --mode uniform
  
  # Lanzar Drivers con kW específicos
  python launch_multiple_drivers.py --num 3 --kafka 127.0.0.1:9092 --cps 5 --kw 25.5
        """
    )
    
    parser.add_argument("--num", type=int, required=True,
                        help="Número de Drivers a lanzar (ej: 8)")
    parser.add_argument("--kafka", type=str, required=True,
                        help="Broker Kafka (IP:puerto)")
    parser.add_argument("--cps", type=int, required=True,
                        help="Número total de CPs disponibles en la red")
    parser.add_argument("--mode", type=str, choices=['random', 'uniform', 'first'], default='random',
                        help="Modo de asignación de CPs: random (aleatorio), uniform (distribuido), first (todos al CP001)")
    parser.add_argument("--kw", type=float, default=None,
                        help="kW deseados (aleatorio si no se especifica)")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="Delay en segundos entre lanzamientos (default: 0.5)")
    parser.add_argument("--interval", type=float, default=0,
                        help="Intervalo en segundos para lanzamientos escalonados (0 = todos a la vez)")
    
    args = parser.parse_args()
    
    if args.num < 1 or args.num > 100:
        print("ERROR: El número de Drivers debe estar entre 1 y 100")
        sys.exit(1)
    
    if args.cps < 1:
        print("ERROR: Debe haber al menos 1 CP disponible")
        sys.exit(1)
    
    print("="*70)
    print(f"  LANZADOR DE DRIVERS - Sistema de Carga EV")
    print("="*70)
    print(f"  Drivers a lanzar:  {args.num}")
    print(f"  CPs disponibles:   {args.cps} (CP001 - CP{args.cps:03d})")
    print(f"  Kafka:             {args.kafka}")
    print(f"  Modo asignación:   {args.mode}")
    print(f"  kW por solicitud:  {'Aleatorio (10-50)' if args.kw is None else args.kw}")
    print("="*70)
    print()
    
    # Verificar que existe el archivo
    if not Path("ev_driver/EV_Driver.py").exists():
        print("ERROR: No se encuentra ev_driver/EV_Driver.py")
        sys.exit(1)
    
    # Lista para almacenar procesos
    procesos = []
    
    # Generar asignaciones de CPs según el modo
    if args.mode == 'random':
        # Aleatorio
        cp_assignments = [f"CP{random.randint(1, args.cps):03d}" for _ in range(args.num)]
    elif args.mode == 'uniform':
        # Distribuir uniformemente (round-robin)
        cp_assignments = [f"CP{(i % args.cps) + 1:03d}" for i in range(args.num)]
    else:  # first
        # Todos al primer CP (prueba de saturación)
        cp_assignments = ["CP001"] * args.num
    
    try:
        # Lanzar cada Driver
        for i in range(args.num):
            cp_id = cp_assignments[i]
            
            driver_process = lanzar_driver(
                driver_num=i + 1,
                kafka_broker=args.kafka,
                cp_id=cp_id,
                kw_deseados=args.kw
            )
            
            if driver_process:
                procesos.append((i + 1, driver_process, cp_id))
            else:
                print(f"[LAUNCHER] ⚠️  DRIVER_{i+1:03d} no pudo lanzarse")
            
            # Delay entre lanzamientos
            if i < args.num - 1:
                time.sleep(args.delay)
        
        print()
        print("="*70)
        print(f"✓ {len(procesos)} Drivers lanzados exitosamente")
        print("="*70)
        print()
        print("Asignaciones:")
        
        # Mostrar estadísticas de asignación
        from collections import Counter
        stats = Counter([cp for _, _, cp in procesos])
        for cp, count in sorted(stats.items()):
            barra = "█" * count
            print(f"  {cp}: {barra} ({count} drivers)")
        
        print()
        print("Procesos activos:")
        for driver_num, process, cp in procesos:
            print(f"  DRIVER_{driver_num:03d} -> {cp} (PID: {process.pid})")
        
        print()
        print("Los Drivers se detendrán automáticamente tras recibir su ticket.")
        print("Presiona Ctrl+C para forzar detención inmediata...")
        print()
        
        # Mantener el script vivo y monitorear procesos
        drivers_activos = len(procesos)
        while drivers_activos > 0:
            time.sleep(2)
            
            # Contar cuántos siguen vivos
            drivers_activos = 0
            for driver_num, process, cp in procesos:
                if process.poll() is None:
                    drivers_activos += 1
            
            if drivers_activos > 0:
                print(f"\r[LAUNCHER] Drivers activos: {drivers_activos}/{len(procesos)}  ", end='', flush=True)
        
        print("\n[LAUNCHER] Todos los Drivers han completado su ciclo.")
    
    except KeyboardInterrupt:
        print("\n[LAUNCHER] Señal de interrupción recibida. Cerrando todos los Drivers...")
        
        # Terminar todos los procesos
        for driver_num, process, cp in procesos:
            try:
                if process.poll() is None:
                    print(f"[LAUNCHER] Deteniendo DRIVER_{driver_num:03d}...")
                    process.terminate()
                    time.sleep(0.2)
                    if process.poll() is None:
                        process.kill()
            except Exception as e:
                print(f"[LAUNCHER] Error deteniendo DRIVER_{driver_num:03d}: {e}")
        
        print("[LAUNCHER] Todos los Drivers detenidos.")
        sys.exit(0)
    
    except Exception as e:
        print(f"[LAUNCHER] Error crítico: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()



