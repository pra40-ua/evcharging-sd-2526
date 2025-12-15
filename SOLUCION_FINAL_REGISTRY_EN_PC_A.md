# 🔧 SOLUCIÓN FINAL: Registry debe estar en PC_A

## 🎯 PROBLEMA ACTUAL

Central en PC_A busca Registry en `127.0.0.1:6000` (localhost de PC_A), pero Registry está corriendo en PC_B.

**Error:**
```
[CENTRAL] ⚠️ Error verificando registro en EV_Registry: HTTPSConnectionPool(host='127.0.0.1', port=6000)
[WinError 10061] No se puede establecer una conexión
```

---

## ✅ ARQUITECTURA CORRECTA

```
┌─────────────────────────────────────────┐
│              PC_A (SERVIDOR)            │
│                                         │
│  ┌─────────────┐  ┌──────────────┐    │
│  │   Kafka     │  │    MySQL     │    │
│  │   :9092     │  │    :3306     │    │
│  └─────────────┘  └──────────────┘    │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │       EV_Registry  :6000        │   │
│  │  (HTTPS - localhost)            │   │
│  └─────────────────────────────────┘   │
│               ↓ consulta                │
│  ┌─────────────────────────────────┐   │
│  │       EV_Central   :5000        │   │
│  │  REGISTRY_URL=https://127...    │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │     Dashboard Web  :8080        │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
                  ↑
                  │ Red local
                  │
┌─────────────────────────────────────────┐
│              PC_B (CLIENTE)             │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │       EV_Weather                │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │     CP_001 (Docker)             │   │
│  │  - Engine                       │   │
│  │  - Monitor  → Registry en PC_A  │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │     CP_002, CP_003...           │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

---

## 🚀 PASOS PARA CORREGIR

### **En PC_B (donde estás ahora):**

1. **Cierra la ventana de EV_Registry_PC_B**
   ```
   ❌ Cerrar ventana: "EV_Registry_PC_B"
   ```

2. **Verifica que `central_ip.txt` existe**
   - Debe contener la IP de PC_A (ejemplo: `192.168.1.43`)

---

### **En PC_A (el servidor):**

3. **Ejecuta `INICIAR_REGISTRY.bat`** (sin el sufijo `_PC_B`)
   ```cmd
   INICIAR_REGISTRY.bat
   ```
   
   Esto hará:
   - ✅ Detecta que no hay `central_ip.txt` → Usa `127.0.0.1` (localhost)
   - ✅ Se conecta a MySQL local (`127.0.0.1:3306`)
   - ✅ Inicia Registry en `https://localhost:6000`
   - ✅ Central puede conectarse porque ambos están en PC_A

4. **NO reinicies Central** - Ya está configurado correctamente
   - Central ya busca Registry en `https://127.0.0.1:6000` ✅

---

### **De vuelta en PC_B:**

5. **Ejecuta normalmente `PC_B_RUN.bat`**
   
   El script detectará automáticamente Registry:
   - Primero busca localhost (`127.0.0.1`) → No encuentra ❌
   - Luego busca en PC_A usando `central_ip.txt` → ✅ Encuentra Registry
   - Configura: `REGISTRY_URL=https://192.168.1.43:6000/api`
   - Los CPs usarán Registry en PC_A ✅

---

## 📊 FLUJO COMPLETO CORREGIDO

### **Orden de ejecución:**

```
1. PC_A: PC_A_RUN.bat
   └─ Inicia: Kafka, MySQL, Central, Dashboard

2. PC_A: INICIAR_REGISTRY.bat
   └─ Inicia: Registry (localhost, BD local)

3. PC_B: PC_B_RUN.bat
   └─ Inicia: Weather + CPs
   └─ CPs se registran con Registry en PC_A (remoto)
   └─ CPs se conectan a Central en PC_A
   └─ Central verifica credenciales con Registry (local ✅)
```

---

## 🔍 VERIFICACIÓN

### **En PC_A, verás en la ventana de Registry:**

```
[EV_Registry] ✓ CP registrado: CP_001
[EV_Registry]   Origen IP: 192.168.1.36 (PC_B)
[EV_Registry]   Credenciales generadas
```

### **En PC_A, verás en la ventana de Central:**

```
[CENTRAL] ╔═══════════════════════════════════════════╗
[CENTRAL] ║  🔐 VERIFICANDO CREDENCIALES CON REGISTRY  ║
[CENTRAL] ╚═══════════════════════════════════════════╝
[CENTRAL]    Consultando Registry en: https://127.0.0.1:6000/api/authenticate
[CENTRAL] ✓ CREDENCIALES VERIFICADAS
[CENTRAL] ✓ AUTH OK enviado a CP_001
```

### **En PC_B, verás en la ventana del CP:**

```
[CP_M] PASO 1: OBTENIENDO CREDENCIALES DE EV_Registry
[CP_M]   Registry URL: https://192.168.1.43:6000/api
[CP_M] ✓ Credenciales obtenidas

[CP_M] PASO 2: ENVIANDO REG A CENTRAL
[CP_M] ✅ AUTENTICACIÓN EXITOSA
```

---

## ⚠️ IMPORTANTE: Firewall en PC_A

Si los CPs en PC_B no pueden conectarse con Registry en PC_A, abre el firewall:

**En PC_A (PowerShell como Admin):**
```powershell
New-NetFirewallRule -DisplayName "EV_Registry" -Direction Inbound -LocalPort 6000 -Protocol TCP -Action Allow
```

---

## 📝 RESUMEN

| Componente | PC | Puerto | Conecta con |
|------------|-----|--------|-------------|
| Kafka | PC_A | 9092 | - |
| MySQL | PC_A | 3306 | - |
| **Registry** | **PC_A** | **6000** | **MySQL (local)** |
| Central | PC_A | 5000 | Registry (local), MySQL (local), Kafka (local) |
| Dashboard | PC_A | 8080 | Central API, Kafka |
| Weather | PC_B | - | Central API (remoto) |
| CPs | PC_B | Docker | Registry (remoto PC_A), Central (remoto PC_A), Kafka (remoto PC_A) |

---

## ✅ CHECKLIST FINAL

- [ ] **PC_B:** Cerrar ventana `EV_Registry_PC_B`
- [ ] **PC_A:** Ejecutar `INICIAR_REGISTRY.bat`
- [ ] **PC_A:** Verificar ventana Registry abierta
- [ ] **PC_B:** Ejecutar `PC_B_RUN.bat`
- [ ] **PC_B:** Verificar que CP se registra correctamente
- [ ] **PC_A:** Verificar mensaje de verificación de credenciales en Central

---

## 🎓 CONCLUSIÓN

**NO necesitas generar nuevos certificados.** El problema era de arquitectura:
- ✅ Los certificados SSL son correctos
- ✅ HTTPS está configurado correctamente
- ❌ Registry estaba en PC incorrecto

Con Registry en PC_A, todo funcionará correctamente porque Central y Registry estarán en el mismo servidor y podrán comunicarse por localhost. 🚀



