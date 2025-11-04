# ✅ Correcciones Aplicadas: Telemetría, Ticket y Lógica de Sesiones

## 📋 Problemas Reportados y Soluciones

### **1. ✅ RESUELTO: Botón de iniciar no debe aparecer sin driver activo**

**Cambios en:** `web_dashboard.py`

**Antes:**
- El botón "▶ Iniciar" aparecía siempre en estado ACTIVADO

**Ahora:**
- **ACTIVADO sin sesión**: "En espera de solicitud" (sin botón)
- **ACTIVADO con sesión**: "▶ Iniciar (DRIVER_ID)" (con botón)
- **CARGANDO**: "⏸ Detener"
- **PRE-SUMINISTRO**: "▶ Iniciar Carga"

---

### **2. ✅ RESUELTO: Evitar reiniciar después de finalizado**

**Cambios en:** `ev_central/EV_Central.py`

**Antes:**
- Se podía hacer START incluso sin sesión activa (creaba sesión de prueba)

**Ahora:**
- El comando START **requiere sesión activa**
- Si no hay sesión: "ERROR: No hay sesión activa en CP_001. Se requiere solicitud de driver primero."
- Solo un nuevo AUTH_REQ (solicitud de driver) puede crear una nueva sesión

---

### **3. 🔍 EN INVESTIGACIÓN: Telemetría no se actualiza en la web**

**Logging agregado en:**
- `web_dashboard.py`: Logs detallados de mensajes recibidos y API
- `ev_cp_engine/EV_CP_E.py`: Telemetría completa con todos los campos
- `ev_cp_monitor/EV_CP_M.py`: Logs de reenvío de FIN

**Para verificar:**

#### **Paso 1: Verificar que Engine publica a Kafka**

En terminal separada:
```powershell
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic telemetria_cp
```

Deberías ver mensajes cada segundo durante la carga:
```json
{
  "cp_id": "CP_001",
  "timestamp": 1762287345.52,
  "estado_carga": "CARGANDO",
  "kw_entregados": 2.45,
  "potencia_actual": 3.0,
  "tiempo_carga_s": 49,
  "tiene_sesion_activa": true,
  "driver_id_sesion": "DRIVER_001"
}
```

#### **Paso 2: Verificar logs del Dashboard**

Logs del Dashboard deben mostrar:
```
[DASHBOARD] ← Mensaje #15 | CP=CP_001 | Estado=CARGANDO | kW=2.45 | P=3.0 | t=49s
[API /api/cps] CP_001: kW=2.45, P=3.0, t=49s, sesion=True
```

Si **NO** ves estos logs:
- El Dashboard no está consumiendo de Kafka correctamente
- Verificar conexión Dashboard ↔ Kafka

Si **SÍ** ves estos logs pero la web no actualiza:
- Problema en el frontend (navegador)
- Refrescar con Ctrl+F5
- Verificar la consola del navegador (F12)

#### **Paso 3: Endpoint de debug**

Acceder a: `http://localhost:8080/api/debug`

Debe mostrar:
```json
{
  "telemetria": {
    "CP_001": {
      "kw_entregados": 2.45,
      "potencia_actual": 3.0,
      "tiempo_carga_s": 49,
      ...
    }
  }
}
```

---

### **4. 🔍 EN INVESTIGACIÓN: Driver no recibe ticket al detener desde web**

**Logging agregado en:**
- `ev_cp_engine/EV_CP_E.py`: Logs detallados de FIN al hacer STOP
- `ev_cp_monitor/EV_CP_M.py`: Logs de reenvío de FIN a Central
- `ev_central/EV_Central.py`: Logs de procesamiento de FIN y envío de ticket

**Para verificar:**

#### **Flujo esperado al hacer STOP desde web:**

1. **Web → Central**: Comando STOP
2. **Central → Monitor → Engine**: CMD STOP
3. **Engine**: Detiene carga y envía FIN al Monitor
   ```
   [CP_001] FIN enviado a Monitor (STOP manual). kWh=2.45, €=1.18, dur_s=49, tx=TX-CP_001-...
   ```

4. **Monitor → Central**: Reenvía FIN
   ```
   [CP_001] ✅ FIN recibido del Engine. Reenviando a Central.
   [CP_001]   Campos FIN: ['CP_001', 'DRIVER_001', '2.45', '1.18', '49', 'Detenido manualmente', 'TX-...']
   [CP_001] ✅ FIN enviado exitosamente a Central
   ```

5. **Central**: Procesa FIN y envía ticket
   ```
   [CENTRAL] ✅ Ticket enviado a DRIVER_001. CP CP_001 listo para nuevo servicio.
   [CENTRAL] CP CP_001 resetado y listo para nuevo servicio (ACTIVADO)
   ```

6. **Driver**: Recibe ticket y termina
   ```
   ============================================================
              🧾 TICKET FINAL - DRIVER DRIVER_001
   ============================================================
     Punto de Carga:  CP_001
     Energía:         2.45 kWh
     Importe:         1.18 €
     Duración:        49 segundos
     ID Transacción:  TX-CP_001-1762287345
   ============================================================
   
   [DRIVER DRIVER_001] ✅ Ticket recibido. Terminando proceso.
   [DRIVER DRIVER_001] 🚗 Servicio completado exitosamente. Adiós!
   ```

#### **Si el driver NO recibe el ticket:**

**Verificar en logs del Monitor (PC_B):**
- ¿Aparece "✅ FIN recibido del Engine"?
- ¿Aparece "✅ FIN enviado exitosamente a Central"?

**Verificar en logs de la Central (PC_A):**
- ¿Aparece "[CENTRAL] ✅ Ticket enviado a DRIVER_XXX"?
- ¿Aparece error al enviar a Kafka?

**Verificar en Kafka:**
```powershell
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic driver_status_DRIVER_001
```

Deberías ver:
```json
{
  "driver_id": "DRIVER_001",
  "evento": "TICKET_FINAL",
  "detalle": {
    "cp_id": "CP_001",
    "energia_kwh": "2.45",
    "importe_eur": "1.18",
    ...
  }
}
```

---

## 🧪 Script de Prueba Completo

### **Terminal 1 - Dashboard (PC_A)**
```powershell
py web_dashboard.py --kafka 192.168.1.43:9092 --central-ip 192.168.1.43 --central-port 5000
```

### **Terminal 2 - Driver (PC_A o PC_B)**
```bash
py ev_driver/EV_Driver.py --kafka 192.168.1.43:9092 --id DRIVER_001 --cp CP_001 --kw 5.0 --listen
```

### **Navegador**
1. Abrir: `http://localhost:8080`
2. Esperar a que CP_001 aparezca en estado PRE-SUMINISTRO
3. Click en "▶ Iniciar Carga"
4. Observar que la energía, potencia y tiempo se actualizan
5. Después de 2-3 kWh, click en "⏸ Detener"
6. Verificar:
   - Driver recibe ticket
   - Driver termina su proceso
   - CP queda en ACTIVADO sin botón de inicio

### **Terminal 3 - Verificar Kafka (opcional)**
```powershell
# Telemetría
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic telemetria_cp

# Tickets del driver
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic driver_status_DRIVER_001
```

---

## 📊 Campos de Telemetría Actualizados

El Engine ahora publica telemetría **completa**:

| Campo | Descripción | Actualización |
|-------|-------------|---------------|
| `cp_id` | ID del CP | Constante |
| `timestamp` | Marca de tiempo | Cada 1s |
| `estado_carga` | Estado actual | CARGANDO/ACTIVADO/REPOSO |
| `estado` | (duplicado) | Compatibilidad |
| `kw_entregados` | Energía acumulada | +0.05 cada 1s |
| `energia_total` | (duplicado) | Compatibilidad |
| `potencia_actual` | Potencia en kW | 3.0 kW constante |
| `tiempo_carga_s` | Tiempo transcurrido | +1 cada 1s |
| `tiene_sesion_activa` | Boolean | true/false |
| `driver_id_sesion` | ID del driver | DRIVER_XXX o null |

---

## 🔧 Archivos Modificados

1. **`ev_central/EV_Central.py`**
   - Validación de sesión activa para START
   - Logs mejorados de FIN y ticket

2. **`ev_cp_engine/EV_CP_E.py`**
   - Telemetría completa con todos los campos
   - FIN detallado con todos los datos

3. **`ev_cp_monitor/EV_CP_M.py`**
   - Logs detallados de reenvío de FIN

4. **`web_dashboard.py`**
   - Lógica de botones según sesión activa
   - Logs de API y telemetría
   - Validación de sesión para mostrar botones

5. **`ev_driver/EV_Driver.py`** (corregido anteriormente)
   - Termina proceso al recibir ticket
   - Formato bonito de ticket

---

## ⚠️ Importante

**Una vez que se detiene una sesión:**
- Se envía el ticket al driver
- Se limpia la sesión
- El CP queda en ACTIVADO
- **NO se puede reiniciar** sin una nueva solicitud de driver
- El botón de inicio **NO aparece** hasta que un nuevo driver solicite

**Flujo correcto para nueva carga:**
1. Driver lanza solicitud: `py ev_driver/EV_Driver.py ...`
2. Central crea sesión y autoriza
3. CP pasa a PRE-SUMINISTRO
4. Web muestra botón "▶ Iniciar Carga"
5. Operador inicia desde web
6. Carga completa o detención manual
7. Ticket enviado y sesión limpiada
8. Repetir desde paso 1 para nuevo servicio

---

## 📝 Próximos Pasos

1. **Reiniciar todos los componentes** para aplicar cambios
2. **Ejecutar script de prueba** completo
3. **Verificar logs** en cada paso del flujo
4. **Reportar** qué logs aparecen y cuáles no

Si la telemetría sigue sin actualizarse después de reiniciar, **proporciona:**
- Logs del Dashboard cuando esté cargando
- Output del consumer de Kafka de telemetria_cp
- Respuesta del endpoint `/api/debug`

