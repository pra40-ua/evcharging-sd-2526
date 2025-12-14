# 🔧 SOLUCIÓN A LOS PROBLEMAS DETECTADOS

## 📋 Problemas encontrados en los logs de Central:

### ❌ Problema 1: Central no puede conectarse a Registry
```
[CENTRAL] ⚠️ Error verificando registro en EV_Registry: HTTPConnectionPool(host='127.0.0.1', port=6000)
Failed to establish a new connection: [WinError 10061]
```

**Causa:** Central estaba configurado con HTTP pero Registry usa HTTPS.

**✅ SOLUCIÓN APLICADA:**
- Modificado `RUN_CENTRAL.bat` para configurar `REGISTRY_URL=https://127.0.0.1:6000/api`
- Ahora Central usará HTTPS para conectarse con Registry

---

### ❌ Problema 2: Tablas faltantes en MySQL
```
Table 'evcharging.cp_encryption_keys' doesn't exist
Table 'evcharging.audit_log' doesn't exist
```

**Causa:** Las tablas no se crearon al iniciar los contenedores Docker.

**✅ SOLUCIÓN APLICADA:**
- Ejecutado script `REPARAR_BD_PC_B.bat` que creó las tablas remotamente en PC_A
- Tablas verificadas y funcionando ✓

**Tablas creadas:**
- ✅ `cp_encryption_keys` - Almacena claves de cifrado E2E por CP
- ✅ `audit_log` - Registro de auditoría de eventos
- ✅ `weather_alerts` - Alertas climatológicas
- ✅ `cp_registry` - Registro de CPs (del Registry)
- ✅ `cp_credentials` - Credenciales de autenticación (del Registry)

---

### ⚠️ Problema 3: CP no envía credenciales
```
[CENTRAL] ⚠️ No se proporcionaron credenciales en REG. Verificando solo registro...
```

**Causa:** El CP no está configurado para registrarse con Registry antes de conectar a Central.

**✅ SOLUCIÓN:**
1. El CP debe ejecutarse con la opción `--registry-url` apuntando a Registry
2. Registry debe estar corriendo ANTES de lanzar el CP
3. El flujo correcto es:
   - CP se registra con Registry → Obtiene credenciales
   - CP se conecta a Central → Envía credenciales
   - Central verifica credenciales con Registry → Acepta o rechaza

---

## 🚀 PASOS PARA CORREGIR Y PROBAR:

### En PC_A:
1. **Reiniciar EV_Central** para que use la nueva configuración:
   - Cerrar la ventana de Central actual
   - Volver a ejecutar desde `PC_A_RUN.bat` (reiniciará Central con REGISTRY_URL correcto)

### En PC_B:
2. **Registry ya está corriendo correctamente** ✅
   - URL: `https://localhost:6000`
   - Conectado a BD de PC_A: `192.168.1.43:3306`
   - Certificados SSL válidos ✓

3. **Lanzar un CP con configuración correcta:**
   - Debe tener `--registry-url https://localhost:6000` en su script de inicio
   - El CP se registrará automáticamente con Registry
   - Central verificará las credenciales consultando a Registry

---

## 📊 FLUJO ESPERADO DESPUÉS DE LAS CORRECCIONES:

### Cuando lances un CP ahora verás:

1. **En CP Monitor:**
   ```
   [CP_M] PASO 1: OBTENIENDO CREDENCIALES DE EV_Registry
   [CP_M] ✓ Credenciales obtenidas: cp_001_user / ********
   ```

2. **En Registry:**
   ```
   [EV_Registry] ✓ CP registrado: CP_001
   [EV_Registry]   Username: cp_001_user generado
   ```

3. **En CP Monitor:**
   ```
   [CP_M] PASO 2: ENVIANDO REG CON CREDENCIALES A CENTRAL
   [CP_M] ✓ Enviando credenciales...
   ```

4. **En Central (CORREGIDO):**
   ```
   [CENTRAL] ╔═══════════════════════════════════════════╗
   [CENTRAL] ║  🔐 VERIFICANDO CREDENCIALES CON REGISTRY  ║
   [CENTRAL] ╚═══════════════════════════════════════════╝
   [CENTRAL]    Consultando Registry en: https://127.0.0.1:6000/api/authenticate
   ```

5. **En Registry:**
   ```
   [EV_Registry] 🔐 Solicitud de autenticación recibida
   [EV_Registry] ✓ CREDENCIALES VÁLIDAS - CP_001
   ```

6. **En Central:**
   ```
   [CENTRAL] ✓ CREDENCIALES VERIFICADAS
   [CENTRAL] ✓ AUTH OK enviado a CP_001 (con clave de cifrado)
   ```

7. **En CP Monitor:**
   ```
   [CP_M] ✅ AUTENTICACIÓN EXITOSA
   [CP_M] 🔐 Clave de cifrado recibida
   [CP_M] Estado: ACTIVADO
   ```

---

## 🔍 VERIFICACIONES RÁPIDAS:

### Verificar Registry (PC_B):
```bash
python -c "import requests; import urllib3; urllib3.disable_warnings(); print(requests.get('https://localhost:6000/api/health', verify=False).json())"
```
**Esperado:** `{'status': 'ok', 'message': '...'}`

### Verificar tablas en MySQL (desde PC_B):
```bash
python -c "import mysql.connector; conn = mysql.connector.connect(host='192.168.1.43', port=3306, user='root', password='root', database='evcharging'); cursor = conn.cursor(); cursor.execute('SHOW TABLES'); [print(t[0]) for t in cursor.fetchall()]"
```
**Esperado:** Lista con 7 tablas incluyendo `cp_encryption_keys` y `audit_log`

### Verificar configuración de Central (PC_A):
Buscar en la salida al iniciar Central:
```
REGISTRY_URL=https://127.0.0.1:6000/api
```

---

## ✅ RESUMEN DE SOLUCIONES APLICADAS:

| Problema | Solución | Estado |
|----------|----------|--------|
| Central usa HTTP en vez de HTTPS | Configurado `REGISTRY_URL` en `RUN_CENTRAL.bat` | ✅ Corregido |
| Tablas `cp_encryption_keys` y `audit_log` faltantes | Ejecutado `REPARAR_BD_PC_B.bat` | ✅ Creadas |
| CPs sin credenciales | Documentado flujo correcto con Registry | ⚠️ Pendiente verificar script CP |

---

## 📝 NOTAS IMPORTANTES:

1. **Debes reiniciar Central en PC_A** para que use la nueva configuración HTTPS de Registry
2. Las tablas ya están creadas y disponibles
3. El siguiente paso es verificar que los scripts de los CPs incluyan `--registry-url`
4. Una vez reiniciado Central, el flujo completo Registry ↔ Central ↔ CP funcionará correctamente

---

## 🎯 SIGUIENTE ACCIÓN:

**En PC_A:**
```
1. Cerrar ventana de EV_Central
2. El script PC_A_RUN.bat lo reiniciará automáticamente con la configuración correcta
```

**Luego en PC_B:**
```
3. Lanzar un CP: INICIAR_CP01.bat
4. Observar las 3 ventanas (CP, Registry, Central) para ver el flujo completo
```

¡Ahora el sistema debería funcionar correctamente con el flujo Registry → Central! 🚀

