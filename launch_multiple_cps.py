#!/usr/bin/env python3
"""
Script para lanzar múltiples Puntos de Recarga (CPs) simultáneamente.
Cada CP consiste en un Engine (EV_CP_E) y un Monitor (EV_CP_M).

Uso:
    python launch_multiple_cps.py --num 10 --central-ip 192.168.1.100 --kafka 192.168.1.100:9092
"""

import argparse
import subprocess
import time
import sys
import os
from pathlib import Path

def lanzar_cp(cp_num: int, central_ip: str, central_port: int, kafka_broker: str, base_engine_port: int = 6000):
    """
    Lanza un CP completo (Engine + Monitor).
    
    Args:
        cp_num: Número del CP (1, 2, 3, ...)
        central_ip: IP de la Central
        central_port: Puerto de la Central
        kafka_broker: Dirección del broker Kafka
        base_engine_port: Puerto base para los Engines (cada uno usa base + cp_num)
    
    Returns:
        tuple: (proceso_engine, proceso_monitor)
    """
    cp_id = f"CP{cp_num:03d}"  # CP001, CP002, ..., CP010
    engine_port = base_engine_port + cp_num
    
    print(f"[LAUNCHER] Lanzando {cp_id} (Engine en puerto {engine_port})...")
    
    # Comando para Engine
    engine_cmd = [
        sys.executable,  # Python actual
        "ev_cp_engine/EV_CP_E.py",
        "--port", str(engine_port),
        "--cp-id", cp_id,
        "--kafka", kafka_broker
    ]
    
    # Comando para Monitor
    monitor_cmd = [
        sys.executable,
        "ev_cp_monitor/EV_CP_M.py",
        "--cp_id", cp_id,
        "--central_ip", central_ip,
        "--central_port", str(central_port),
        "--engine_ip", "127.0.0.1",  # Engine local
        "--engine_port", str(engine_port)
    ]
    
    try:
        # Lanzar Engine
        engine_process = subprocess.Popen(
            engine_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        print(f"[LAUNCHER] ✓ Engine {cp_id} lanzado (PID: {engine_process.pid})")
        
        # Esperar brevemente para que el Engine esté listo
        time.sleep(0.5)
        
        # Lanzar Monitor
        monitor_process = subprocess.Popen(
            monitor_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        print(f"[LAUNCHER] ✓ Monitor {cp_id} lanzado (PID: {monitor_process.pid})")
        
        # Esperar un poco para que se registre
        time.sleep(0.3)
        
        return (engine_process, monitor_process)
        
    except Exception as e:
        print(f"[LAUNCHER] ✗ Error lanzando {cp_id}: {e}")
        return (None, None)


def main():
    parser = argparse.ArgumentParser(
        description="Lanzador de múltiples CPs para pruebas de escalabilidad",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Lanzar 5 CPs conectados a Central local
  python launch_multiple_cps.py --num 5 --central-ip 127.0.0.1 --kafka 127.0.0.1:9092
  
  # Lanzar 10 CPs conectados a Central remota
  python launch_multiple_cps.py --num 10 --central-ip 192.168.1.100 --kafka 192.168.1.100:9092 --base-port 6000
        """
    )
    
    parser.add_argument("--num", type=int, required=True, 
                        help="Número de CPs a lanzar (ej: 10)")
    parser.add_argument("--central-ip", type=str, required=True,
                        help="IP de EV_Central")
    parser.add_argument("--central-port", type=int, default=5000,
                        help="Puerto de EV_Central (default: 5000)")
    parser.add_argument("--kafka", type=str, required=True,
                        help="Broker Kafka (IP:puerto)")
    parser.add_argument("--base-port", type=int, default=6000,
                        help="Puerto base para Engines (default: 6000)")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Delay en segundos entre lanzamientos (default: 1.0)")
    
    args = parser.parse_args()
    
    if args.num < 1 or args.num > 100:
        print("ERROR: El número de CPs debe estar entre 1 y 100")
        sys.exit(1)
    
    print("="*70)
    print(f"  LANZADOR DE CPs - Sistema de Carga EV")
    print("="*70)
    print(f"  CPs a lanzar:    {args.num}")
    print(f"  Central:         {args.central_ip}:{args.central_port}")
    print(f"  Kafka:           {args.kafka}")
    print(f"  Puertos Engine:  {args.base_port} - {args.base_port + args.num}")
    print("="*70)
    print()
    
    # Verificar que existen los archivos
    if not Path("ev_cp_engine/EV_CP_E.py").exists():
        print("ERROR: No se encuentra ev_cp_engine/EV_CP_E.py")
        sys.exit(1)
    if not Path("ev_cp_monitor/EV_CP_M.py").exists():
        print("ERROR: No se encuentra ev_cp_monitor/EV_CP_M.py")
        sys.exit(1)
    
    # Lista para almacenar procesos
    procesos = []
    
    try:
        # Lanzar cada CP
        for i in range(1, args.num + 1):
            engine, monitor = lanzar_cp(
                cp_num=i,
                central_ip=args.central_ip,
                central_port=args.central_port,
                kafka_broker=args.kafka,
                base_engine_port=args.base_port
            )
            
            if engine and monitor:
                procesos.append((i, engine, monitor))
            else:
                print(f"[LAUNCHER] ⚠️  CP{i:03d} no pudo lanzarse correctamente")
            
            # Delay entre lanzamientos para evitar saturación
            if i < args.num:
                time.sleep(args.delay)
        
        print()
        print("="*70)
        print(f"✓ {len(procesos)} CPs lanzados exitosamente")
        print("="*70)
        print()
        print("Procesos activos:")
        for cp_num, engine, monitor in procesos:
            print(f"  CP{cp_num:03d}: Engine PID={engine.pid}, Monitor PID={monitor.pid}")
        print()
        print("Presiona Ctrl+C para detener todos los CPs...")
        print()
        
        # Mantener el script vivo y monitorear procesos
        while True:
            time.sleep(2)
            
            # Verificar si algún proceso murió
            for cp_num, engine, monitor in procesos:
                if engine.poll() is not None:
                    print(f"⚠️  Engine CP{cp_num:03d} terminó (código: {engine.returncode})")
                if monitor.poll() is not None:
                    print(f"⚠️  Monitor CP{cp_num:03d} terminó (código: {monitor.returncode})")
    
    except KeyboardInterrupt:
        print("\n[LAUNCHER] Señal de interrupción recibida. Cerrando todos los CPs...")
        
        # Terminar todos los procesos
        for cp_num, engine, monitor in procesos:
            try:
                print(f"[LAUNCHER] Deteniendo CP{cp_num:03d}...")
                monitor.terminate()
                engine.terminate()
                
                # Esperar un poco
                time.sleep(0.5)
                
                # Forzar si no respondieron
                if monitor.poll() is None:
                    monitor.kill()
                if engine.poll() is None:
                    engine.kill()
                    
            except Exception as e:
                print(f"[LAUNCHER] Error deteniendo CP{cp_num:03d}: {e}")
        
        print("[LAUNCHER] Todos los CPs detenidos.")
        sys.exit(0)
    
    except Exception as e:
        print(f"[LAUNCHER] Error crítico: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()




