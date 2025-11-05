# Actualización del Dashboard Web - Múltiples CPs

## 📅 Fecha
4 de Noviembre de 2025

## 🎯 Problema Resuelto
Los 5 CPs se ejecutan y aparecen en la terminal de Central, pero NO se mostraban en la interfaz web del dashboard.

---

## 🔍 Causa del Problema

El Dashboard web solo mostraba CPs cuando recibía telemetría de Kafka. Sin embargo:

1. **Los CPs solo envían telemetría cuando hay una sesión de carga activa**
2. **Si el Dashboard se inicia después de que los CPs ya se registraron**, no los ve hasta que haya telemetría nueva
3. **Los CPs en estado "Available" o "Activado" NO envían telemetría** hasta que inicie una carga

---

## ✅ Solución Implementada

### 1. **Sincronización Automática con Base de Datos** 

Ahora el Dashboard:
- **Carga el estado inicial** de todos los CPs registrados desde la base de datos al iniciar
- **Sincroniza automáticamente cada 10 segundos** consultando la BD para detectar nuevos CPs
- **No depende solo de Kafka** para descubrir CPs

### 2. **Endpoint de Recarga Manual**

Nuevo endpoint REST: `POST /api/reload_from_db`
- Permite forzar una recarga de CPs desde la BD
- Útil para debug y sincronización inmediata

### 3. **Botón de Recarga en la Interfaz Web**

Añadido botón **"🔄 Recargar desde BD"** en el header del dashboard que:
- Fuerza una sincronización inmediata con la BD
- Muestra notificación de éxito/error
- Actualiza la tabla de CPs automáticamente

---

## 📝 Cambios Realizados

### Archivo: `web_dashboard.py`

#### 1. Función `cargar_estado_inicial_bd()` mejorada
```python
def cargar_estado_inicial_bd():
    """Carga el estado inicial de CPs desde la base de datos."""
    # Ahora retorna el número de CPs cargados
    # Solo añade CPs nuevos (no sobrescribe los que ya tienen telemetría)
    # Logs mejorados para debug
```

#### 2. Nueva función `sincronizar_cps_desde_bd()`
```python
def sincronizar_cps_desde_bd():
    """Sincroniza periódicamente el estado de CPs desde la base de datos."""
    while True:
        time.sleep(10)  # Sincronizar cada 10 segundos
        num_cps = cargar_estado_inicial_bd()
        # Log cada sincronización
```

#### 3. Nuevo endpoint `/api/reload_from_db`
```python
@app.route('/api/reload_from_db', methods=['POST'])
def api_reload_from_db():
    """Fuerza una recarga de CPs desde la base de datos."""
    # Recarga inmediata y retorna resultado
```

#### 4. Hilo de sincronización automática
```python
# En main(), si hay configuración de BD:
bd_sync_thread = threading.Thread(
    target=sincronizar_cps_desde_bd,
    daemon=True
)
bd_sync_thread.start()
```

### Archivo: `templates/dashboard.html`

#### 1. Botón de recarga en el header
```html
<button class="btn-reload" onclick="recargarDesdeDB()" ...>
    🔄 Recargar desde BD
</button>
```

#### 2. Función JavaScript `recargarDesdeDB()`
```javascript
function recargarDesdeDB() {
    fetch('/api/reload_from_db', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            mostrarNotificacion(`✓ ${data.message}`, 'success');
            actualizarDashboard();
        });
}
```

---

## 🚀 Cómo Usar

### Opción 1: Sincronización Automática (Por Defecto)

1. Asegúrate de que el Dashboard se inicia con configuración de BD:
   ```bash
   python web_dashboard.py --kafka 192.168.1.43:9092 --db "192.168.1.43:3306:root:admin:evcharging_db"
   ```

2. El Dashboard automáticamente:
   - Carga CPs al iniciar
   - Sincroniza cada 10 segundos
   - Muestra todos los CPs registrados

### Opción 2: Recarga Manual

1. Abre el dashboard en tu navegador: `http://localhost:8080`

2. Haz clic en el botón **"🔄 Recargar desde BD"** en el header

3. Verás una notificación: **"✓ X CPs cargados desde BD"**

4. La tabla se actualiza automáticamente mostrando los CPs

---

## 🔧 Configuración Requerida

Para que funcione la sincronización con BD, **DEBES** iniciar el Dashboard con el parámetro `--db`:

```bash
python web_dashboard.py \
    --kafka 192.168.1.43:9092 \
    --db "192.168.1.43:3306:root:admin:evcharging_db"
```

El formato de `--db` es:
```
--db "HOST:PUERTO:USUARIO:PASSWORD:DATABASE"
```

---

## 📊 Flujo del Sistema Actualizado

### Antes (Solo Kafka)
```
1. CP se registra en Central
2. Central guarda en BD
3. CP espera sesión de carga
4. Dashboard espera telemetría de Kafka
   ❌ SIN TELEMETRÍA = NO SE VE EN WEB
```

### Ahora (Kafka + BD)
```
1. CP se registra en Central
2. Central guarda en BD
3. Dashboard sincroniza con BD cada 10s
   ✅ CP VISIBLE EN WEB INMEDIATAMENTE
4. Cuando hay carga, telemetría actualiza estado en tiempo real
```

---

## 🎨 Mejoras Visuales

### Log Mejorado del Dashboard

```
[DASHBOARD] Cargando estado inicial desde la base de datos...
[DASHBOARD] ✓ CP cargado desde BD: CP_001 - ACTIVADO
[DASHBOARD] ✓ CP cargado desde BD: CP_002 - ACTIVADO
[DASHBOARD] ✓ CP cargado desde BD: CP_003 - ACTIVADO
[DASHBOARD] ✓ 3 CP(s) nuevos cargados desde BD (Total: 3)
[DASHBOARD] ✓ Sincronización automática con BD activada
[DASHBOARD] 🔄 Sincronización BD: 3 CPs en estado
```

### Notificaciones en la Web

- **✓** Notificación verde al recargar exitosamente
- **⚠** Notificación amarilla si no hay CPs
- **✗** Notificación roja en caso de error

---

## 🧪 Pruebas Realizadas

### Test 1: Dashboard se inicia DESPUÉS de los CPs
✅ **RESULTADO**: Todos los CPs visibles al cargar la página

### Test 2: Se lanzan 5 CPs simultáneos
✅ **RESULTADO**: Los 5 CPs aparecen en la web en ~10 segundos máximo

### Test 3: Recarga manual desde botón
✅ **RESULTADO**: Sincronización inmediata, notificación de éxito

### Test 4: Sin configuración de BD
✅ **RESULTADO**: Dashboard funciona (solo con Kafka), muestra advertencia

---

## 🐛 Troubleshooting

### Los CPs aún no aparecen en la web

1. **Verifica que el Dashboard tiene configuración de BD:**
   ```
   [DASHBOARD] ✓ Sincronización automática con BD activada
   ```
   Si no ves esto, el Dashboard NO tiene configuración de BD.

2. **Revisa que los CPs están en la BD:**
   ```bash
   python verificar_bd.ps1
   ```
   
3. **Fuerza una recarga manual:**
   - Haz clic en el botón "🔄 Recargar desde BD"
   - O accede a: `http://localhost:8080/api/debug`

4. **Verifica los logs del Dashboard:**
   ```
   [DASHBOARD] ✓ CP cargado desde BD: CP_001 - ACTIVADO
   ```

### El botón de recarga no funciona

1. Abre la consola del navegador (F12)
2. Busca errores JavaScript
3. Verifica que el endpoint responde:
   ```bash
   curl -X POST http://localhost:8080/api/reload_from_db
   ```

---

## 📚 Archivos Relacionados

- `web_dashboard.py` - Backend del dashboard (actualizado)
- `templates/dashboard.html` - Frontend del dashboard (actualizado)
- `DIAGNOSTICO_WEB_NO_MUESTRA_CPS.md` - Guía de diagnóstico original

---

## ✨ Beneficios de la Actualización

1. ✅ **Visibilidad inmediata** de todos los CPs registrados
2. ✅ **No depende solo de Kafka** para descubrir CPs
3. ✅ **Sincronización automática** cada 10 segundos
4. ✅ **Recarga manual** para debug y testing
5. ✅ **Compatible** con el flujo anterior (telemetría por Kafka)
6. ✅ **Logs mejorados** para diagnóstico

---

## 🎉 Resultado Final

**AHORA**: Los 5 CPs se ejecutan, aparecen en la terminal de Central **Y** en la interfaz web del dashboard, incluso cuando no tienen sesiones de carga activas.

---

## 📞 Soporte

Si los CPs aún no aparecen:
1. Ejecuta `http://localhost:8080/api/debug` y comparte el resultado
2. Verifica los logs del Dashboard
3. Confirma que el Dashboard se inició con `--db`
4. Haz clic en "🔄 Recargar desde BD"

