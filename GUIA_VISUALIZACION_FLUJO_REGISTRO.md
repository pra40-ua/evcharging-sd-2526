# 📋 GUÍA: Cómo Verificar el Flujo de Registro CP → Registry → Central

## 🎯 Objetivo
Cuando lances un CP en PC_B, verás mensajes en **3 ventanas diferentes** que muestran el flujo completo de registro y autenticación.

---

## 📺 Ventanas que debes tener abiertas:

### 1️⃣ **Ventana: EV_Registry (PC_B)**
   - Ya la tienes abierta ejecutando en `https://192.168.1.36:6000`
   - Aquí verás las solicitudes de autenticación

### 2️⃣ **Ventana: EV_Central (PC_A)**
   - Ejecutándose en el otro PC (`192.168.1.43:5000`)
   - Esta ventana muestra cuando verifica credenciales con Registry

### 3️⃣ **Ventana: CP Monitor (PC_B)** 
   - Se abrirá cuando ejecutes `INICIAR_CP01.bat`
   - Muestra el proceso de conexión del CP

---

## 🔄 FLUJO COMPLETO DE MENSAJES (Paso a Paso)

### ⏱️ **PASO 1: Lanzar el CP**

**Comando:**
```cmd
INICIAR_CP01.bat
```

---

### 📱 **Ventana CP Monitor (PC_B)** - Verás:

```
======================================================================
  [CP_M] PASO 1: OBTENIENDO CREDENCIALES DE EV_Registry
======================================================================

[CP_M] Conectando a EV_Registry: https://192.168.1.36:6000
[CP_M] Solicitando registro/credenciales para CP_01...

[CP_M] ✓ RESPUESTA DE REGISTRY RECIBIDA:
[CP_M]   Status: registered
[CP_M]   CP_ID: CP_01
[CP_M]   Username: cp_01_user
[CP_M]   Password: ********** (recibido, será enviado a Central)

[CP_M] ✓ Credenciales obtenidas exitosamente desde EV_Registry
```

**✅ AQUÍ CONFIRMAS:** El CP se está **registrando con Registry** y obteniendo credenciales.

---

### 🖥️ **Ventana EV_Registry (PC_B)** - Simultáneamente verás:

```
127.0.0.1 - - [14/Dec/2025 10:30:15] "POST /api/register HTTP/1.1" 200 -
[EV_Registry] ✓ CP registrado: CP_01
[EV_Registry]   Ubicación: Alicante
[EV_Registry]   Credenciales generadas:
[EV_Registry]     Username: cp_01_user
[EV_Registry]     Password hash: ********

[EV_Registry] 📋 Credenciales almacenadas en BD (PC_A: 192.168.1.43)
```

**✅ AQUÍ CONFIRMAS:** Registry **generó las credenciales** y las guardó en la BD de PC_A.

---

### 📱 **Ventana CP Monitor (PC_B)** - Continúa:

```
======================================================================
  [CP_M] PASO 2: ENVIANDO REG A CENTRAL CON CREDENCIALES
======================================================================

[CP_M] Conectando a Central: 192.168.1.43:5000
[CP_M] Conexión con Central establecida. Enviando REG...

[CP_M] ✓ Enviando REG con credenciales del Registry:
[CP_M]   CP_ID: CP_01
[CP_M]   Username: cp_01_user
[CP_M]   Password: 3a7f8b2c9d... (enviado completo)
======================================================================

[CP_M] Esperando respuesta de Central...
```

**✅ AQUÍ CONFIRMAS:** El CP está **enviando las credenciales a Central** para autenticación.

---

### 🏢 **Ventana EV_Central (PC_A)** - MENSAJE CLAVE:

```
[CENTRAL] Recibida conexión desde: 192.168.1.36:xxxxx
[CENTRAL] Mensaje REG recibido de CP_01

[CENTRAL] ╔═══════════════════════════════════════════╗
[CENTRAL] ║  🔐 VERIFICANDO CREDENCIALES CON REGISTRY  ║
[CENTRAL] ╚═══════════════════════════════════════════╝
[CENTRAL]    CP ID: CP_01
[CENTRAL]    Username: cp_01_user
[CENTRAL]    Verificando con EV_Registry...

[CENTRAL] 🌐 Consultando EV_Registry en: https://192.168.1.43:6000/api/authenticate
[CENTRAL]    Payload: {"username": "cp_01_user", "password": "3a7f8b2c9d..."}
```

**✅ AQUÍ CONFIRMAS:** Central está **consultando a Registry** para validar credenciales.

---

### 🖥️ **Ventana EV_Registry (PC_B o PC_A)** - Verás la consulta:

```
192.168.1.43 - - [14/Dec/2025 10:30:16] "POST /api/authenticate HTTP/1.1" 200 -
[EV_Registry] 🔐 Solicitud de autenticación recibida
[EV_Registry]   Username: cp_01_user
[EV_Registry]   Verificando en BD...

[EV_Registry] ✓ CREDENCIALES VÁLIDAS
[EV_Registry]   CP_ID verificado: CP_01
[EV_Registry]   Usuario autenticado correctamente
[EV_Registry]   Respondiendo: {"status": "ok", "cp_id": "CP_01"}
```

**✅ AQUÍ CONFIRMAS:** Registry **validó las credenciales** y respondió OK a Central.

---

### 🏢 **Ventana EV_Central (PC_A)** - Respuesta de Registry:

```
[CENTRAL] ✓ CREDENCIALES VERIFICADAS
[CENTRAL]    EV_Registry confirmó que las credenciales son correctas
[CENTRAL]    Autenticación exitosa mediante Registry
[CENTRAL] ═══════════════════════════════════════════

[CENTRAL] ✓ AUTH OK: CP_01 autenticado con credenciales del Registry

[CENTRAL] 🔐 Generando clave de cifrado para CP_01...
[CENTRAL] ✓ Clave de cifrado generada y almacenada en BD

[CENTRAL] -> Enviando AUTH:OK a CP_01 con clave de cifrado
```

**✅ AQUÍ CONFIRMAS:** Central **aceptó la autenticación** y envió respuesta al CP.

---

### 📱 **Ventana CP Monitor (PC_B)** - Respuesta final:

```
[CP_M] Recibida respuesta de Central

[CP_M] ✅ AUTENTICACIÓN EXITOSA
[CP_M]    Central aceptó las credenciales del Registry
[CP_M]    Mensaje: Autenticación mediante EV_Registry exitosa

[CP_M] 🔐 Clave de cifrado recibida de Central
[CP_M]    Activando comunicación cifrada...
[CP_M]    ✓ Cifrado E2E habilitado

======================================================================
  CP_01 - REGISTRO EXITOSO Y COMUNICACIÓN ESTABLECIDA
======================================================================
Estado: ACTIVADO
Conectado a: 192.168.1.43:5000
Cifrado: ✓ Habilitado
Autenticación: ✓ Mediante EV_Registry

Esperando órdenes de Central...
```

**✅ AQUÍ CONFIRMAS:** ¡El CP está **completamente conectado y autenticado**!

---

## 🔍 RESUMEN: ¿Qué buscar en cada ventana?

| Ventana | Mensaje Clave | Qué Confirma |
|---------|---------------|--------------|
| **CP Monitor** | `PASO 1: OBTENIENDO CREDENCIALES` | CP se registra con Registry |
| **Registry** | `✓ CP registrado: CP_01` | Registry genera credenciales |
| **CP Monitor** | `PASO 2: ENVIANDO REG CON CREDENCIALES` | CP envía credenciales a Central |
| **Central** | `🔐 VERIFICANDO CREDENCIALES CON REGISTRY` | Central consulta Registry |
| **Registry** | `🔐 Solicitud de autenticación` + `✓ CREDENCIALES VÁLIDAS` | Registry valida y responde |
| **Central** | `✓ CREDENCIALES VERIFICADAS` + `AUTH OK` | Central acepta autenticación |
| **CP Monitor** | `✅ AUTENTICACIÓN EXITOSA` | CP conectado correctamente |

---

## 🚨 ¿Qué pasa si algo falla?

### ❌ **Si Registry no responde:**
```
[CP_M] ❌ ERROR: No se pudo conectar a EV_Registry
[CP_M]    URL: https://192.168.1.36:6000
[CP_M]    Verifica que INICIAR_REGISTRY_PC_B.bat esté ejecutándose
```

### ❌ **Si Central rechaza credenciales:**
```
[CENTRAL] ❌ CREDENCIALES INVÁLIDAS
[CENTRAL]    El Registry rechazó las credenciales proporcionadas
[CP_M] ❌ AUTH FAIL: Credenciales inválidas
```

### ❌ **Si CP no está registrado:**
```
[CENTRAL] ❌ AUTH DENEGADO: CP_01 no registrado en EV_Registry
[CP_M] ❌ AUTH FAIL: CP no registrado. Debe registrarse primero.
```

---

## 🎓 CONCLUSIÓN

**Sabrás que todo funciona correctamente cuando veas:**

1. ✅ CP obtiene credenciales de **Registry** (Ventana CP)
2. ✅ **Registry** muestra registro exitoso
3. ✅ CP envía credenciales a **Central**
4. ✅ **Central** consulta a **Registry** (mensaje `VERIFICANDO CREDENCIALES`)
5. ✅ **Registry** confirma credenciales válidas
6. ✅ **Central** envía AUTH:OK
7. ✅ CP recibe autenticación exitosa y activa cifrado

**El flujo completo Registry ← → Central está funcionando si ves el recuadro:**
```
[CENTRAL] ╔═══════════════════════════════════════════╗
[CENTRAL] ║  🔐 VERIFICANDO CREDENCIALES CON REGISTRY  ║
[CENTRAL] ╚═══════════════════════════════════════════╝
```

---

## 📸 TIP: Organiza tus ventanas

Coloca las ventanas así para ver el flujo en tiempo real:

```
┌─────────────────┬─────────────────┐
│   EV_Registry   │   EV_Central    │
│     (PC_B)      │     (PC_A)      │
├─────────────────┴─────────────────┤
│         CP Monitor (PC_B)         │
└───────────────────────────────────┘
```

¡Así verás el flujo completo de mensajes sincronizados! 🚀

