# 🖥️ Guía: Usar en Diferentes Ordenadores

## 📋 Resumen

**DOS SCRIPTS PRINCIPALES:**
- `PC_A_COMPLETO.bat` → Para el ordenador servidor (Central)
- `PC_B_COMPLETO.bat` → Para el ordenador de puntos de recarga (CPs + Drivers)

**¡Eso es todo!** Cada script hace TODO automáticamente.

---

## 🚀 Instalación Inicial (Solo Primera Vez)

### En Ambos Ordenadores (PC_A y PC_B)

#### 1. Instalar Python
```
https://www.python.org/downloads/
```
⚠️ **IMPORTANTE**: Durante instalación, marcar **"Add Python to PATH"**

#### 2. Instalar Docker Desktop (Solo PC_A)
```
https://www.docker.com/products/docker-desktop/
```
Solo es necesario en PC_A. PC_B puede funcionar sin Docker.

#### 3. Clonar Repositorio
```bash
git clone <url_repositorio>
cd evcharging-sd-2526
```

---

## 🎬 Uso Normal

### PASO 1: En PC_A (Servidor Central)

```batch
PC_A_COMPLETO.bat
```

**¿Qué hace este script?**
1. ✅ Verifica Python instalado
2. ✅ Instala dependencias automáticamente
3. ✅ Verifica Docker
4. ✅ Inicia Kafka + MySQL (Docker Compose)
5. ✅ Detecta IP local automáticamente
6. ✅ Guarda IP en `central_ip.txt`
7. ✅ Inicia EV_Central

**Al finalizar:**
- Se abre una ventana con EV_Central corriendo
- Se crea archivo `central_ip.txt` con la IP de PC_A

### PASO 2: Copiar `central_ip.txt` a PC_B

**Opción A: Carpeta compartida en red**
```batch
copy central_ip.txt \\PC_B\proyecto\
```

**Opción B: USB/Correo/Cualquier método**
- Copia el archivo `central_ip.txt` desde PC_A a PC_B
- Colócalo en la raíz del proyecto en PC_B

**Opción C: Manual**
- Abre `central_ip.txt` en PC_A
- Copia la IP (ej: `192.168.1.43`)
- El script de PC_B te pedirá la IP si no encuentra el archivo

### PASO 3: En PC_B (Puntos de Recarga)

```batch
PC_B_COMPLETO.bat
```

**¿Qué hace este script?**
1. ✅ Verifica Python instalado
2. ✅ Instala dependencias automáticamente
3. ✅ Lee IP de Central desde `central_ip.txt`
4. ✅ Te pregunta cuántos CPs lanzar
5. ✅ Te pregunta cuántos Drivers lanzar
6. ✅ Verifica conectividad con Central
7. ✅ Lanza los CPs (Engine + Monitor cada uno)
8. ✅ Lanza los Drivers

**Al finalizar:**
- Se abren 2 ventanas: una para CPs, otra para Drivers
- Los CPs se registran automáticamente en la Central

---

## 📊 Ejemplo Completo

### Escenario: Demostración con 10 CPs y 8 Drivers

#### PC_A:
```batch
PC_A_COMPLETO.bat
```
- Esperar a que termine (30-60 segundos primera vez)
- Se abre ventana de Central
- Se crea `central_ip.txt`

#### PC_B:
```batch
REM Copiar central_ip.txt desde PC_A primero

PC_B_COMPLETO.bat
```
- Cuando pregunte: **10** CPs
- Cuando pregunte: **8** Drivers
- Seleccionar modo: **1** (Random)

#### Resultado:
- 10 CPs registrados en Central
- 8 Drivers solicitando servicio
- Todo funcionando en red local

---

## 🌐 Configuración de Red

### Firewall en PC_A (si están en red local)

Si PC_B está en otro ordenador físico, abre estos puertos en PC_A:

```powershell
# Ejecutar PowerShell como Administrador en PC_A

New-NetFirewallRule -DisplayName "Kafka" -Direction Inbound -LocalPort 9092 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Central" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "MySQL" -Direction Inbound -LocalPort 3306 -Protocol TCP -Action Allow
```

O manualmente:
1. Panel de Control → Firewall de Windows → Configuración avanzada
2. Reglas de entrada → Nueva regla
3. Puerto → TCP → Específicos: 5000, 9092, 3306
4. Permitir conexión

---

## 🔍 Verificación

### En PC_A (Central)

Deberías ver en la ventana de Central:
```
[CP_M] CP001 REGISTRO EXITOSO!
[CP_M] CP002 REGISTRO EXITOSO!
...
[CENTRAL] Recibida solicitud de DRIVER_001
[CENTRAL] Recibida solicitud de DRIVER_002
...
```

### En PC_B

Ventana de CPs:
```
✓ CP001 lanzado (PID: xxxx)
✓ CP002 lanzado (PID: xxxx)
...
```

Ventana de Drivers:
```
✓ DRIVER_001 lanzado (PID: xxxx)
✓ DRIVER_002 lanzado (PID: xxxx)
...
```

---

## 📱 Dashboard Web (Opcional)

En **cualquier PC** conectado a la red:

```bash
python web_dashboard.py --kafka <IP_PC_A>:9092
```

Ejemplo:
```bash
python web_dashboard.py --kafka 192.168.1.43:9092
```

Accede en navegador: **http://localhost:8080**

---

## 🔧 Parámetros Personalizables

### En PC_B_COMPLETO.bat

Al ejecutar, te preguntará:

**1. Número de CPs:**
```
Numero de CPs [default: 3]: 10
```
Introduce el número deseado (ej: 10 para demostración al profesor)

**2. Número de Drivers:**
```
Numero de Drivers [default: 2]: 8
```
Introduce el número deseado (ej: 8 para demostración)

**3. Modo de asignación:**
```
[1] Random   - Asignacion aleatoria
[2] Uniform  - Distribucion uniforme
[3] First    - Todos al primer CP
Selecciona modo [1-3, default: 1]: 1
```

---

## 🛠️ Solución de Problemas

### "Python no está instalado"
1. Descarga desde https://www.python.org/downloads/
2. Durante instalación: ☑️ **"Add Python to PATH"**
3. Reinicia el ordenador
4. Ejecuta el script de nuevo

### "Docker no está corriendo" (Solo PC_A)
1. Abre Docker Desktop
2. Espera a ver "Docker Desktop is running"
3. Ejecuta el script de nuevo

### "No se encuentra central_ip.txt" (PC_B)
- Opción A: Copia el archivo desde PC_A
- Opción B: El script te pedirá introducir la IP manualmente

### "No se puede conectar a Central"
1. Verifica que PC_A tiene Central corriendo
2. Verifica la IP en `central_ip.txt`
3. Haz ping desde PC_B: `ping <IP_PC_A>`
4. Abre firewall en PC_A (ver sección Firewall)
5. Verifica que ambos están en la misma red

### Los CPs no se registran
1. Ve a la ventana de Central en PC_A
2. Busca mensajes de error
3. Verifica IP en `central_ip.txt`
4. Prueba ping: `ping <IP_PC_A>`
5. Verifica firewall

---

## 📦 Archivos Generados

### En PC_A:
- `central_ip.txt` - IP del servidor (compartir con PC_B)
- `commands_PC_A.ps1` - Script de PowerShell generado
- Logs de Docker Compose

### En PC_B:
- `central_ip.txt` - Copiado desde PC_A (o creado manualmente)

---

## 🔄 Ejecuciones Posteriores

### PC_A (días siguientes):
```batch
PC_A_COMPLETO.bat
```
- Ya no necesitas instalar dependencias (ya están)
- Kafka y MySQL mantienen datos (volúmenes persistentes)

### PC_B (días siguientes):
```batch
PC_B_COMPLETO.bat
```
- Ya no necesitas instalar dependencias
- `central_ip.txt` sigue siendo válido si PC_A mantiene la IP

---

## 🎓 Para Demostración al Profesor

### Setup Rápido (5 minutos):

**PC_A:**
```batch
PC_A_COMPLETO.bat
```
Esperar → Copiar `central_ip.txt`

**PC_B:**
```batch
PC_B_COMPLETO.bat
```
- CPs: **10**
- Drivers: **8**
- Modo: **1** (Random)

### Dashboard (Opcional):
```bash
python web_dashboard.py --kafka <IP_PC_A>:9092
```
Abrir: http://localhost:8080

### Mostrar:
1. ✅ Ventana Central con 10 CPs registrados
2. ✅ Ventana CPs con Engine + Monitor
3. ✅ Ventana Drivers con 8 clientes
4. ✅ Dashboard web con estadísticas en tiempo real

---

## 📝 Resumen de Comandos

```batch
# PC_A (Servidor Central)
PC_A_COMPLETO.bat

# Copiar central_ip.txt a PC_B

# PC_B (Puntos de Recarga + Drivers)
PC_B_COMPLETO.bat

# Dashboard (opcional, en cualquier PC)
python web_dashboard.py --kafka <IP_PC_A>:9092
```

---

## 🎯 Ventajas de Este Sistema

✅ **UN SOLO SCRIPT por ordenador** - Simplicidad máxima
✅ **Auto-instalación** - Instala dependencias automáticamente
✅ **Auto-configuración** - Detecta IP automáticamente
✅ **Interactivo** - Te pregunta parámetros (número de CPs/Drivers)
✅ **Verificaciones** - Comprueba conectividad antes de continuar
✅ **Mensajes claros** - Instrucciones paso a paso
✅ **Resiliente** - Continúa aunque haya advertencias menores
✅ **Completo** - Incluye todo (Kafka, MySQL, Central, CPs, Drivers)

---

**¡Dos scripts, dos ordenadores, todo funcionando! 🚀**


