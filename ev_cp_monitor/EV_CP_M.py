import time
import argparse
import socket
import sys
import threading
from queue import Queue, Empty
import requests
import base64
import os
import json
from cryptography.fernet import Fernet
import urllib3

# Deshabilitar advertencias SSL para certificados autofirmados
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =================================================================
#                         FUNCIONES DE PROTOCOLO
# =================================================================
# Constantes de Protocolo
STX = b'\x02'
ETX = b'\x03'
DELIMITER = '#'
HCK_INTERVAL = 1 # Segundos entre cada HCK

def calcular_lrc(data_bytes: bytes) -> bytes:
    """Calcula el Longitudinal Redundancy Check (XOR de todos los bytes)."""
    lrc = 0
    for byte in data_bytes:
        lrc ^= byte
    return bytes([lrc])

def es_trama_fin(trama_bytes: bytes) -> bool:
    """Verifica rápidamente si una trama es FIN sin descomponerla completamente."""
    if len(trama_bytes) < 5:  # Mínimo: STX + "FIN" + ETX + LRC
        return False
    if not trama_bytes.startswith(STX):
        return False
    try:
        # Extraer el código de operación (después de STX hasta el primer # o ETX)
        data_start = 1  # Después de STX
        data_end = trama_bytes.find(ETX, data_start)
        if data_end == -1:
            return False
        data_part = trama_bytes[data_start:data_end]
        # Verificar si empieza con "FIN#"
        if data_part.startswith(b'FIN#'):
            return True
    except Exception:
        pass
    return False

def descomponer_trama(trama_bytes: bytes) -> tuple:
    # ... [Tu lógica robusta de descomponer_trama] ...
    if len(trama_bytes) < 4:
         return None, None
    
    lrc_recibido = trama_bytes[-1:] 
    data_con_etx = trama_bytes[1:-1]
    data_bytes = data_con_etx[:-1]
    
    if not (trama_bytes.startswith(STX) and data_con_etx.endswith(ETX)):
        return None, None
        
    lrc_calculado = calcular_lrc(data_bytes)
    if lrc_recibido != lrc_calculado:
        # Solo para depuración: print(f"Error LRC. Recibido: {lrc_recibido.hex()}, Calculado: {lrc_calculado.hex()}.")
        return None, None
        
    try:
        DATA = data_bytes.decode('utf-8')
        partes = DATA.split(DELIMITER)
        return partes[0], partes[1:]
    except UnicodeDecodeError:
        return None, None

def construir_trama(cod_op: str, campos: list, cifrar: bool = True) -> bytes:
    """
    Construye la trama completa del protocolo EV_CP_M.
    Si hay clave de cifrado, cifra el contenido antes de enviarlo.
    """
    DATA = f"{cod_op}#{DELIMITER.join(map(str, campos))}"
    DATA_bytes = DATA.encode('utf-8')
    
    # Cifrar si hay clave disponible
    if cifrar:
        with ENCRYPTION_KEY_LOCK:
            key = ENCRYPTION_KEY
        if key:
            try:
                fernet = Fernet(key)
                DATA_bytes = fernet.encrypt(DATA_bytes)
                # Prefijo para indicar que está cifrado
                DATA_bytes = b'ENC' + DATA_bytes
            except Exception as e:
                print(f"[CP_M] ⚠️ Error cifrando mensaje: {e}")
    
    LRC_byte = calcular_lrc(DATA_bytes)
    trama = STX + DATA_bytes + ETX + LRC_byte
    return trama

def descomponer_trama_cifrada(trama_bytes: bytes) -> tuple:
    """
    Descompone una trama, descifrándola si está cifrada.
    """
    if len(trama_bytes) < 4:
        return None, None
    
    lrc_recibido = trama_bytes[-1:]
    data_con_etx = trama_bytes[1:-1]
    data_bytes = data_con_etx[:-1]
    
    if not (trama_bytes.startswith(STX) and data_con_etx.endswith(ETX)):
        return None, None
    
    # Verificar si está cifrado
    if data_bytes.startswith(b'ENC'):
        # Descifrar
        with ENCRYPTION_KEY_LOCK:
            key = ENCRYPTION_KEY
        if key:
            try:
                fernet = Fernet(key)
                data_cifrado = data_bytes[3:]  # Quitar prefijo 'ENC'
                data_bytes = fernet.decrypt(data_cifrado)
            except Exception as e:
                print(f"[CP_M] ⚠️ Error descifrando mensaje: {e}")
                return None, None
        else:
            print(f"[CP_M] ⚠️ Mensaje cifrado recibido pero no hay clave disponible")
            return None, None
    
    lrc_calculado = calcular_lrc(data_bytes)
    if lrc_recibido != lrc_calculado:
        return None, None
    
    try:
        DATA = data_bytes.decode('utf-8')
        partes = DATA.split(DELIMITER)
        return partes[0], partes[1:]
    except UnicodeDecodeError:
        return None, None

# =================================================================
#                     COLA DE ORDENES (STOP/START)
# =================================================================

# Cola compartida entre el hilo de escucha de la Central y el hilo HCK
COMMAND_QUEUE: Queue = Queue()

# Sesión actual (se establece al recibir AUTH_REQ de Central)
SESION_DRIVER_ID = None
SESION_KW_SOLICITADOS = None
WAITING_FOR_PLUG = False

# Credenciales de EV_Registry
REGISTRY_CREDENTIALS = {
    'username': None,
    'password': None,
    'cp_id': None
}
REGISTRY_CREDENTIALS_LOCK = threading.Lock()

# Clave de cifrado recibida de Central
ENCRYPTION_KEY = None
ENCRYPTION_KEY_LOCK = threading.Lock()

# URL de EV_Registry
# Si REGISTRY_URL no especifica protocolo, intentar HTTPS primero, luego HTTP
REGISTRY_URL_ENV = os.getenv('REGISTRY_URL', '')
if REGISTRY_URL_ENV:
    REGISTRY_URL = REGISTRY_URL_ENV
else:
    # Por defecto, intentar HTTPS primero (si hay certificados)
    # Si no funciona, el código intentará HTTP
    REGISTRY_URL = os.getenv('REGISTRY_URL_HTTPS', 'https://127.0.0.1:6000/api')
    # Fallback a HTTP si HTTPS no está disponible
    if not REGISTRY_URL.startswith(('http://', 'https://')):
        REGISTRY_URL = f'https://{REGISTRY_URL}'

# =================================================================
#                       LÓGICA DE COMUNICACIÓN CENTRAL
# =================================================================

def notificar_averia_central(central_socket: socket.socket, cp_id: str, motivo: str):
    """Envía un mensaje AVR (Avería/Estado ROJO) a la Central (cifrado si hay clave)."""
    try:
        # Enviar el estado de AVERÍA (se cifrará automáticamente si hay clave)
        trama_averia = construir_trama('AVR', [cp_id, motivo], cifrar=True)
        central_socket.sendall(trama_averia)
        print(f"[{cp_id}] -> ENVIADO AVR a Central. Motivo: {motivo}")

    except Exception as e:
        print(f"[{cp_id}] ERROR al notificar avería a la Central: {e}. Conexión perdida.")
        # La conexión con Central está caída. El hilo de escucha ya debería manejar esto.


def enviar_orden_a_engine(engine_ip: str, engine_port: int, orden: str, cp_id: str) -> None:
    """Abre una conexión corta con el Engine para enviar una orden (CMD) y esperar ACK."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect((engine_ip, engine_port))
            trama_cmd = construir_trama('CMD', [orden])
            s.sendall(trama_cmd)

            resp = s.recv(1024)
            if not resp:
                print(f"[{cp_id}] Engine no respondió al comando {orden}.")
                return

            cod_op, campos = descomponer_trama(resp)
            if cod_op == 'ACK':
                detalle = campos[0] if campos else ''
                print(f"[{cp_id}] ACK del Engine recibido: {detalle}")
            else:
                print(f"[{cp_id}] Respuesta inesperada del Engine: {cod_op}")
    except Exception as e:
        print(f"[{cp_id}] Error enviando orden '{orden}' al Engine: {e}")

# =================================================================
#                    FUNCIONES DE EV_Registry
# =================================================================

def registrar_en_registry(cp_id: str, ubicacion: str) -> tuple:
    """
    Registra el CP en EV_Registry.
    Intenta HTTPS primero, luego HTTP si falla.
    
    Returns:
        (success: bool, username: str, password: str) o (False, None, None)
    """
    # Intentar HTTPS primero si la URL no especifica protocolo
    base_url = REGISTRY_URL
    if not base_url.startswith(('http://', 'https://')):
        base_url = f'https://{base_url}'
    
    # Si la URL base termina en /api, no agregar /register dos veces
    if base_url.endswith('/api'):
        url = f"{base_url}/register"
    else:
        url = f"{base_url}/api/register"
    
    payload = {
        'cp_id': cp_id,
        'ubicacion': ubicacion
    }
    
    try:
        # Intentar HTTPS primero (con verify=False para certificados autofirmados)
        try:
            response = requests.post(url, json=payload, timeout=10, verify=False)
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
            # Si HTTPS falla, intentar HTTP
            if url.startswith('https://'):
                url_http = url.replace('https://', 'http://')
                print(f"[CP_M] ⚠️ HTTPS falló, intentando HTTP...")
                response = requests.post(url_http, json=payload, timeout=10)
            else:
                raise
        
        if response.status_code == 201:
            data = response.json()
            username = data.get('username')
            password = data.get('password')
            
            if username and password:
                with REGISTRY_CREDENTIALS_LOCK:
                    REGISTRY_CREDENTIALS['username'] = username
                    REGISTRY_CREDENTIALS['password'] = password
                    REGISTRY_CREDENTIALS['cp_id'] = cp_id
                
                print(f"[CP_M] ✓ Registrado en EV_Registry")
                print(f"[CP_M]   Username: {username}")
                print(f"[CP_M]   Password: {password[:10]}...")
                return True, username, password
            else:
                print(f"[CP_M] ❌ Respuesta de Registry inválida: no hay credenciales")
                return False, None, None
        elif response.status_code == 409:
            print(f"[CP_M] ⚠️ CP ya registrado. Use autenticación en su lugar.")
            return False, None, None
        else:
            print(f"[CP_M] ❌ Error registrando en EV_Registry: HTTP {response.status_code} - {response.text[:100]}")
            return False, None, None
            
    except requests.exceptions.RequestException as e:
        print(f"[CP_M] ❌ Error de conexión con EV_Registry: {e}")
        return False, None, None
    except Exception as e:
        print(f"[CP_M] ❌ Error inesperado registrando: {e}")
        return False, None, None

def autenticar_en_registry(username: str, password: str) -> bool:
    """
    Autentica el CP en EV_Registry.
    Intenta HTTPS primero, luego HTTP si falla.
    
    Returns:
        True si la autenticación fue exitosa
    """
    # Intentar HTTPS primero si la URL no especifica protocolo
    base_url = REGISTRY_URL
    if not base_url.startswith(('http://', 'https://')):
        base_url = f'https://{base_url}'
    
    # Si la URL base termina en /api, no agregar /authenticate dos veces
    if base_url.endswith('/api'):
        url = f"{base_url}/authenticate"
    else:
        url = f"{base_url}/api/authenticate"
    
    payload = {
        'username': username,
        'password': password
    }
    
    try:
        # Intentar HTTPS primero (con verify=False para certificados autofirmados)
        try:
            response = requests.post(url, json=payload, timeout=10, verify=False)
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
            # Si HTTPS falla, intentar HTTP
            if url.startswith('https://'):
                url_http = url.replace('https://', 'http://')
                print(f"[CP_M] ⚠️ HTTPS falló, intentando HTTP...")
                response = requests.post(url_http, json=payload, timeout=10)
            else:
                raise
        
        if response.status_code == 200:
            data = response.json()
            cp_id = data.get('cp_id')
            if cp_id:
                with REGISTRY_CREDENTIALS_LOCK:
                    REGISTRY_CREDENTIALS['cp_id'] = cp_id
                print(f"[CP_M] ✓ Autenticación exitosa en EV_Registry (CP: {cp_id})")
                return True
            else:
                print(f"[CP_M] ❌ Respuesta de autenticación inválida")
                return False
        else:
            print(f"[CP_M] ❌ Autenticación fallida: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[CP_M] ❌ Error autenticando: {e}")
        return False

# =================================================================
#                    FUNCIONES DE REGISTRO CON CENTRAL
# =================================================================

def conectar_y_registrar(central_ip: str, central_port: int, cp_id: str) -> socket.socket:
    """Conecta al EV_Central y realiza el registro. Retorna el socket conectado."""
    
    # Solicitar localización al usuario si no está configurada
    ubicacion_cp = os.getenv(f'CP_{cp_id}_UBICACION', '')
    if not ubicacion_cp:
        try:
            print(f"\n{'='*70}")
            print(f"  REGISTRO DE CP: {cp_id}")
            print(f"{'='*70}")
            print("  Por favor, ingrese la localización del CP:")
            print("  Formato: Ciudad,País (ejemplo: Madrid,ES)")
            ubicacion_cp = input(f"  Localización para {cp_id}: ").strip()
            if not ubicacion_cp:
                ubicacion_cp = "Madrid,ES"  # Valor por defecto
                print(f"  Usando localización por defecto: {ubicacion_cp}")
            print(f"{'='*70}\n")
        except (EOFError, KeyboardInterrupt):
            ubicacion_cp = "Madrid,ES"  # Valor por defecto si no hay entrada
            print(f"[CP_M] Usando localización por defecto: {ubicacion_cp}")
    
    precio_kwh = "0.48"
    client_socket = None

    # ====== PASO 1: REGISTRO/AUTENTICACIÓN EN EV_Registry ======
    print(f"\n{'='*70}")
    print(f"  [CP_M] PASO 1: REGISTRO/AUTENTICACIÓN EN EV_Registry")
    print(f"{'='*70}")
    
    username = None
    password = None
    
    # Verificar si ya tenemos credenciales almacenadas
    with REGISTRY_CREDENTIALS_LOCK:
        if REGISTRY_CREDENTIALS.get('username') and REGISTRY_CREDENTIALS.get('password'):
            username = REGISTRY_CREDENTIALS['username']
            password = REGISTRY_CREDENTIALS['password']
            print(f"[CP_M] ✓ Credenciales de Registry encontradas en memoria")
            print(f"[CP_M]   Username: {username}")
            print(f"[CP_M]   Intentando autenticación con Registry...")
            
            # Intentar autenticar con las credenciales existentes
            if autenticar_en_registry(username, password):
                print(f"[CP_M] ✓ Autenticación exitosa con Registry usando credenciales existentes")
            else:
                print(f"[CP_M] ⚠️ Autenticación fallida. Intentando registro nuevo...")
                username = None
                password = None
    
    # Si no hay credenciales o la autenticación falló, registrar nuevo CP
    if not username or not password:
        print(f"[CP_M] Registrando CP {cp_id} en EV_Registry...")
        success, username, password = registrar_en_registry(cp_id, ubicacion_cp)
        
        if not success or not username or not password:
            print(f"[CP_M] ❌ ERROR: No se pudo registrar/autenticar en EV_Registry")
            print(f"[CP_M] ⚠️ Continuando sin credenciales (modo compatibilidad)...")
            username = None
            password = None
        else:
            print(f"[CP_M] ✓ Registro exitoso en EV_Registry")
            print(f"[CP_M]   Username: {username}")
            print(f"[CP_M]   Password: {password[:10]}... (mostrando primeros 10 caracteres)")
    
    print(f"{'='*70}\n")

    try:
        # Registrar localización en EV_W si está disponible
        weather_api_url = os.getenv('WEATHER_API_URL', 'http://127.0.0.1:5000/api')
        try:
            # Extraer ciudad,país de la ubicación
            if ',' in ubicacion_cp:
                ciudad_pais = ubicacion_cp.split(',')[0].strip() + ',' + ubicacion_cp.split(',')[1].strip() if len(ubicacion_cp.split(',')) >= 2 else ubicacion_cp
            else:
                ciudad_pais = ubicacion_cp
            
            # Intentar registrar en EV_W (no crítico si falla)
            try:
                weather_register_url = f"{weather_api_url.replace('/api', '')}/weather/register_cp" if '/api' in weather_api_url else f"{weather_api_url}/weather/register_cp"
                payload = {'cp_id': cp_id, 'localizacion': ciudad_pais}
                response = requests.post(weather_register_url, json=payload, timeout=2)
                if response.status_code in (200, 201):
                    print(f"[CP_M] ✓ Localización registrada en EV_W: {ciudad_pais}")
                else:
                    print(f"[CP_M] ⚠️ No se pudo registrar en EV_W (HTTP {response.status_code})")
            except Exception as e:
                print(f"[CP_M] ⚠️ EV_W no disponible o error registrando localización: {e}")
        except Exception:
            pass  # No crítico si falla
        
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Timeout de conexión para evitar bloqueos indefinidos
        client_socket.settimeout(10)
        
        print(f"[CP_M] Intentando conectar a EV_Central en {central_ip}:{central_port}...")
        
        try:
            client_socket.connect((central_ip, central_port))
        except socket.timeout:
            raise Exception(f"Timeout al conectar (10s). Verifica que EV_Central esté ejecutándose en {central_ip}:{central_port}")
        except ConnectionRefusedError:
            raise Exception(
                f"Connection refused. Posibles causas:\n"
                f"  1. EV_Central no está ejecutándose en {central_ip}:{central_port}\n"
                f"  2. El firewall de PC_A está bloqueando el puerto {central_port}\n"
                f"  3. La IP {central_ip} es incorrecta (debe ser la IP del PC_A, no 127.0.0.1)\n"
                f"  4. El contenedor de la Central no tiene el puerto 5000 mapeado correctamente"
            )
        except socket.gaierror as e:
            raise Exception(f"No se pudo resolver el hostname/IP {central_ip}: {e}")
        
        print("[CP_M] Conexión con Central establecida. Enviando REG...")
        
        # Quitar timeout para la comunicación posterior
        client_socket.settimeout(None)

        # ====== PASO 2: ENVIAR REG CON CREDENCIALES DEL REGISTRY ======
        print(f"\n{'='*70}")
        print(f"  [CP_M] PASO 2: ENVIANDO REG A CENTRAL CON CREDENCIALES")
        print(f"{'='*70}")
        
        # Construir mensaje REG con credenciales si están disponibles
        campos_reg = [cp_id, ubicacion_cp, precio_kwh]
        if username and password:
            campos_reg.extend([username, password])
            print(f"[CP_M] ✓ Enviando REG con credenciales del Registry:")
            print(f"[CP_M]   CP_ID: {cp_id}")
            print(f"[CP_M]   Username: {username}")
            print(f"[CP_M]   Password: {password[:10]}... (enviado completo)")
        else:
            print(f"[CP_M] ⚠️ Enviando REG sin credenciales (modo compatibilidad)")
        
        print(f"{'='*70}\n")
        
        trama_registro = construir_trama('REG', campos_reg)
        client_socket.sendall(trama_registro)

        respuesta_bytes = client_socket.recv(1024)
        if not respuesta_bytes:
            raise Exception("No se recibió respuesta o Central cerró la conexión.")

        # Usar descomponer_trama_cifrada para manejar mensajes cifrados
        cod_op, campos = descomponer_trama_cifrada(respuesta_bytes)
        
        print(f"[CP_M] Recibida respuesta de Central")

        if cod_op == 'AUTH' and campos and campos[0] == 'OK':
            mensaje = campos[1] if len(campos) > 1 else 'Autenticación exitosa'
            
            # Verificar si se recibió clave de cifrado (tercer campo)
            if len(campos) >= 3:
                clave_b64 = campos[2]
                try:
                    clave_bytes = base64.b64decode(clave_b64)
                    with ENCRYPTION_KEY_LOCK:
                        ENCRYPTION_KEY = clave_bytes
                    print(f"[CP_M] ✓ Clave de cifrado recibida y almacenada")
                except Exception as e:
                    print(f"[CP_M] ⚠️ Error procesando clave de cifrado: {e}")
            
            print(f"\n{'='*70}")
            print(f"  [CP_M] ✓ REGISTRO Y AUTENTICACIÓN EXITOSOS")
            print(f"{'='*70}")
            if username and password:
                print(f"[CP_M] ✓ Credenciales del Registry verificadas correctamente por Central")
                print(f"[CP_M]   Username: {username}")
                print(f"[CP_M]   Central validó las credenciales con EV_Registry")
            print(f"[CP_M]   CP ID: {cp_id}")
            print(f"[CP_M]   Estado: ACTIVADO")
            print(f"[CP_M]   Mensaje: {mensaje}")
            print(f"{'='*70}\n")
            
            return client_socket 
        else:
            raise Exception(f"Fallo de autenticación. Respuesta inválida o AUTH#FAIL. Cod={cod_op}, Campos={campos}")

    except Exception as e:
        print(f"[CP_M] ERROR durante el registro: {e}")
        if client_socket:
            client_socket.close()
        raise

def escuchar_central(central_socket: socket.socket, cp_id: str, engine_ip: str, engine_port: int):
    """Bucle de escucha permanente para comandos síncronos de la Central."""
    print(f"[{cp_id}] Hilo de escucha de Central iniciado.")
    # NOTA: Necesitamos el socket del Engine para enviar la orden de START/STOP. 
    # Lo más limpio es reabrir la conexión brevemente o usar el hilo HCK.
    # Por ahora, vamos a notificar la recepción.
    
    try:
        while True:
            trama_bytes = central_socket.recv(4096)  # Aumentar buffer para mensajes cifrados
            if not trama_bytes:
                print(f"[{cp_id}] Central cerró la conexión. Socket de comando cerrado.")
                break
            
            cod_op, campos = descomponer_trama_cifrada(trama_bytes)
            
            if cod_op == 'AUTH_REQ':
                # AUTH_REQ#<driver_id>#<kw_deseados>
                try:
                    driver_id = campos[0] if len(campos) > 0 else 'UNKNOWN'
                    kw_deseados = campos[1] if len(campos) > 1 else '0'
                    print(f"[{cp_id}] <--- AUTH_REQ recibido de Central. Driver={driver_id}, kW={kw_deseados}")
                    # Guardar sesión actual
                    try:
                        globals()['SESION_DRIVER_ID'] = driver_id
                        globals()['SESION_KW_SOLICITADOS'] = float(kw_deseados)
                    except Exception:
                        globals()['SESION_DRIVER_ID'] = driver_id
                        globals()['SESION_KW_SOLICITADOS'] = None
                    # Marcar que estamos autorizados
                    globals()['WAITING_FOR_PLUG'] = True
                    
                    # NUEVO: Reenviar AUTH_REQ al Engine para que muestre el botón "Iniciar Suministro"
                    try:
                        print(f"[{cp_id}] 📤 Reenviando AUTH_REQ al Engine...")
                        trama_auth_engine = construir_trama('AUTH_REQ', [driver_id, kw_deseados])
                        # Encolar para envío en el siguiente ciclo HCK
                        COMMAND_QUEUE.put_nowait(('AUTH_REQ', time.time(), driver_id, kw_deseados))
                        print(f"[{cp_id}] ✓ AUTH_REQ encolado para Engine")
                    except Exception as e:
                        print(f"[{cp_id}] Error encolando AUTH_REQ para Engine: {e}")
                    
                    # Responder a la Central con autorización OK (cifrado)
                    resp = construir_trama('AUTH_RESP', [driver_id, 'OK', 'Autorizacion concedida'], cifrar=True)
                    central_socket.sendall(resp)
                    print(f"[{cp_id}] ✓ AUTH_RESP enviado a Central (cifrado). Esperando acción del operador del Engine...")
                except Exception as e:
                    print(f"[{cp_id}] Error procesando AUTH_REQ: {e}")
                continue

            if cod_op in ('STOP', 'START'):
                print(f"[{cp_id}] <--- COMANDO CENTRAL RECIBIDO: {cod_op}")
                # Encolamos la orden para que la ejecute el hilo HCK sobre su socket
                try:
                    if cod_op == 'START' and len(campos) >= 2:
                        # START con parámetros (driver_id, kw_deseados) desde comando manual de web
                        driver_id = campos[0] if len(campos) > 0 else None
                        kw_deseados = campos[1] if len(campos) > 1 else None
                        try:
                            kw_float = float(kw_deseados) if kw_deseados else None
                        except:
                            kw_float = None
                        COMMAND_QUEUE.put_nowait((cod_op, time.time(), kw_float, driver_id))
                        print(f"[{cp_id}] Orden '{cod_op}' encolada para Engine con parámetros: driver={driver_id}, kW={kw_float}")
                    else:
                        # STOP o START sin parámetros
                        COMMAND_QUEUE.put_nowait((cod_op, time.time(), None, None))
                        print(f"[{cp_id}] Orden '{cod_op}' encolada para Engine.")
                except Exception as e:
                    print(f"[{cp_id}] No se pudo encolar la orden {cod_op}: {e}")
                # Notificar inmediatamente a la Central el estado administrativo (cifrado)
                try:
                    nuevo_estado = 'PARADO' if cod_op == 'STOP' else 'ACTIVADO'
                    trama_state = construir_trama('STATE', [cp_id, nuevo_estado], cifrar=True)
                    central_socket.sendall(trama_state)
                    print(f"[{cp_id}] STATE inmediato enviado a Central (cifrado): {nuevo_estado}")
                except Exception as e:
                    print(f"[{cp_id}] Error enviando STATE a Central: {e}")

            else:
                 # Manejo de otros códigos, como AVR, o tramas inesperadas
                print(f"[{cp_id}] <--- Trama Central recibida (No comando): {cod_op}")


    except Exception as e:
        print(f"[{cp_id}] Error en hilo de escucha de Central: {e}")
    finally:
        central_socket.close()


def chequear_salud_engine(engine_ip: str, engine_port: int, central_socket: socket.socket, cp_id: str):
    """Hilo para enviar HCK al Engine cada 1 segundo y gestionar la respuesta."""
    engine_socket = None
    conexion_perdida_notificada = False

    while True:
        try:
            # 1. Intentar establecer/reestablecer conexión con el Engine
            if engine_socket is None:
                try:
                    print(f"[{cp_id}] Intentando conectar al Engine en {engine_ip}:{engine_port}...")
                    engine_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    engine_socket.settimeout(3.0)  # Timeout para el connect
                    engine_socket.connect((engine_ip, engine_port))
                    print(f"[{cp_id}] ✓ Conexión con Engine establecida.")
                    engine_socket.settimeout(HCK_INTERVAL * 0.8)
                    conexion_perdida_notificada = False
                except (ConnectionRefusedError, socket.timeout, OSError) as e:
                    if not conexion_perdida_notificada:
                        print(f"[{cp_id}] Engine no disponible aún. Reintentando cada {HCK_INTERVAL}s...")
                        conexion_perdida_notificada = True
                    if engine_socket:
                        engine_socket.close()
                    engine_socket = None
                    time.sleep(HCK_INTERVAL)
                    continue
            
            # 2. Antes de enviar HCK, consumir órdenes pendientes y enviarlas por el mismo socket
            #    Consumimos todas las que haya disponibles sin bloquear
            while True:
                try:
                    item = COMMAND_QUEUE.get_nowait()
                except Empty:
                    break
                try:
                    # item puede ser (orden, ts) o (orden, ts, param1, param2)
                    if isinstance(item, tuple) and len(item) >= 2:
                        orden = item[0]
                        ts = item[1]
                        param1 = item[2] if len(item) > 2 else None
                        param2 = item[3] if len(item) > 3 else None
                    else:
                        orden = str(item)
                        ts = time.time()
                        param1 = None
                        param2 = None

                    # Manejar AUTH_REQ especialmente (no es un CMD)
                    if orden == 'AUTH_REQ':
                        driver_id = param1
                        kw_deseados = param2
                        campos_auth = [driver_id, str(kw_deseados) if kw_deseados else '0']
                        trama_auth = construir_trama('AUTH_REQ', campos_auth)
                        engine_socket.sendall(trama_auth)
                        print(f"[{cp_id}] 📤 AUTH_REQ enviado al Engine (Driver: {driver_id}, kW: {kw_deseados})")
                        # El Engine procesará el AUTH_REQ internamente y responderá con ACK
                        # Leer la respuesta para limpiar el buffer
                        try:
                            resp_auth = engine_socket.recv(1024)
                            cod_resp, campos_resp = descomponer_trama(resp_auth)
                            if cod_resp == 'ACK':
                                print(f"[{cp_id}] ✓ Engine confirmó recepción de AUTH_REQ: {campos_resp[0] if campos_resp else 'OK'}")
                            else:
                                print(f"[{cp_id}] ⚠️ Respuesta inesperada a AUTH_REQ: {cod_resp}")
                        except Exception as e:
                            print(f"[{cp_id}] ⚠️ Error leyendo respuesta AUTH_REQ: {e}")
                        continue
                    
                    # Para START/STOP y otros comandos CMD
                    campos_cmd = [orden]
                    if orden == 'START' and param1 is not None:
                        # param1 es kw, param2 es driver
                        campos_cmd.append(str(param1))
                        if param2:
                            campos_cmd.append(str(param2))
                    trama_cmd = construir_trama('CMD', campos_cmd)
                    engine_socket.sendall(trama_cmd)
                    resp_cmd = engine_socket.recv(1024)
                    
                    # Verificar si la respuesta es FIN antes de descomponerla
                    if es_trama_fin(resp_cmd):
                        print(f"[{cp_id}] 📩 Trama FIN recibida del Engine (respuesta a CMD '{orden}'). Reenviando a Central...")
                        try:
                            # Descomponer y reconstruir cifrado para Central
                            cod_fin_cmd, campos_fin_cmd = descomponer_trama(resp_cmd)
                            if cod_fin_cmd == 'FIN':
                                trama_fin_cifrada = construir_trama('FIN', campos_fin_cmd, cifrar=True)
                                central_socket.sendall(trama_fin_cifrada)
                                print(f"[{cp_id}] 📤 Trama FIN reenviada a Central con éxito (cifrado).")
                        except Exception as e:
                            print(f"[{cp_id}] ❌ ERROR al reenviar FIN a Central: {e}")
                            import traceback
                            traceback.print_exc()
                        # También descomponer para logging opcional
                        cod_cmd, campos_cmd = descomponer_trama(resp_cmd)
                        if cod_cmd == 'FIN':
                            print(f"[{cp_id}]   Campos FIN: {campos_cmd}")
                        # No procesar más, el FIN ya fue reenviado
                        continue
                    
                    cod_cmd, campos_cmd = descomponer_trama(resp_cmd)
                    if cod_cmd == 'ACK':
                        detalle = campos_cmd[0] if campos_cmd else ''
                        print(f"[{cp_id}] ACK Engine a '{orden}': {detalle}")
                    else:
                        print(f"[{cp_id}] Respuesta inesperada a CMD '{orden}': {cod_cmd}")
                except Exception as e:
                    print(f"[{cp_id}] Error enviando comando '{orden}' por HCK socket: {e}")
                    # Reencolar para reintentar cuando se restablezca la conexión
                    try:
                        COMMAND_QUEUE.put_nowait(item)
                    except Exception:
                        pass
                    raise

            # 3. Enviar HCK
            trama_hck = construir_trama('HCK', [cp_id])
            engine_socket.sendall(trama_hck)
            
            # 4. Recibir y procesar todas las respuestas disponibles (puede llegar más de una trama)
            # Nota: Las respuestas del Engine no están cifradas, solo las de Central
            def _procesar_trama_engine(cod: str, args: list, trama_completa: bytes = None):
                if cod == 'HCK_RESP' and args:
                    status = args[0]
                    if status == 'OK':
                        return
                    if status == 'KO':
                        print(f"[{cp_id}] HCK KO recibido. Notificando avería a Central.")
                        notificar_averia_central(central_socket, cp_id, "Fallo reportado por Engine")
                    else:
                        print(f"[{cp_id}] Respuesta HCK_RESP inválida: {status}")
                    return
                if cod == 'FIN':
                    try:
                        print(f"[{cp_id}] 📩 Trama FIN recibida del Engine. Reenviando a Central...")
                        if trama_completa is not None:
                            # Reenviar la trama completa original (con STX, ETX y LRC)
                            central_socket.sendall(trama_completa)
                            print(f"[{cp_id}] 📤 Trama FIN reenviada a Central con éxito.")
                        else:
                            # Fallback: reconstruir si no tenemos la trama original (cifrado)
                            print(f"[{cp_id}] ⚠️ Advertencia: Reconstruyendo FIN (trama original no disponible)")
                            print(f"[{cp_id}]   Campos FIN: {args}")
                            trama_fin = construir_trama('FIN', args, cifrar=True)
                            central_socket.sendall(trama_fin)
                            print(f"[{cp_id}] ✅ FIN enviado exitosamente a Central (cifrado)")
                    except Exception as e:
                        print(f"[{cp_id}] ❌ ERROR al reenviar FIN a Central: {e}")
                        import traceback
                        traceback.print_exc()
                    return
                if cod == 'READY_TO_START':
                    try:
                        engine_cp_id = args[0] if len(args) > 0 else cp_id
                        driver_id = args[1] if len(args) > 1 else 'UNKNOWN'
                        print(f"[{cp_id}] 📩 READY_TO_START recibido del Engine (Driver: {driver_id})")
                        trama = construir_trama('READY_TO_START', [engine_cp_id, driver_id], cifrar=True)
                        central_socket.sendall(trama)
                        print(f"[{cp_id}] 📤 READY_TO_START reenviado a Central (cifrado)")
                    except Exception as e:
                        print(f"[{cp_id}] Error procesando READY_TO_START: {e}")
                    return
                if cod == 'AVR_CLR':
                    try:
                        # Reenviar a Central cifrado: AVR_CLR#cp_id#motivo#codigo
                        if trama_completa:
                            # Si tenemos la trama original del Engine, reconstruirla cifrada
                            trama_cifrada = construir_trama('AVR_CLR', args, cifrar=True)
                            central_socket.sendall(trama_cifrada)
                        else:
                            trama_cifrada = construir_trama('AVR_CLR', args, cifrar=True)
                            central_socket.sendall(trama_cifrada)
                        print(f"[{cp_id}] 📤 AVR_CLR reenviado a Central (cifrado)")
                    except Exception as e:
                        print(f"[{cp_id}] Error reenviando AVR_CLR a Central: {e}")
                    return
                if cod == 'REQUEST_STOP':
                    try:
                        engine_cp_id = args[0] if len(args) > 0 else cp_id
                        driver_id = args[1] if len(args) > 1 else 'UNKNOWN'
                        kw_actual = args[2] if len(args) > 2 else '0'
                        segundos = args[3] if len(args) > 3 else '0'
                        print(f"[{cp_id}] 📩 REQUEST_STOP recibido del Engine (Driver: {driver_id}, {kw_actual} kWh)")
                        trama = construir_trama('REQUEST_STOP', [engine_cp_id, driver_id, kw_actual, segundos], cifrar=True)
                        central_socket.sendall(trama)
                        print(f"[{cp_id}] 📤 REQUEST_STOP reenviado a Central (cifrado)")
                    except Exception as e:
                        print(f"[{cp_id}] Error procesando REQUEST_STOP: {e}")
                    return
                if cod == 'STATE':
                    try:
                        estado = args[1] if len(args) > 1 else 'ACTIVADO'
                        print(f"[{cp_id}] STATE desde Engine: {estado}.")
                        print(f"[{cp_id}] Avisando a Central del estado: {estado}.")
                        trama_state = construir_trama('STATE', [cp_id, estado], cifrar=True)
                        central_socket.sendall(trama_state)
                    except Exception as e:
                        print(f"[{cp_id}] Error reenviando STATE a Central: {e}")
                    return
                if cod == 'ACK':
                    detalle = args[0] if args else 'Sin detalle'
                    print(f"[{cp_id}] ACK tardío del Engine recibido: {detalle}")
                    return
                print(f"[{cp_id}] Trama inesperada desde Engine: {cod}")

            # Primer frame (bloqueante con timeout normal)
            respuesta_bytes = engine_socket.recv(1024)
            if not respuesta_bytes:
                raise ConnectionResetError("Engine cerró la conexión o respondió vacío.")
            
            # Nota: Los mensajes del Engine NO están cifrados, usar descomponer_trama normal
            # Verificar si es FIN antes de descomponerla para reenviarla completa
            if es_trama_fin(respuesta_bytes):
                print(f"[{cp_id}] 📩 Trama FIN recibida del Engine. Reenviando a Central (cifrado)...")
                try:
                    # Descomponer para obtener campos, luego reconstruir cifrado
                    cod_fin, campos_fin = descomponer_trama(respuesta_bytes)
                    if cod_fin == 'FIN':
                        trama_fin_cifrada = construir_trama('FIN', campos_fin, cifrar=True)
                        central_socket.sendall(trama_fin_cifrada)
                        print(f"[{cp_id}] 📤 Trama FIN reenviada a Central con éxito (cifrado).")
                except Exception as e:
                    print(f"[{cp_id}] ❌ ERROR al reenviar FIN a Central: {e}")
                    import traceback
                    traceback.print_exc()
                # También descomponer para logging opcional (Engine no cifra)
                cod_op, campos = descomponer_trama(respuesta_bytes)
                if cod_op == 'FIN':
                    print(f"[{cp_id}]   Campos FIN: {campos}")
                # No procesar más, el FIN ya fue reenviado
                continue
            
            # Engine no cifra, usar descomponer_trama normal
            cod_op, campos = descomponer_trama(respuesta_bytes)
            _procesar_trama_engine(cod_op, campos, respuesta_bytes if cod_op == 'FIN' else None)

            # Drenar frames adicionales que pudieran haber llegado encadenados (no bloquear)
            try:
                engine_socket.settimeout(0.01)
                while True:
                    extra = engine_socket.recv(1024)
                    if not extra:
                        break
                    # Verificar si es FIN antes de descomponerla para reenviarla completa
                    if es_trama_fin(extra):
                        print(f"[{cp_id}] 📩 Trama FIN recibida del Engine (frame adicional). Reenviando a Central (cifrado)...")
                        try:
                            # Descomponer para obtener campos, luego reconstruir cifrado
                            cod_fin_extra, campos_fin_extra = descomponer_trama(extra)
                            if cod_fin_extra == 'FIN':
                                trama_fin_cifrada = construir_trama('FIN', campos_fin_extra, cifrar=True)
                                central_socket.sendall(trama_fin_cifrada)
                                print(f"[{cp_id}] 📤 Trama FIN reenviada a Central con éxito (cifrado).")
                        except Exception as e:
                            print(f"[{cp_id}] ❌ ERROR al reenviar FIN a Central: {e}")
                            import traceback
                            traceback.print_exc()
                        # También descomponer para logging opcional (Engine no cifra)
                        cod_extra, campos_extra = descomponer_trama(extra)
                        if cod_extra == 'FIN':
                            print(f"[{cp_id}]   Campos FIN: {campos_extra}")
                        # No procesar más, el FIN ya fue reenviado
                        continue
                    # Engine no cifra, usar descomponer_trama normal
                    cod_extra, campos_extra = descomponer_trama(extra)
                    _procesar_trama_engine(cod_extra, campos_extra, extra if cod_extra == 'FIN' else None)
            except (socket.timeout, BlockingIOError):
                pass
            finally:
                engine_socket.settimeout(HCK_INTERVAL * 0.8)

        except socket.timeout:
            print(f"[{cp_id}] ⚠ Timeout HCK. Engine no responde. Notificando avería.")
            notificar_averia_central(central_socket, cp_id, "Timeout de HCK")
            if engine_socket:
                engine_socket.close()
            engine_socket = None # Forzar reconexión
            conexion_perdida_notificada = False
            
        except (ConnectionRefusedError, ConnectionResetError, BrokenPipeError, OSError) as e:
            if not conexion_perdida_notificada:
                print(f"[{cp_id}] ⚠ Conexión con Engine perdida. Reintentando reconexión...")
                notificar_averia_central(central_socket, cp_id, "Conexión con Engine perdida")
                conexion_perdida_notificada = True
            if engine_socket:
                engine_socket.close()
            engine_socket = None 

        except Exception as e:
            print(f"[{cp_id}] Error general en Hilo HCK: {e}")
            if engine_socket:
                engine_socket.close()
            engine_socket = None 
            conexion_perdida_notificada = False
            
        finally:
            # Esperar el intervalo antes de la siguiente comprobación
            time.sleep(HCK_INTERVAL)
            
def main():
    parser = argparse.ArgumentParser(description="Proceso EC_CP_M (Charging Point Monitor)")
    parser.add_argument("--engine_ip", type=str, required=True, help="IP del CP Engine")
    parser.add_argument("--engine_port", type=int, required=True, help="Puerto del CP Engine")
    parser.add_argument("--central_ip", type=str, required=True, help="IP del EV_Central")
    parser.add_argument("--central_port", type=int, required=True, help="Puerto del EV_Central")
    parser.add_argument("--cp_id", type=str, required=True, help="Identificador del Charging Point")
    args = parser.parse_args()

    print("="*40)
    print("[EC_CP_M] INICIADO")
    print(f"Conectando a Engine en: {args.engine_ip}:{args.engine_port}")
    print(f"Conectando a Central en: {args.central_ip}:{args.central_port}")
    print(f"ID del CP: {args.cp_id}")
    print("="*40)
    
    central_socket = None
    try:
        # 1. Registro en la Central
        central_socket = conectar_y_registrar(args.central_ip, args.central_port, args.cp_id)

        # 2. Hilo de escucha de comandos de la Central
        central_listener_thread = threading.Thread(
            target=escuchar_central,
            args=(central_socket, args.cp_id, args.engine_ip, args.engine_port),
            daemon=True
        )
        central_listener_thread.start()

        # 3. Hilo de Chequeo de Salud local (HCK)
        health_check_thread = threading.Thread(
            target=chequear_salud_engine,
            args=(args.engine_ip, args.engine_port, central_socket, args.cp_id),
            daemon=True
        )
        health_check_thread.start()

        print("\n[CP_M] Sistema ACTIVADO. Monitorización local de Engine iniciada.")

        # Bucle principal para mantener el proceso vivo
        while True:
            time.sleep(1)

    except Exception as e:
        print(f"[{args.cp_id}] Proceso EC_CP_M finalizado debido a un error crítico: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()