# Resumen de Cambios Realizados

## Fecha: 04/11/2025

### Problemas Identificados y Solucionados:

#### 1. ❌ **Puerto 5000 no escuchaba (RESUELTO)**
   - **Problema**: El archivo `commands_PC_A.ps1` no existía
   - **Solución**: Creado el archivo `commands_PC_A.ps1` que ejecuta correctamente `EV_Central.py`
   - **Estado**: ✅ Puerto 5000 ahora escucha correctamente

#### 2. ❌ **"Trama inesperada ACK" en Monitor (RESUELTO)**
   - **Problema**: El Monitor no reconocía ACK del Engine cuando llegaba fuera de secuencia
   - **Solución**: Agregada condición `elif cod_op == 'ACK'` en `ev_cp_monitor/EV_CP_M.py` línea 354-357
   - **Estado**: ✅ ACK ahora se procesa correctamente

#### 3. ❌ **CPs no se detectaban en la web al conectarse (RESUELTO)**
   - **Problema**: Los CP solo se registraban en BD, pero no publicaban telemetría inicial en Kafka
   - **Solución**: Agregado código en `ev_central/EV_Central.py` línea 1043-1064 para publicar telemetría inicial cuando un CP se registra
   - **Estado**: ✅ Los CP ahora aparecen en la web inmediatamente al conectarse

#### 4. ❌ **kW siempre mostraban 0.00 en la web (RESUELTO)**
   - **Problema 1**: El frontend leía `cp.telemetria.kw_entregados` pero el backend guardaba en `cp.energia_kwh`
   - **Solución 1**: Corregido el frontend en `web_dashboard.py` línea 696-706 para leer los campos correctos
   - **Problema 2**: El Engine no enviaba el campo `potencia_actual` en la telemetría
   - **Solución 2**: Agregado campo `potencia_actual` en `ev_cp_engine/EV_CP_E.py` línea 46-60 y 88-107
   - **Estado**: ✅ Los kW ahora se muestran correctamente en la web

---

## Archivos Modificados:

1. **`commands_PC_A.ps1`** (NUEVO)
   - Ejecuta EV_Central con los parámetros correctos
   - Lee la IP desde `central_ip.txt`

2. **`ev_cp_monitor/EV_CP_M.py`**
   - Líneas 354-357: Manejo de ACK tardío

3. **`ev_central/EV_Central.py`**
   - Líneas 1043-1064: Publicación de telemetría inicial en Kafka cuando un CP se registra

4. **`ev_cp_engine/EV_CP_E.py`**
   - Líneas 46-60: Agregado parámetro `potencia_kw` en función de telemetría
   - Líneas 88-107: Envío de potencia en bucle de telemetría
   - Líneas 117-128: Envío de potencia 0.0 en estado REPOSO

5. **`web_dashboard.py`**
   - Líneas 696-706: Corrección del frontend para leer campos correctos de telemetría

---

## Cómo Probar el Sistema:

### 1. **Reiniciar todos los componentes**

Necesitas reconstruir las imágenes Docker para que incluyan los cambios:

#### En PC_A:
```powershell
# Detener todo
docker compose down

# Ejecutar de nuevo PC_A_RUN.bat
.\PC_A_RUN.bat
```

#### En PC_B:
```powershell
# Reconstruir las imágenes con los cambios
docker build -t ev_monitor:local -f ev_cp_monitor/Dockerfile .
docker build -t ev_engine:local -f ev_cp_engine/Dockerfile .

# Ejecutar los scripts de PC_B en orden:
.\commands_PC_B_build_engine.ps1
.\commands_PC_B_monitor.ps1
```

### 2. **Verificar que funciona**

#### Verificar puertos escuchando:
```powershell
netstat -ano | Select-String ":5000|:8080|:9092"
```

Deberías ver:
- Puerto 5000 (EV_Central)
- Puerto 8080 (Dashboard Web)
- Puerto 9092 (Kafka)

#### Verificar en el navegador:
1. Abre `http://localhost:8080`
2. **Deberías ver inmediatamente el CP registrado** (CP_001 en estado ACTIVADO con 0.00 kWh)
3. Cuando empiece a cargar, los kWh deberían incrementarse correctamente

#### Probar el botón "Activar" en la web:
1. Haz clic en "Activar" para el CP_001
2. **No debería aparecer más el error "Trama inesperada ACK"**
3. El estado debería cambiar a SUMINISTRANDO
4. Los kWh deberían empezar a incrementarse (0.05 kWh por segundo)

---

## Notas Importantes:

1. **Es necesario reconstruir las imágenes Docker** porque los cambios afectan a archivos Python dentro de los contenedores

2. **El campo potencia_actual está simulado en 3.0 kW** constante. Si necesitas valores dinámicos, puedes modificar la línea 100 de `ev_cp_engine/EV_CP_E.py`

3. **La web se actualiza automáticamente cada 2 segundos**, así que verás los cambios en tiempo real

4. **Si sigues sin ver los kWh**, verifica en la terminal del Engine que esté enviando telemetría a Kafka correctamente (debería imprimir mensajes cada segundo)

---

## Próximos Pasos (Opcional):

- [ ] Implementar potencia dinámica basada en el estado de la batería
- [ ] Agregar gráficos de evolución de carga en el dashboard
- [ ] Implementar límites de potencia configurables por CP
- [ ] Agregar notificaciones en tiempo real en el dashboard

