# Verificación de Configuración SSL

## ✅ Estado Actual

### Certificados SSL
- ✅ **Generados**: `certificados/registry_cert.pem` y `certificados/registry_key.pem`
- ✅ **Ubicación**: En el directorio raíz del proyecto

### PC_A_RUN.bat
- ✅ **Estado**: No requiere cambios (no usa SSL directamente)
- ✅ **Funcionalidad**: Inicia Kafka, MySQL, EV_Central y Dashboard Web

### PC_B_RUN.bat
- ✅ **Estado**: Configurado para iniciar EV_Weather, Monitores y Engines
- ✅ **EV_CP_M.py**: Actualizado para soportar HTTPS con certificados autofirmados
  - Intenta HTTPS primero
  - Si falla, intenta HTTP automáticamente
  - Deshabilita advertencias SSL para certificados autofirmados

### PC_C_RUN.bat
- ✅ **Estado**: Configurado para detectar certificados SSL automáticamente
- ✅ **Funcionalidad**: 
  - Detecta si existen `certificados/registry_cert.pem` y `certificados/registry_key.pem`
  - Si existen, usa HTTPS
  - Si no existen, usa HTTP
  - Muestra mensaje informativo sobre el protocolo usado

## 🔧 Configuración Automática

### EV_Registry (PC_C)
El script `PC_C_RUN.bat` detecta automáticamente si hay certificados:
- **Con certificados**: Usa HTTPS en puerto 6000
- **Sin certificados**: Usa HTTP en puerto 6000

### EV_CP_M (PC_B)
El módulo `EV_CP_M.py` intenta automáticamente:
1. **HTTPS primero** (si la URL no especifica protocolo)
2. **HTTP como fallback** (si HTTPS falla)

## 📋 Verificación de Funcionamiento

### Para verificar que todo funciona:

1. **Ejecutar PC_C_RUN.bat**:
   - Debería mostrar: `[INFO] Certificados SSL encontrados. Usando HTTPS.`
   - O: `[OK] EV_Registry iniciado con HTTP`

2. **Ejecutar PC_B_RUN.bat**:
   - Los Monitores intentarán conectarse a EV_Registry
   - Si hay certificados, usarán HTTPS
   - Si no hay certificados o HTTPS falla, usarán HTTP automáticamente

3. **Verificar en los logs**:
   - Buscar mensajes como: `[CP_M] ✓ Registrado en EV_Registry`
   - O: `[CP_M] ⚠️ HTTPS falló, intentando HTTP...`

## ⚠️ Notas Importantes

1. **Certificados Autofirmados**:
   - Los navegadores mostrarán advertencias (normal en desarrollo)
   - Python deshabilitará advertencias SSL automáticamente

2. **Red Local**:
   - Si PC_B y PC_C están en máquinas diferentes:
     - Asegúrate de que la IP de PC_C sea accesible desde PC_B
     - El protocolo (HTTP/HTTPS) se detecta automáticamente

3. **Producción**:
   - Para producción, usa certificados de una CA reconocida
   - Actualiza `EV_CP_M.py` para usar `verify=True` en producción

## 🚀 Próximos Pasos

1. Ejecutar `PC_A_RUN.bat` en PC_A
2. Ejecutar `PC_B_RUN.bat` en PC_B
3. Ejecutar `PC_C_RUN.bat` en PC_C
4. Verificar que los CPs se registren correctamente en EV_Registry

