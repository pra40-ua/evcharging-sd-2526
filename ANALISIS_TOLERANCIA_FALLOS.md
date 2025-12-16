# Análisis: Tolerancia a Fallos por Componente

## Objetivo
Implementar el principio: **"Cualquier fallo en cualquier componente solo invalida el servicio proporcionado por ese componente. El resto de los componentes pueden seguir operando normalmente salvo en lo que se vea afectado por el componente caído."**

---

## Evaluación de Dificultad: **MEDIA-ALTA** ⚠️

### Resumen Ejecutivo
El sistema actual tiene **cierta resiliencia básica** pero está **arquitectónicamente acoplado** en varios puntos críticos. Implementar tolerancia completa a fallos requeriría **modificaciones significativas** en múltiples componentes, aunque **no es imposible**.

---

## Análisis de Dependencias Actuales

### 1. **Dashboard Web (web_dashboard.py) → Central API**

**Dependencia actual:**
```python
# Líneas 763-773: Consulta Central API para alertas climáticas
central_api_url = f"http://{CONFIG['central_ip']}:{CONFIG.get('central_api_port', 5001)}/api/status"
response = requests.get(central_api_url, timeout=2)
```

**Estado actual:**
- ✅ Ya maneja errores (try/except)
- ⚠️ Si Central cae, pierde alertas climáticas pero continúa mostrando datos de Kafka

**Dificultad para hacerlo independiente:** 🟢 **BAJA**
- **Cambios necesarios:**
  - Consumir alertas climáticas directamente desde Kafka (si EV_Weather publica allí)
  - O usar cache local de alertas con expiración
  - El Dashboard ya funciona principalmente con Kafka, solo depende de Central para alertas

---

### 2. **Monitor (EV_CP_M.py) → Central (socket TCP)**

**Dependencia actual:**
- Conexión socket directa a Central (línea 589)
- Si Central cae, el Monitor pierde la conexión y no puede enviar telemetría

**Estado actual:**
- ⚠️ No hay reconexión automática clara
- ❌ Si Central cae, el Monitor se queda sin conexión

**Dificultad para hacerlo resiliente:** 🟡 **MEDIA**
- **Cambios necesarios:**
  - Implementar bucle de reconexión con backoff exponencial
  - Buffer local de telemetría para enviar cuando se recupere la conexión
  - Continuar funcionando localmente aunque Central esté caído

---

### 3. **Engine (EV_CP_E.py) → Kafka**

**Dependencia actual:**
- Publica telemetría a Kafka
- Consume mensajes del Driver desde Kafka
- Si Kafka cae, no puede comunicarse

**Estado actual:**
- ⚠️ El Engine puede seguir suministrando energía localmente
- ❌ Pero no puede enviar telemetría ni recibir comandos

**Dificultad para hacerlo resiliente:** 🟠 **MEDIA-ALTA**
- **Cambios necesarios:**
  - Buffer local de telemetría pendiente
  - Reintentos automáticos para Kafka
  - Funcionamiento local independiente (el Engine puede seguir controlando el CP físicamente)
  - Usar estado local para decisiones críticas

---

### 4. **Central (EV_Central.py) → Kafka + Base de Datos**

**Dependencia actual:**
- Publica/consume de Kafka
- Consulta BD para información de CPs
- Si Kafka o BD caen, pierde funcionalidad

**Estado actual:**
- ⚠️ Mantiene estado en memoria (CONEXIONES_ACTIVAS, TELEMETRIA_ACTUAL)
- ❌ Pero depende de Kafka para comunicarse con Dashboard y otros componentes
- ❌ Depende de BD para persistencia y datos históricos

**Dificultad para hacerlo resiliente:** 🟠 **MEDIA-ALTA**
- **Cambios necesarios:**
  - Cache local más robusto
  - Funcionar sin BD para operación básica (usar solo estado en memoria)
  - Reintentos para Kafka con buffer de mensajes pendientes

---

### 5. **Driver (EV_Driver.py) → Kafka**

**Dependencia actual:**
- Envía solicitudes a Kafka
- Consume respuestas desde Kafka
- Si Kafka cae, no puede solicitar carga

**Estado actual:**
- ❌ Dependencia completa de Kafka

**Dificultad para hacerlo resiliente:** 🟡 **MEDIA**
- **Cambios necesarios:**
  - Reintentos con backoff
  - Mensaje de error claro al usuario si Kafka no está disponible
  - Retry automático hasta que Kafka esté disponible

---

### 6. **Kafka como Punto de Falla Único**

**Problema crítico:**
- Muchos componentes dependen de Kafka
- Si Kafka cae, múltiples componentes se ven afectados

**Dificultad para hacerlo resiliente:** 🔴 **ALTA**
- **Opciones:**
  1. **Kafka con alta disponibilidad** (clúster Kafka)
  2. **Alternativas de comunicación** (MQTT, Redis Pub/Sub, RabbitMQ)
  3. **Múltiples mecanismos de comunicación** (Kafka + HTTP fallback)

---

## Componentes ya Resilientes

### ✅ **Engine puede funcionar sin Monitor**
- El Engine tiene su propia lógica de control
- Si el Monitor cae, el Engine puede seguir suministrando
- Solo se pierde la telemetría a Central

### ✅ **Dashboard tiene manejo básico de errores**
- Ya maneja fallos de Central API
- Principalmente funciona con Kafka

---

## Plan de Implementación (Por Prioridad)

### FASE 1: Cambios Fáciles (1-2 semanas) 🟢

1. **Dashboard independiente de Central API**
   - Consumir alertas climáticas desde Kafka (si EV_Weather publica allí)
   - O implementar cache local con expiración
   - **Esfuerzo:** 1-2 días

2. **Driver con retry robusto**
   - Reintentos automáticos para Kafka
   - Mensajes de error claros
   - **Esfuerzo:** 1 día

---

### FASE 2: Cambios Medianos (2-4 semanas) 🟡

3. **Monitor con reconexión automática**
   - Bucle de reconexión con backoff exponencial
   - Buffer local de telemetría
   - Continuar funcionando aunque Central esté caído
   - **Esfuerzo:** 3-5 días

4. **Engine con buffer local**
   - Buffer de telemetría pendiente
   - Reintentos para Kafka
   - **Esfuerzo:** 2-3 días

5. **Central funcionando sin BD**
   - Usar solo estado en memoria para operación básica
   - BD solo para persistencia/persistencia histórica
   - **Esfuerzo:** 2-3 días

---

### FASE 3: Cambios Complejos (4-8 semanas) 🔴

6. **Kafka con alta disponibilidad o alternativa**
   - Opción A: Configurar clúster Kafka (requiere infraestructura)
   - Opción B: Implementar fallback a HTTP para comunicación crítica
   - Opción C: Usar sistema de mensajería más resiliente (Redis Pub/Sub, RabbitMQ)
   - **Esfuerzo:** 1-2 semanas

---

## Ejemplo de Cambio: Dashboard sin Central API

### Antes:
```python
# Depende de Central API
try:
    central_api_url = f"http://{CONFIG['central_ip']}:{CONFIG.get('central_api_port', 5001)}/api/status"
    response = requests.get(central_api_url, timeout=2)
    if response.status_code == 200:
        central_data = response.json()
        alertas_central = central_data.get('alertas_clima', {})
        WEATHER_ALERTS.update(alertas_central)
except Exception as e:
    # Si Central cae, no hay alertas
    pass
```

### Después:
```python
# Opción 1: Consumir desde Kafka directamente (si EV_Weather publica allí)
# Opción 2: Cache local con expiración
if not WEATHER_ALERTS or time.time() - LAST_WEATHER_UPDATE > 300:  # 5 minutos
    try:
        # Intentar obtener de Central API
        central_api_url = f"http://{CONFIG['central_ip']}:{CONFIG.get('central_api_port', 5001)}/api/status"
        response = requests.get(central_api_url, timeout=2)
        if response.status_code == 200:
            central_data = response.json()
            alertas_central = central_data.get('alertas_clima', {})
            WEATHER_ALERTS.update(alertas_central)
            LAST_WEATHER_UPDATE = time.time()
    except Exception as e:
        # Si Central cae, usar cache anterior
        print(f"[DASHBOARD] Central API no disponible, usando cache de alertas")
        pass  # Continuar con alertas en cache
```

---

## Conclusión

### Dificultad General: **MEDIA-ALTA** (6/10)

**Razones:**
- ✅ Muchos componentes ya tienen cierto manejo de errores
- ✅ Algunas dependencias son fáciles de eliminar
- ⚠️ Requiere cambios en múltiples componentes
- ⚠️ Kafka es un punto de falla único que requiere atención especial
- ⚠️ Requiere testing exhaustivo para validar el comportamiento

### Recomendación

1. **Comenzar con FASE 1** (cambios fáciles) para ganar experiencia
2. **Evaluar la necesidad real** de cada dependencia
3. **Priorizar según impacto**: ¿Qué componentes son críticos y cuáles pueden fallar sin afectar el servicio principal?
4. **Para Kafka**: Considerar alta disponibilidad o alternativas según presupuesto/infraestructura

### Ejemplo Práctico

**Escenario:** "Si el Front (Dashboard) o el API_Central no funciona, la operación del servicio puede continuar sin problemas."

**Estado actual:** ⚠️ Parcialmente cierto
- Dashboard puede funcionar solo con Kafka (casi independiente)
- Pero pierde algunas funcionalidades (alertas climáticas)
- Central es más crítico porque gestiona las conexiones de Monitores

**Después de FASE 1:** ✅ Cierto
- Dashboard completamente independiente
- Central sigue siendo necesario para Monitores, pero Engine puede funcionar localmente

---

## Métricas de Éxito

Para validar que se logró el objetivo:

1. ✅ Dashboard funciona sin Central API (solo muestra datos antiguos de alertas)
2. ✅ Monitor puede seguir funcionando localmente aunque Central esté caído
3. ✅ Engine puede seguir suministrando aunque Kafka esté caído (localmente)
4. ✅ Driver muestra mensaje claro si no puede conectar, pero no bloquea otros componentes
5. ✅ Un componente puede fallar sin afectar a otros

---

**Fecha de análisis:** 2024-12-15  
**Última actualización:** 2024-12-15

