# 🚗 Guía Rápida - Engine Interactivo

## ¡SOLUCIÓN AL PROBLEMA DE ENTRADA EN WINDOWS! ✅

El menú del Engine ahora funciona correctamente en Windows. Ya NO necesitas presionar Enter después de cada comando.

---

## 🎮 Cómo Usar el Menú Interactivo

### Inicio del Engine
Cuando inicies el Engine, verás:

```
[EV_CP_E] INICIADO
Puerto de escucha: 7001
CP ID: CP_001
Kafka: 172.21.42.5:9092
========================================
[EV_CP_E] Telemetría en reposo. A la espera de START para CP_001
[ENGINE] Detectado Windows - usando menú interactivo optimizado

============================================================
[ENGINE] MENÚ INTERACTIVO ACTIVO
============================================================
Comandos: 'p' Plug | 'f' Finish | 'x' Stop | 'h' Ayuda
============================================================

[EV_CP_E] Servidor escuchando en TCP (:7001). Esperando Monitor...
```

### ⚡ Comandos Rápidos (Sin Enter)

Simplemente presiona UNA tecla:

| Tecla | Comando | Descripción |
|-------|---------|-------------|
| **p** | Plug | Conectar vehículo (enchufar) |
| **f** | Finish | Finalizar carga y enviar ticket |
| **x** | Stop | Detener carga inmediatamente |
| **h** | Help | Mostrar ayuda |

**NO necesitas presionar Enter**. El comando se ejecuta inmediatamente.

---

## 📝 Ejemplos de Uso

### Ejemplo 1: Enchufar Vehículo

```
[ENGINE] Listo para siguiente comando...
p                                           ← Solo presiona 'p'
[ENGINE] >>> Enviando señal PLUGGED al Monitor...
[ENGINE] ✓ STATE enviado al Monitor: PLUGGED
[ENGINE] Listo para siguiente comando...
```

### Ejemplo 2: Finalizar Carga (FINISH)

```
[ENGINE] Listo para siguiente comando...
f                                           ← Solo presiona 'f'
[ENGINE] >>> FINISH solicitado: finalizando carga de forma ordenada...
[ENGINE] ✓ FIN enviado a Monitor. kWh=2.50, €=1.20, duración=50s
[ENGINE] Listo para siguiente comando...
```

### Ejemplo 3: Detener Inmediatamente

```
[ENGINE] Listo para siguiente comando...
x                                           ← Solo presiona 'x'
[ENGINE] >>> Deteniendo carga y desenchufando...
[ENGINE] ✓ Señal UNPLUGGED enviada.
[ENGINE] Listo para siguiente comando...
```

### Ejemplo 4: Ver Ayuda

```
[ENGINE] Listo para siguiente comando...
h                                           ← Solo presiona 'h'

[ENGINE] === COMANDOS DISPONIBLES ===
  p = Enchufar (Plug) - Avisar al Monitor que el vehículo está conectado
  f = FINISH - Finalizar carga normalmente y enviar ticket al Driver
  x = Stop - Detener carga inmediatamente (desenchufar)
  h = Ayuda - Mostrar este mensaje
=====================================

[ENGINE] Listo para siguiente comando...
```

---

## 🔄 Flujo de Trabajo Típico

### Escenario 1: Carga Normal Completa

1. **Iniciar Engine y Monitor** (en terminales separados)
2. **Driver solicita carga** desde su terminal
3. **Central autoriza** y notifica al CP
4. **En Engine, presiona `p`** para conectar el vehículo
   - El Monitor detecta PLUGGED y envía START al Engine
   - Comienza la carga automáticamente
5. **Espera** a que la telemetría alcance el objetivo
   - Se envía FIN automáticamente
   - Driver recibe el ticket
6. **CP vuelve a ACTIVADO** listo para nueva carga

### Escenario 2: Finalizar Carga Manualmente

1. Durante una carga activa...
2. **En Engine, presiona `f`**
   - Se detiene el suministro
   - Se calcula el consumo final
   - Se envía FIN al Monitor
   - Monitor reenvía a Central
   - Driver recibe ticket
3. **CP vuelve a ACTIVADO**

### Escenario 3: Detener por Emergencia

1. Durante una carga activa...
2. **En Engine, presiona `x`**
   - Se detiene inmediatamente
   - Se notifica UNPLUGGED
   - NO se genera ticket (es un stop de emergencia)

---

## ⚠️ Solución de Problemas

### "No puedo escribir en el terminal del Engine"

**Solución**: Ya está resuelto. El nuevo código usa `msvcrt` en Windows para lectura no bloqueante.

- ✅ Asegúrate de tener la última versión del código
- ✅ Verifica que al iniciar veas: `[ENGINE] Detectado Windows - usando menú interactivo optimizado`
- ✅ Simplemente presiona las teclas directamente (p, f, x, h)

### "Presiono una tecla pero no pasa nada"

1. Verifica que el Engine esté conectado al Monitor
2. Comprueba que el menú esté activo (debe aparecer el banner al inicio)
3. Si usas Docker, verifica que el contenedor tenga acceso a TTY

### "El comando se ejecuta pero no veo respuesta"

Los mensajes aparecen mezclados con otros logs. Busca líneas que empiecen con:
- `[ENGINE] >>>` - Indica que se está ejecutando un comando
- `[ENGINE] ✓` - Indica éxito
- `[ENGINE] ✗` - Indica error

---

## 📊 Símbolos de Estado

| Símbolo | Significado |
|---------|-------------|
| ✓ | Comando ejecutado correctamente |
| ✗ | Error al ejecutar comando |
| >>> | Comando en proceso |

---

## 🔧 Comandos por Contexto

### Antes de Iniciar Carga
- `h` - Ver ayuda

### Durante Autorización (esperando vehículo)
- `p` - Conectar vehículo y empezar carga

### Durante Carga Activa
- `f` - Finalizar normalmente (genera ticket)
- `x` - Detener inmediatamente (emergencia)

### Después de Carga
- `p` - Conectar nuevo vehículo para próxima carga

---

## 💡 Tips

1. **Teclas rápidas**: No presiones Enter, solo la tecla
2. **Visual**: Busca los símbolos ✓ y ✗ para confirmar ejecución
3. **Comando FINISH**: Usa `f` para finalizar ordenadamente (mejor que `x`)
4. **Estado del CP**: Tras FINISH o STOP, el CP vuelve a ACTIVADO automáticamente

---

## 🆘 Ayuda Rápida en Terminal

En cualquier momento, presiona `h` para ver la ayuda:

```
h
[ENGINE] === COMANDOS DISPONIBLES ===
  p = Enchufar (Plug) - Avisar al Monitor que el vehículo está conectado
  f = FINISH - Finalizar carga normalmente y enviar ticket al Driver
  x = Stop - Detener carga inmediatamente (desenchufar)
  h = Ayuda - Mostrar este mensaje
=====================================
```

---

## 📞 Contacto

Si tienes problemas, verifica:
1. Versión actualizada del código (con cambios de 31/10/2025)
2. Windows detectado correctamente al iniciar
3. Monitor conectado al Engine
4. Logs del sistema para mensajes de error

---

**Última actualización**: 31 de Octubre, 2025
**Sistema**: EV Charging - Distributed System (SD-2526)

