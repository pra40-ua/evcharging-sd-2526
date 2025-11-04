# Sistema de Múltiples Charging Points - PC_B

## 🎯 Descripción

Este sistema permite lanzar hasta **5 Charging Points (CPs) simultáneamente** en PC_B, cada uno en su propia terminal interactiva.

Cada terminal de CP muestra:
- ✅ **Estado actual** del CP (Available, Charging, Pre-Suministro, etc.)
- 📡 **Comunicaciones OCPP-like** (mensajes enviados y recibidos)
- 🎮 **Menú interactivo** para simular acciones del conductor

---

## 🚀 Cómo Usar

### Opción 1: Lanzador Principal (Recomendado)

1. Ejecuta `PC_B_RUN.bat`
2. Selecciona la opción **[1] NUEVO: Multiples CPs**
3. Indica cuántos CPs quieres lanzar (1-5)
4. El sistema construirá las imágenes Docker y lanzará cada CP en su terminal

```batch
PC_B_RUN.bat
```

### Opción 2: Lanzador Directo de Múltiples CPs

Si ya sabes que quieres múltiples CPs, puedes ejecutar directamente:

```batch
PC_B_RUN_MULTIPLE_CPS.bat
```

### Opción 3: Lanzar un CP Individual (PowerShell)

Para lanzar un CP específico manualmente:

```powershell
.\launch_single_cp.ps1 -CpId "CP_001" -EnginePort 5001 -CentralIp "192.168.1.43"
```

---

## 📺 Interfaz de Cada CP

Cada CP tendrá **2 terminales**:

### Terminal 1: ENGINE (Puerto 5001, 5002, ...)
```
======================================================================
  CHARGING POINT: CP_001
======================================================================
  Estado: DISPONIBLE (Available)
======================================================================

  MENÚ DE SIMULACIÓN DEL CONDUCTOR:
    [p] Enchufar vehículo (Plug)
    [d] Desenchufar vehículo (Unplug)
    [r] Simular RFID / Iniciar sesión
    [s] Mostrar estado actual
    [h] Ayuda
    [q] Salir
======================================================================

[CP_001] Acción: _
```

### Terminal 2: MONITOR
Muestra la comunicación con la Central y el estado de salud del Engine.

---

## 🎮 Comandos Disponibles en el Engine

| Comando | Descripción | Ejemplo de Uso |
|---------|-------------|----------------|
| **p** | Enchufar vehículo | Simula que un vehículo se conecta físicamente al CP |
| **d** | Desenchufar vehículo | Simula que un vehículo se desconecta del CP |
| **r** | Simular RFID | Información sobre autenticación (normalmente se hace desde la web) |
| **s** | Mostrar estado | Muestra el estado actual completo del CP |
| **h** | Ayuda | Muestra el menú de ayuda |
| **q** | Salir | Cierra el menú interactivo (el CP sigue funcionando) |

---

## 📡 Mensajes OCPP-like Visibles

El sistema muestra claramente los mensajes intercambiados:

### Ejemplo: Inicio de Carga
```
======================================================================
  [CP_001] 📩 MENSAJE RECIBIDO: CMD START
  Driver: DRIVER_123
  Objetivo: 10.0 kWh
======================================================================

[CP_001] ⚡ CARGA INICIADA - Estado: CARGANDO

======================================================================
  [CP_001] 📤 MENSAJE ENVIADO: ACK START_OK 10.0kWh
======================================================================
```

### Ejemplo: Fin de Carga
```
======================================================================
  [CP_001] 📩 MENSAJE RECIBIDO: CMD STOP
======================================================================

[CP_001] 🛑 CARGA DETENIDA - Estado: REPOSO

======================================================================
  [CP_001] 📤 MENSAJE ENVIADO: FIN
  Energía entregada: 8.5 kWh
  Importe: €4.08
  Duración: 170s
  Transacción: TX-CP_001-1730759243
======================================================================
```

---

## 🔧 Configuración Técnica

### Puertos Asignados
- **CP_001**: Engine en puerto **5001**
- **CP_002**: Engine en puerto **5002**
- **CP_003**: Engine en puerto **5003**
- **CP_004**: Engine en puerto **5004**
- **CP_005**: Engine en puerto **5005**

### Variables de Entorno
Cada CP se configura automáticamente con:
- `CP_ID`: Identificador único (CP_001, CP_002, ...)
- `ENGINE_PORT`: Puerto del Engine
- `KAFKA_SERVER`: Servidor Kafka para telemetría
- `CENTRAL_IP`: IP de la Central (PC_A)
- `CENTRAL_PORT`: Puerto de la Central (5000)

---

## 🛑 Cómo Detener

### Opción 1: Desde cada terminal
Presiona `Ctrl+C` en cada ventana de PowerShell (Engine y Monitor)

### Opción 2: Usando Docker
```batch
docker stop engine_CP_001 engine_CP_002 engine_CP_003 monitor_CP_001 monitor_CP_002 monitor_CP_003
```

### Opción 3: Detener todos los contenedores
```batch
docker stop $(docker ps -q)
```

---

## 📋 Flujo de Trabajo Típico

1. **Lanzar CPs**: Ejecutar `PC_B_RUN.bat` y seleccionar número de CPs
2. **Esperar registro**: Los CPs se registran automáticamente en la Central
3. **Simular conductor**: En la terminal del Engine:
   - Teclear `p` para enchufar un vehículo
   - La Central autoriza y envía comando START
   - La carga comienza automáticamente
4. **Monitorear**: Ver en tiempo real el estado y los mensajes
5. **Finalizar**: 
   - Teclear `d` para desenchufar, o
   - Esperar a que se complete el objetivo de kWh

---

## 🐛 Solución de Problemas

### Los CPs no se conectan a la Central
- Verifica que `central_ip.txt` contiene la IP correcta de PC_A
- Verifica que EV_Central esté ejecutándose en PC_A
- Verifica el firewall de Windows en ambos PCs

### Los Monitors no se conectan a los Engines
- Los Engines usan `host.docker.internal` para conectarse
- Asegúrate de que Docker Desktop esté actualizado

### Las terminales se cierran inmediatamente
- Revisa los logs de Docker: `docker logs engine_CP_001`
- Verifica que las imágenes se construyeron correctamente

---

## 📚 Archivos Relacionados

- `PC_B_RUN.bat`: Lanzador principal con menú de opciones
- `PC_B_RUN_MULTIPLE_CPS.bat`: Lanzador directo de múltiples CPs
- `launch_single_cp.ps1`: Script auxiliar de PowerShell
- `ev_cp_engine/EV_CP_E.py`: Engine mejorado con menú interactivo
- `ev_cp_monitor/EV_CP_M.py`: Monitor del CP

---

## ✨ Ventajas del Sistema

- ✅ Pruebas de escalabilidad (hasta 5 CPs simultáneos)
- ✅ Interfaz clara y visual por cada CP
- ✅ Simulación realista de acciones del conductor
- ✅ Visibilidad completa de las comunicaciones OCPP-like
- ✅ Fácil de usar y configurar

---

## 📞 Soporte

Si tienes problemas, revisa:
1. Este documento de instrucciones
2. Los logs en las terminales
3. Los logs de Docker
4. El archivo `DIAGNOSTICO_WEB_NO_MUESTRA_CPS.md` para problemas de conectividad

