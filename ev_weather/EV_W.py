#!/usr/bin/env python3
"""
EV_W - Weather Control Office
Módulo que monitorea el clima en las localizaciones de los CPs y notifica alertas a EV_Central.

Uso:
    python EV_W.py --api-key <OPENWEATHER_API_KEY> --central-url http://127.0.0.1:5000/api
"""

import requests
import time
import argparse
import threading
import json
from datetime import datetime
from typing import Dict, List, Optional

# =================================================================
#                    CONFIGURACIÓN GLOBAL
# =================================================================

# Localizaciones de CPs (ciudad, país)
LOCALIZACIONES: Dict[str, str] = {}  # cp_id -> "Ciudad,País"
LOCALIZACIONES_LOCK = threading.Lock()

# Estado de alertas por localización
ALERTAS_ACTIVAS: Dict[str, bool] = {}  # cp_id -> True/False si hay alerta
ALERTAS_LOCK = threading.Lock()

# API Key de OpenWeather
OPENWEATHER_API_KEY: Optional[str] = None

# URL base de la API de EV_Central
CENTRAL_API_URL: Optional[str] = None

# Intervalo de consulta (4 segundos según especificación)
CHECK_INTERVAL = 4

# =================================================================
#                    FUNCIONES DE CLIMA
# =================================================================

def obtener_temperatura(ciudad_pais: str) -> Optional[float]:
    """
    Consulta la temperatura actual en OpenWeather API.
    
    Args:
        ciudad_pais: String en formato "Ciudad,País" (ej: "Madrid,ES")
    
    Returns:
        Temperatura en grados Celsius, o None si hay error
    """
    if not OPENWEATHER_API_KEY:
        print("[EV_W] ERROR: API Key de OpenWeather no configurada")
        return None
    
    try:
        # Construir URL de la API de OpenWeather
        url = f"http://api.openweathermap.org/data/2.5/weather"
        params = {
            'q': ciudad_pais,
            'appid': OPENWEATHER_API_KEY,
            'units': 'metric'  # Temperatura en Celsius
        }
        
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            temp = data.get('main', {}).get('temp')
            if temp is not None:
                return float(temp)
            else:
                print(f"[EV_W] ⚠️ No se encontró temperatura en respuesta para {ciudad_pais}")
                return None
        elif response.status_code == 401:
            print(f"[EV_W] ❌ ERROR: API Key inválida o expirada")
            return None
        elif response.status_code == 404:
            print(f"[EV_W] ⚠️ Ciudad no encontrada: {ciudad_pais}")
            return None
        else:
            print(f"[EV_W] ⚠️ Error HTTP {response.status_code} consultando {ciudad_pais}: {response.text[:100]}")
            return None
            
    except requests.exceptions.Timeout:
        print(f"[EV_W] ⚠️ Timeout consultando OpenWeather para {ciudad_pais}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[EV_W] ❌ Error de conexión consultando OpenWeather: {e}")
        return None
    except Exception as e:
        print(f"[EV_W] ❌ Error inesperado consultando clima: {e}")
        return None

def notificar_alerta_central(cp_id: str, temperatura: float, activar: bool) -> bool:
    """
    Notifica una alerta climatológica a EV_Central vía API REST.
    
    Args:
        cp_id: ID del punto de carga
        temperatura: Temperatura actual
        activar: True para activar alerta, False para desactivar
    
    Returns:
        True si la notificación fue exitosa, False en caso contrario
    """
    if not CENTRAL_API_URL:
        print("[EV_W] ERROR: URL de Central no configurada")
        return False
    
    try:
        url = f"{CENTRAL_API_URL}/weather_alert"
        payload = {
            'cp_id': cp_id,
            'temperatura': temperatura,
            'alerta_activa': activar,
            'timestamp': datetime.now().isoformat()
        }
        
        response = requests.post(url, json=payload, timeout=5)
        
        if response.status_code == 200:
            print(f"[EV_W] ✓ Alerta {'activada' if activar else 'desactivada'} notificada a Central para {cp_id} (T={temperatura:.1f}°C)")
            return True
        else:
            print(f"[EV_W] ⚠️ Error notificando alerta a Central: HTTP {response.status_code} - {response.text[:100]}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"[EV_W] ❌ Error de conexión notificando a Central: {e}")
        return False
    except Exception as e:
        print(f"[EV_W] ❌ Error inesperado notificando alerta: {e}")
        return False

def procesar_localizacion(cp_id: str, ciudad_pais: str):
    """
    Procesa una localización: consulta temperatura y gestiona alertas.
    
    Args:
        cp_id: ID del punto de carga
        ciudad_pais: Localización en formato "Ciudad,País"
    """
    temperatura = obtener_temperatura(ciudad_pais)
    
    if temperatura is None:
        # Error al obtener temperatura, no cambiar estado de alerta
        return
    
    # Verificar si hay alerta activa actualmente
    with ALERTAS_LOCK:
        alerta_actual = ALERTAS_ACTIVAS.get(cp_id, False)
    
    # Lógica de alerta: temperatura < 0°C
    if temperatura < 0.0:
        # Debe activar alerta si no está activa
        if not alerta_actual:
            print(f"\n{'='*70}")
            print(f"[EV_W] ⚠️ ALERTA CLIMATOLÓGICA ACTIVADA")
            print(f"  CP: {cp_id}")
            print(f"  Localización: {ciudad_pais}")
            print(f"  Temperatura: {temperatura:.1f}°C (< 0°C)")
            print(f"{'='*70}\n")
            
            # Notificar a Central
            if notificar_alerta_central(cp_id, temperatura, True):
                with ALERTAS_LOCK:
                    ALERTAS_ACTIVAS[cp_id] = True
        else:
            # Alerta ya activa, solo log
            print(f"[EV_W] Alerta activa para {cp_id}: T={temperatura:.1f}°C")
    else:
        # Temperatura >= 0°C, debe desactivar alerta si está activa
        if alerta_actual:
            print(f"\n{'='*70}")
            print(f"[EV_W] ✓ ALERTA CLIMATOLÓGICA DESACTIVADA")
            print(f"  CP: {cp_id}")
            print(f"  Localización: {ciudad_pais}")
            print(f"  Temperatura: {temperatura:.1f}°C (>= 0°C)")
            print(f"{'='*70}\n")
            
            # Notificar a Central
            if notificar_alerta_central(cp_id, temperatura, False):
                with ALERTAS_LOCK:
                    ALERTAS_ACTIVAS[cp_id] = False
        else:
            # Sin alerta, solo log periódico
            print(f"[EV_W] {cp_id} ({ciudad_pais}): T={temperatura:.1f}°C - OK")

def bucle_monitoreo_clima():
    """
    Bucle principal que consulta el clima cada 4 segundos para todas las localizaciones.
    """
    print("[EV_W] Iniciando bucle de monitoreo de clima...")
    print(f"[EV_W] Intervalo de consulta: {CHECK_INTERVAL} segundos")
    
    while True:
        try:
            # Obtener copia de localizaciones para evitar bloqueos largos
            with LOCALIZACIONES_LOCK:
                localizaciones_copy = LOCALIZACIONES.copy()
            
            if not localizaciones_copy:
                print("[EV_W] ⚠️ No hay localizaciones configuradas. Use el menú para añadir CPs.")
                time.sleep(CHECK_INTERVAL)
                continue
            
            # Procesar cada localización
            for cp_id, ciudad_pais in localizaciones_copy.items():
                procesar_localizacion(cp_id, ciudad_pais)
                # Pequeña pausa entre consultas para no saturar la API
                time.sleep(0.5)
            
            # Esperar el intervalo antes de la siguiente ronda
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n[EV_W] Interrupción recibida. Cerrando...")
            break
        except Exception as e:
            print(f"[EV_W] ❌ Error en bucle de monitoreo: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(CHECK_INTERVAL)

# =================================================================
#                    MENÚ INTERACTIVO
# =================================================================

def mostrar_menu():
    """Muestra el menú de opciones."""
    print("\n" + "="*70)
    print("  EV_W - Weather Control Office")
    print("="*70)
    print("  [1] Añadir localización de CP")
    print("  [2] Eliminar localización de CP")
    print("  [3] Listar localizaciones")
    print("  [4] Consultar temperatura de una localización")
    print("  [5] Estado de alertas")
    print("  [h] Ayuda")
    print("  [q] Salir")
    print("="*70)

def añadir_localizacion():
    """Añade una nueva localización de CP."""
    try:
        cp_id = input("ID del CP (ej: CP001): ").strip()
        if not cp_id:
            print("[EV_W] ❌ ID de CP no puede estar vacío")
            return
        
        ciudad_pais = input("Localización (formato: Ciudad,País, ej: Madrid,ES): ").strip()
        if not ciudad_pais:
            print("[EV_W] ❌ Localización no puede estar vacía")
            return
        
        with LOCALIZACIONES_LOCK:
            LOCALIZACIONES[cp_id] = ciudad_pais
        
        print(f"[EV_W] ✓ Localización añadida: {cp_id} -> {ciudad_pais}")
        
        # Consultar temperatura inmediatamente para verificar
        temp = obtener_temperatura(ciudad_pais)
        if temp is not None:
            print(f"[EV_W]   Temperatura actual: {temp:.1f}°C")
        else:
            print(f"[EV_W]   ⚠️ No se pudo obtener temperatura. Verifique la localización.")
            
    except KeyboardInterrupt:
        print("\n[EV_W] Operación cancelada")
    except Exception as e:
        print(f"[EV_W] ❌ Error añadiendo localización: {e}")

def eliminar_localizacion():
    """Elimina una localización de CP."""
    try:
        cp_id = input("ID del CP a eliminar: ").strip()
        if not cp_id:
            print("[EV_W] ❌ ID de CP no puede estar vacío")
            return
        
        with LOCALIZACIONES_LOCK:
            if cp_id in LOCALIZACIONES:
                ciudad_pais = LOCALIZACIONES.pop(cp_id)
                print(f"[EV_W] ✓ Localización eliminada: {cp_id} -> {ciudad_pais}")
                
                # También eliminar alerta si existe
                with ALERTAS_LOCK:
                    if cp_id in ALERTAS_ACTIVAS:
                        del ALERTAS_ACTIVAS[cp_id]
            else:
                print(f"[EV_W] ❌ CP {cp_id} no encontrado")
                
    except KeyboardInterrupt:
        print("\n[EV_W] Operación cancelada")
    except Exception as e:
        print(f"[EV_W] ❌ Error eliminando localización: {e}")

def listar_localizaciones():
    """Lista todas las localizaciones configuradas."""
    with LOCALIZACIONES_LOCK:
        if not LOCALIZACIONES:
            print("[EV_W] No hay localizaciones configuradas")
            return
        
        print("\n" + "="*70)
        print("  LOCALIZACIONES CONFIGURADAS")
        print("="*70)
        for cp_id, ciudad_pais in LOCALIZACIONES.items():
            with ALERTAS_LOCK:
                alerta = ALERTAS_ACTIVAS.get(cp_id, False)
            estado_alerta = "⚠️ ALERTA ACTIVA" if alerta else "✓ OK"
            print(f"  {cp_id:10} -> {ciudad_pais:30} [{estado_alerta}]")
        print("="*70)

def consultar_temperatura():
    """Consulta la temperatura de una localización específica."""
    try:
        ciudad_pais = input("Localización (formato: Ciudad,País): ").strip()
        if not ciudad_pais:
            print("[EV_W] ❌ Localización no puede estar vacía")
            return
        
        print(f"[EV_W] Consultando temperatura para {ciudad_pais}...")
        temp = obtener_temperatura(ciudad_pais)
        
        if temp is not None:
            print(f"[EV_W] ✓ Temperatura: {temp:.1f}°C")
            if temp < 0.0:
                print(f"[EV_W] ⚠️ ALERTA: Temperatura por debajo de 0°C")
            else:
                print(f"[EV_W] ✓ Temperatura OK (>= 0°C)")
        else:
            print(f"[EV_W] ❌ No se pudo obtener temperatura")
            
    except KeyboardInterrupt:
        print("\n[EV_W] Operación cancelada")
    except Exception as e:
        print(f"[EV_W] ❌ Error consultando temperatura: {e}")

def estado_alertas():
    """Muestra el estado actual de todas las alertas."""
    with ALERTAS_LOCK, LOCALIZACIONES_LOCK:
        if not ALERTAS_ACTIVAS and not LOCALIZACIONES:
            print("[EV_W] No hay alertas ni localizaciones configuradas")
            return
        
        print("\n" + "="*70)
        print("  ESTADO DE ALERTAS CLIMATOLÓGICAS")
        print("="*70)
        
        alertas_activas_list = [cp_id for cp_id, activa in ALERTAS_ACTIVAS.items() if activa]
        
        if alertas_activas_list:
            print("  ⚠️ ALERTAS ACTIVAS:")
            for cp_id in alertas_activas_list:
                ciudad = LOCALIZACIONES.get(cp_id, "N/D")
                print(f"    - {cp_id} ({ciudad})")
        else:
            print("  ✓ No hay alertas activas")
        
        print("="*70)

def menu_interactivo():
    """Menú interactivo para gestionar localizaciones."""
    while True:
        try:
            mostrar_menu()
            opcion = input("\n[EV_W] Opción: ").strip().lower()
            
            if opcion == '1':
                añadir_localizacion()
            elif opcion == '2':
                eliminar_localizacion()
            elif opcion == '3':
                listar_localizaciones()
            elif opcion == '4':
                consultar_temperatura()
            elif opcion == '5':
                estado_alertas()
            elif opcion == 'h':
                mostrar_menu()
            elif opcion == 'q':
                print("[EV_W] Saliendo del menú...")
                break
            else:
                print(f"[EV_W] ❌ Opción no reconocida: {opcion}")
                
        except KeyboardInterrupt:
            print("\n[EV_W] Saliendo del menú...")
            break
        except Exception as e:
            print(f"[EV_W] ❌ Error en menú: {e}")

# =================================================================
#                    MAIN
# =================================================================

def main():
    global OPENWEATHER_API_KEY, CENTRAL_API_URL
    
    parser = argparse.ArgumentParser(description="EV_W - Weather Control Office")
    parser.add_argument("--api-key", type=str, required=True,
                        help="API Key de OpenWeather (obtener en https://openweathermap.org/api)")
    parser.add_argument("--central-url", type=str, default="http://127.0.0.1:5000/api",
                        help="URL base de la API de EV_Central (default: http://127.0.0.1:5000/api)")
    
    args = parser.parse_args()
    
    OPENWEATHER_API_KEY = args.api_key
    CENTRAL_API_URL = args.central_url.rstrip('/')
    
    print("="*70)
    print("  EV_W - Weather Control Office")
    print("="*70)
    print(f"  API Key: {OPENWEATHER_API_KEY[:10]}...")
    print(f"  Central URL: {CENTRAL_API_URL}")
    print(f"  Intervalo de consulta: {CHECK_INTERVAL} segundos")
    print("="*70)
    print()
    
    # Verificar conexión con OpenWeather
    print("[EV_W] Verificando conexión con OpenWeather...")
    test_temp = obtener_temperatura("Madrid,ES")
    if test_temp is not None:
        print(f"[EV_W] ✓ Conexión OK. Temperatura de prueba (Madrid): {test_temp:.1f}°C")
    else:
        print("[EV_W] ⚠️ No se pudo verificar conexión. Continuando de todas formas...")
    
    # Iniciar hilo de monitoreo de clima
    monitoreo_thread = threading.Thread(target=bucle_monitoreo_clima, daemon=True)
    monitoreo_thread.start()
    print("[EV_W] ✓ Hilo de monitoreo iniciado")
    
    # Iniciar menú interactivo en el hilo principal
    try:
        menu_interactivo()
    except KeyboardInterrupt:
        print("\n[EV_W] Cerrando EV_W...")
    finally:
        print("[EV_W] Finalizado")

if __name__ == "__main__":
    main()

