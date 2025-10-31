# Cambios Implementados: Estados CP y Comando FINISH

## Fecha: 31 de Octubre, 2025

### Resumen de Cambios

Se han implementado mejoras en el sistema de gestión de estados del Charging Point (CP) y se ha añadido el comando FINISH para finalizar cargas de forma ordenada.

---

## 1. Estado ACTIVADO tras STOP

### Problema Original
Cuando se ejecutaba un comando STOP (manual o programático), el CP pasaba al estado "PARADO", lo cual no era el comportamiento deseado.

### Solución Implementada
El CP ahora permanece en estado **ACTIVADO** mientras esté conectado y no esté suministrando energía. Esto incluye:
- Tras ejecutar un STOP manual desde Central
- Tras completar una sesión de carga
- Tras recibir un comando FINISH

### Archivos Modificados

#### `ev_central\EV_Central.py`
- **Línea 173-177**: Modificada la función `_enviar_comando_cp()` para establecer el estado a ACTIVADO tras STOP (en lugar de PARADO)
- El estado manual se actualiza a 'ACTIVADO' en lugar de 'PARADO'

```python
if orden.upper() == 'STOP':
    # CAMBIO: Tras STOP, volver a ACTIVADO (no PARADO)
    with CP_ESTADO_MANUAL_LOCK:
        CP_ESTADO_MANUAL[cp_id] = 'ACTIVADO'
    try:
        cambiar_estado_cp(cp_id, 'ACTIVADO')
```

#### `ev_cp_monitor\EV_CP_M.py`
- **Línea 216**: Modificada la lógica de notificación de estado tras recibir STOP/START desde Central
- Ahora siempre envía estado 'ACTIVADO' a Central tras cualquiera de estos comandos

```python
# CAMBIO: Tras STOP, el CP vuelve a ACTIVADO (no PARADO)
nuevo_estado = 'ACTIVADO'  # Siempre ACTIVADO tras START o STOP
```

---

## 2. Comando FINISH en Engine

### Funcionalidad Nueva
Se ha añadido el comando **'f' (FINISH)** al menú interactivo del Engine para permitir finalizar una sesión de carga de forma ordenada.

### Comportamiento
Cuando el operador escribe 'f' en el terminal del Engine:
1. Se detiene el suministro de energía
2. Se calcula el consumo final (kWh, importe, duración)
3. Se envía una trama FIN al Monitor con todos los detalles
4. El Monitor reenvía el FIN a Central
5. Central envía el ticket final al Driver
6. El CP vuelve automáticamente a estado ACTIVADO

### Archivos Modificados

#### `ev_cp_engine\EV_CP_E.py`
- **Línea 305**: Actualizado el mensaje del menú para incluir 'f'
- **Líneas 323-354**: Implementado el handler del comando FINISH
  - Detiene el hilo de telemetría
  - Obtiene valores finales (kWh, segundos)
  - Construye y envía trama FIN al Monitor con:
    - CP_ID
    - Driver_ID
    - Energía entregada (kWh)
    - Importe (€)
    - Duración (segundos)
    - Motivo: "Finalizado por operador (FINISH)"
    - Transaction ID

```python
if cmd == 'f':
    # FINISH: Detener suministro de forma ordenada y enviar FIN
    print("[ENGINE] === FINISH solicitado: finalizando carga de forma ordenada ===")
    # ... lógica de finalización ...
    trama_fin = construir_trama('FIN', [cp_id, driver_id, f"{kw_final:.2f}", 
                                         f"{importe:.2f}", str(secs_final), 
                                         motivo, tx_id])
    conn.sendall(trama_fin)
```

---

## 3. Mejoras en Mensajes de Telemetría

### Problema Original
Los mensajes de telemetría no mostraban claramente el objetivo de kW solicitado por el Driver.

### Solución Implementada
Los mensajes de telemetría ahora muestran de forma clara el objetivo solicitado.

### Archivos Modificados

#### `ev_central\EV_Central.py`
- **Línea 360**: Mejorado el formato del mensaje para mostrar "Objetivo: X.XX kWh"
- El objetivo se muestra en todos los mensajes de telemetría cuando hay una sesión activa

**Ejemplo de salida:**
```
[19:07:15] [ESTADO] CP_001 -> SUMINISTRANDO.
[19:07:16] Telemetría recibida de CP_001: est=CARGANDO, E=0.70, P=N/D | Objetivo: 5.00 kWh
[KAFKA CONSUMER] -> Telemetría de CP_001 recibida: {'cp_id': 'CP_001', ...}
```

---

## 4. Flujo Completo de Finalización

### Secuencia Actualizada

1. **Operador escribe 'f' en terminal del Engine**
   - Engine: Detiene telemetría y calcula valores finales
   - Engine → Monitor: Envía trama FIN

2. **Monitor recibe FIN**
   - Monitor → Central: Reenvía trama FIN

3. **Central procesa FIN** (código ya existente, líneas 1060-1099)
   - Registra evento de fin de carga
   - Central → Driver: Envía notificación 'TICKET_FINAL' vía Kafka
   - Actualiza estado del CP a ACTIVADO
   - Limpia información de sesión (objetivo kWh, driver ID)

4. **Driver recibe ticket**
   - Muestra información de la carga finalizada
   - Guarda ticket en archivo local

5. **CP queda listo para nueva sesión**
   - Estado: ACTIVADO
   - Esperando nueva solicitud de Driver

---

## Estados del CP - Resumen

| Estado | Descripción | Cuándo se Activa |
|--------|-------------|------------------|
| **DESCONECTADO** | CP no está conectado a Central | Sin conexión socket |
| **ACTIVADO** | CP conectado, listo para recibir solicitudes | Tras registro, tras STOP, tras FIN |
| **PRE-SUMINISTRO** | Autorización concedida, esperando inicio físico | Tras AUTH_REQ/AUTH_RESP OK |
| **SUMINISTRANDO** | Carga activa | Telemetría indica CARGANDO |
| **PARADO** | ~~Ya no se usa tras STOP~~ | Solo para averías graves |
| **AVERÍA** | Fallo detectado por HCK o telemetría | Timeout HCK, estado KO |

---

## Comandos Disponibles

### Engine (Terminal Interactivo)
- **'p'** - Enchufar (Plug): Notifica al Monitor que el vehículo está conectado
- **'f'** - Finalizar (Finish): **NUEVO** - Finaliza la carga y envía ticket
- **'x'** - Detener (Stop): Detiene inmediatamente y desenchufa
- **'h'** - Ayuda: Muestra información de comandos

### Central (Terminal)
- **'1'** - Refrescar estado de red
- **'2 START CP_ID'** - Activar un CP manualmente
- **'2 STOP CP_ID'** - Detener un CP manualmente (CP volverá a ACTIVADO)
- **'3'** - Salir

---

## Compatibilidad

Todos los cambios son **retrocompatibles** con el flujo existente:
- El flujo de auto-stop por objetivo alcanzado sigue funcionando
- Los comandos manuales START/STOP desde Central siguen funcionando
- La finalización automática por consumo completo sigue funcionando
- Se añade una nueva forma manual de finalizar desde el Engine

---

## Testing Recomendado

1. **Probar STOP manual desde Central**
   - Verificar que el CP vuelve a ACTIVADO
   - Confirmar que puede recibir nueva solicitud

2. **Probar comando FINISH desde Engine**
   - Durante una carga activa, escribir 'f'
   - Verificar que se envía FIN
   - Confirmar que Driver recibe ticket
   - Verificar que CP vuelve a ACTIVADO

3. **Verificar mensajes de telemetría**
   - Confirmar que se muestra "Objetivo: X.XX kWh"
   - Verificar que aparece en todos los mensajes durante carga

4. **Probar reconexión tras STOP**
   - Ejecutar STOP
   - Enviar nueva solicitud desde Driver
   - Verificar que se acepta correctamente

---

## Notas Técnicas

- Los cambios NO afectan a la base de datos
- Los mapeos de estados BD permanecen igual
- No se requieren cambios en Docker Compose
- Compatible con la versión actual de Kafka
- No se requieren migraciones

---

## Autores
- Modificaciones realizadas el 31/10/2025
- Sistema: EV Charging - Distributed System (SD-2526)

