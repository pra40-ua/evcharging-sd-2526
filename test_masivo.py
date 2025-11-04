#!/usr/bin/env python3
"""
Script de prueba masiva del sistema EV Charging.
Lanza Central, Dashboard, múltiples CPs y múltiples Drivers para verificar escalabilidad.

Uso:
    python test_masivo.py --cps 10 --drivers 8
"""

import argparse
import subprocess
import time
import sys
import os
from pathlib import Path

def verificar_requisitos():
    """Verifica que todos los archivos necesarios existan."""
    archivos_requeridos = [
        'ev_central/EV_Central.py',
        'ev_cp_engine/EV_CP_E.py',
        'ev_cp_monitor/EV_CP_M.py',
        'ev_driver/EV_Driver.py',
        'web_dashboard.py',
        'launch_multiple_cps.py',
        'launch_multiple_drivers.py'
    ]
    
    faltantes = []
    for archivo in archivos_requeridos:
        if not Path(archivo).exists():
            faltantes.append(archivo)
    
    if faltantes:
        print("ERROR: Faltan los siguientes archivos:")
        for f in faltantes:
            print(f"  - {f}")
        return False
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Prueba masiva del sistema EV Charging",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Este script lanza automáticamente:
  1. EV_Central (servidor principal)
  2. Dashboard Web (interfaz visual)
  3. N Puntos de Recarga (cada uno con Engine + Monitor)
  4. M Drivers (clientes que solicitan servicio)

Ejemplo:
  python test_masivo.py --cps 10 --drivers 8 --kafka 127.0.0.1:9092

Accede al dashboard en: http://localhost:8080
        """
    )
    
    parser.add_argument("--cps", type=int, default=5,
                        help="Número de Puntos de Carga a lanzar (default: 5)")
    parser.add_argument("--drivers", type=int, default=3,
                        help="Número de Drivers a lanzar (default: 3)")
    parser.add_argument("--kafka", type=str, default="127.0.0.1:9092",
                        help="Broker Kafka (default: 127.0.0.1:9092)")
    parser.add_argument("--db", type=str, default="127.0.0.1:3306:root::evcharging",
                        help="Configuración de BD (default: 127.0.0.1:3306:root::evcharging)")
    parser.add_argument("--central-port", type=int, default=5000,
                        help="Puerto de Central (default: 5000)")
    parser.add_argument("--dashboard-port", type=int, default=8080,
                        help="Puerto del dashboard web (default: 8080)")
    parser.add_argument("--delay-drivers", type=int, default=10,
                        help="Segundos de espera antes de lanzar drivers (default: 10)")
    parser.add_argument("--no-dashboard", action="store_true",
                        help="No lanzar el dashboard web")
    
    args = parser.parse_args()
    
    print("="*80)
    print("  PRUEBA MASIVA - SISTEMA EV CHARGING")
    print("="*80)
    print(f"  Configuración:")
    print(f"    - Puntos de Carga: {args.cps}")
    print(f"    - Drivers:         {args.drivers}")
    print(f"    - Kafka:           {args.kafka}")
    print(f"    - Central:         127.0.0.1:{args.central_port}")
    print(f"    - Dashboard:       http://localhost:{args.dashboard_port}")
    print(f"    - Base de Datos:   {args.db}")
    print("="*80)
    print()
    
    # Verificar requisitos
    if not verificar_requisitos():
        sys.exit(1)
    
    procesos = []
    
    try:
        # ===== PASO 1: Lanzar EV_Central =====
        print("[1/5] Lanzando EV_Central...")
        central_cmd = [
            sys.executable,
            "ev_central/EV_Central.py",
            "--port", str(args.central_port),
            "--kafka", args.kafka,
            "--db", args.db
        ]
        
        central_process = subprocess.Popen(
            central_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        procesos.append(("Central", central_process))
        print(f"      ✓ Central lanzada (PID: {central_process.pid})")
        
        # Esperar a que Central esté lista
        print("      Esperando a que Central esté lista...")
        time.sleep(3)
        
        # ===== PASO 2: Lanzar Dashboard Web (opcional) =====
        if not args.no_dashboard:
            print("\n[2/5] Lanzando Dashboard Web...")
            dashboard_cmd = [
                sys.executable,
                "web_dashboard.py",
                "--port", str(args.dashboard_port),
                "--kafka", args.kafka,
                "--central-ip", "127.0.0.1",
                "--central-port", str(args.central_port)
            ]
            
            dashboard_process = subprocess.Popen(
                dashboard_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            procesos.append(("Dashboard", dashboard_process))
            print(f"      ✓ Dashboard lanzado (PID: {dashboard_process.pid})")
            print(f"      📊 Accede en: http://localhost:{args.dashboard_port}")
            time.sleep(2)
        else:
            print("\n[2/5] Dashboard deshabilitado (--no-dashboard)")
        
        # ===== PASO 3: Lanzar Puntos de Recarga =====
        print(f"\n[3/5] Lanzando {args.cps} Puntos de Recarga...")
        cps_cmd = [
            sys.executable,
            "launch_multiple_cps.py",
            "--num", str(args.cps),
            "--central-ip", "127.0.0.1",
            "--central-port", str(args.central_port),
            "--kafka", args.kafka,
            "--base-port", "6000",
            "--delay", "0.8"
        ]
        
        cps_process = subprocess.Popen(
            cps_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        procesos.append(("CPs", cps_process))
        print(f"      ✓ Launcher de CPs iniciado (PID: {cps_process.pid})")
        
        # Esperar a que todos los CPs se registren
        tiempo_espera_cps = max(5, args.cps * 0.8 + 2)
        print(f"      Esperando {tiempo_espera_cps:.1f}s a que los CPs se registren...")
        time.sleep(tiempo_espera_cps)
        
        # ===== PASO 4: Esperar antes de lanzar Drivers =====
        print(f"\n[4/5] Sistema estabilizado. Esperando {args.delay_drivers}s antes de lanzar Drivers...")
        for i in range(args.delay_drivers, 0, -1):
            print(f"      {i}s...", end='\r', flush=True)
            time.sleep(1)
        print("      ¡Lanzando Drivers!")
        
        # ===== PASO 5: Lanzar Drivers =====
        print(f"\n[5/5] Lanzando {args.drivers} Drivers...")
        drivers_cmd = [
            sys.executable,
            "launch_multiple_drivers.py",
            "--num", str(args.drivers),
            "--kafka", args.kafka,
            "--cps", str(args.cps),
            "--mode", "random",  # Distribución aleatoria
            "--delay", "1.0"
        ]
        
        drivers_process = subprocess.Popen(
            drivers_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        procesos.append(("Drivers", drivers_process))
        print(f"      ✓ Launcher de Drivers iniciado (PID: {drivers_process.pid})")
        
        # ===== Sistema Lanzado =====
        print("\n" + "="*80)
        print("  ✓ SISTEMA COMPLETAMENTE LANZADO")
        print("="*80)
        print()
        print("  Componentes activos:")
        for nombre, proceso in procesos:
            print(f"    - {nombre:<12} (PID: {proceso.pid})")
        print()
        if not args.no_dashboard:
            print(f"  📊 Dashboard: http://localhost:{args.dashboard_port}")
        print(f"  ⚡ CPs:       {args.cps} puntos de recarga")
        print(f"  🚗 Drivers:   {args.drivers} clientes activos")
        print()
        print("  Presiona Ctrl+C para detener todo el sistema...")
        print("="*80)
        print()
        
        # Mantener vivo y monitorear
        while True:
            time.sleep(5)
            
            # Verificar si algún proceso crítico murió
            for nombre, proceso in procesos:
                if proceso.poll() is not None and nombre in ["Central", "CPs"]:
                    print(f"\n⚠️  ADVERTENCIA: {nombre} terminó inesperadamente (código: {proceso.returncode})")
    
    except KeyboardInterrupt:
        print("\n\n[TEST] Señal de interrupción recibida. Deteniendo sistema...")
        print("="*80)
        
        # Detener en orden inverso
        for nombre, proceso in reversed(procesos):
            try:
                print(f"  Deteniendo {nombre}... ", end='', flush=True)
                proceso.terminate()
                
                # Esperar hasta 3 segundos
                try:
                    proceso.wait(timeout=3)
                    print("✓")
                except subprocess.TimeoutExpired:
                    print("(forzando) ", end='', flush=True)
                    proceso.kill()
                    proceso.wait()
                    print("✓")
                    
            except Exception as e:
                print(f"✗ ({e})")
        
        print("="*80)
        print("  Sistema detenido completamente.")
        print("="*80)
        sys.exit(0)
    
    except Exception as e:
        print(f"\n[TEST] Error crítico: {e}")
        
        # Intentar limpiar procesos
        for nombre, proceso in procesos:
            try:
                proceso.kill()
            except:
                pass
        
        sys.exit(1)


if __name__ == "__main__":
    main()



