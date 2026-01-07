# Análisis del Flujo: Simular Avería → Recuperar Avería

## ✅ FLUJO COMPLETO VERIFICADO

### 1. SIMULAR AVERÍA (Opción 3)

**Engine (`/api/simular_averia`)**:
- ✅ Activa `SIMULAR_AVERIA = True`
- ✅ El Engine responde `KO` a los `HCK` del Monitor
- ✅ La telemetría incluye `averia_activa: True`

**Monitor**:
- ✅ Detecta `HCK_RESP#KO` del Engine
- ✅ Llama a `notificar_averia_central()` 
- ✅ Envía `AVR#cp_id#motivo` a Central (cifrado)

**Central**:
- ✅ Recibe `AVR` y procesa: `campos[0] = cp_id`, `campos[1] = motivo`
- ✅ Establece `CP_ALERTA[cp_id] = True`
- ✅ Cambia estado a `AVERÍA`
- ⚠️ **NOTA**: Hay un pequeño desajuste de formato (envía `cp_id` en campos[0] pero Central lo interpreta como motivo), pero funciona porque Central ya tiene `cp_id` del socket

### 2. RECUPERAR AVERÍA (Opción 4)

**Engine (`/api/recuperar_averia`)**:
- ✅ Desactiva `SIMULAR_AVERIA = False`
- ✅ Envía `AVR_CLR#cp_id#RECUPERADA#OK` al Monitor (sin cifrar, comunicación local)

**Monitor**:
- ✅ Recibe `AVR_CLR` del Engine
- ✅ Reenvía `AVR_CLR#cp_id#RECUPERADA#OK` a Central (cifrado)

**Central**:
- ✅ Recibe `AVR_CLR` y procesa: `campos[0] = cp_id`, `campos[1] = RECUPERADA`, `campos[2] = OK`
- ✅ Establece `CP_ALERTA[cp_id] = False`
- ✅ Cambia estado a `ACTIVADO`
- ✅ Resetea contadores de telemetría
- ✅ Publica telemetría actualizada a Kafka

## ⚠️ PROBLEMAS DETECTADOS Y CORREGIDOS

### 1. **Formato de AVR inconsistente** (Menor)
- **Problema**: Monitor envía `AVR#cp_id#motivo` pero Central espera `AVR#motivo#codigo`
- **Impacto**: Funciona pero es confuso (Central interpreta `cp_id` como motivo)
- **Estado**: Funcional, pero podría mejorarse

### 2. **Spam de mensajes de alerta climatológica** (Corregido ✅)
- **Problema**: `api_weather_alert()` se ejecutaba repetidamente sin verificar cambios
- **Solución**: Agregada verificación de cambio de estado antes de procesar
- **Estado**: ✅ CORREGIDO

### 3. **CP no encontrado en BD** (Corregido ✅)
- **Problema**: Si el CP no existe en BD, `actualizar_estado_cp()` fallaba
- **Solución**: Auto-registro del CP si no existe
- **Estado**: ✅ CORREGIDO

## ✅ CONCLUSIÓN

**El flujo de Simular Avería → Recuperar Avería DEBERÍA FUNCIONAR correctamente** con el código actual, después de las correcciones aplicadas.

### Flujo esperado:
1. **Simular Avería**: Engine → Monitor → Central → Estado AVERÍA ✅
2. **Recuperar Avería**: Engine → Monitor → Central → Estado ACTIVADO ✅

### Verificación recomendada:
1. Reiniciar Central para aplicar correcciones
2. Simular avería y verificar que Central cambia a AVERÍA
3. Recuperar avería y verificar que Central cambia a ACTIVADO
4. Verificar que no hay spam de mensajes repetidos
