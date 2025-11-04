# Solución al Problema de Timeout de Conexión

## Problema
El Monitor en PC_B no puede conectarse al Central en PC_A, mostrando:
```
[CP_M] ERROR durante el registro: Timeout al conectar (10s).
Verifica que EV_Central esté ejecutándose en 192.168.1.43:5000
```

## Causa Principal
Los contenedores Docker en PC_B están usando la configuración de red por defecto (bridge), que no permite acceder directamente a IPs externas como la del Central en PC_A.

## Solución

### Opción 1: Usar el Script Completo (RECOMENDADO)

Ejecuta el nuevo script unificado que corrige automáticamente el problema:

```powershell
.\PC_B_RUN_COMPLETO.ps1
```

Este script:
- ✅ Verifica la conexión con PC_A
- ✅ Construye las imágenes Docker si no existen
- ✅ Lanza Engine y Monitor con `--network host` (solución al problema)
- ✅ Muestra diagnósticos útiles

### Opción 2: Diagnóstico Primero

Si quieres diagnosticar primero qué está fallando:

```powershell
.\diagnostico_PC_B.ps1
```

Este script verifica:
1. ✅ Conectividad de red (PING)
2. ✅ Puerto 5000 (EV_Central)
3. ✅ Puerto 9092 (Kafka)
4. ✅ Docker funcionando
5. ✅ Imágenes Docker construidas

### Opción 3: Scripts Individuales Corregidos

Si prefieres lanzar los componentes manualmente:

**Engine:**
```powershell
.\commands_PC_B_engine_fixed.ps1
```

**Monitor:**
```powershell
.\commands_PC_B_monitor_fixed.ps1
```

## ¿Por qué `--network host`?

El parámetro `--network host` hace que el contenedor Docker use **directamente la red del PC**, en lugar de crear una red virtual aislada. Esto permite:

- ✅ Conectarse a IPs externas (PC_A en 192.168.1.43)
- ✅ Acceder a servicios en localhost (Engine en 5001)
- ✅ Sin necesidad de mapear puertos con `-p`

**Antes (NO funcionaba):**
```powershell
docker run --rm --name monitor ...
# El contenedor está en red bridge aislada
# No puede llegar a 192.168.1.43:5000
```

**Ahora (SÍ funciona):**
```powershell
docker run --rm --network host --name monitor ...
# El contenedor usa la red del PC
# Puede llegar a 192.168.1.43:5000 directamente
```

## Verificación de Éxito

Cuando el problema esté resuelto, verás:

```
[CP_M] Intentando conectar a EV_Central en 192.168.1.43:5000...
[CP_M] Conexión con Central establecida. Enviando REG...
[CP_M] ¡CP_001 REGISTRO EXITOSO! Estado ACTIVADO. Mensaje: Autenticacion exitosa
[CP_M] Sistema ACTIVADO. Monitorización local de Engine iniciada.
```

## Checklist de Verificación en PC_A

Si aún tienes problemas, verifica en PC_A:

### 1. EV_Central está ejecutándose
- [ ] Hay una ventana abierta con "EV_Central INICIADO"
- [ ] El puerto 5000 está escuchando

### 2. Firewall abierto (CRÍTICO)
Abre PowerShell como **Administrador** y ejecuta:

```powershell
# Abrir puerto 5000 (EV_Central)
New-NetFirewallRule -DisplayName "EV_Central" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow

# Abrir puerto 9092 (Kafka)
New-NetFirewallRule -DisplayName "Kafka" -Direction Inbound -LocalPort 9092 -Protocol TCP -Action Allow

# Abrir puerto 3306 (MySQL) - opcional
New-NetFirewallRule -DisplayName "MySQL" -Direction Inbound -LocalPort 3306 -Protocol TCP -Action Allow
```

### 3. IP correcta en central_ip.txt
Verifica que `central_ip.txt` contenga la IP correcta de PC_A:

```powershell
Get-Content central_ip.txt
```

Debe mostrar algo como: `192.168.1.43` (la IP real de PC_A en tu red)

### 4. Servicios Docker activos en PC_A
```powershell
docker ps
```

Debe mostrar:
- kafka (puerto 9092)
- mysql (puerto 3306)

## Problemas Comunes y Soluciones

### Problema: "Connection refused"
**Causa:** EV_Central no está ejecutándose o el firewall bloquea el puerto 5000  
**Solución:** Verifica que EV_Central esté corriendo y abre el firewall (ver arriba)

### Problema: "Timeout al conectar"
**Causa:** Los contenedores no usan `--network host`  
**Solución:** Usa los scripts corregidos (`PC_B_RUN_COMPLETO.ps1` o `commands_PC_B_monitor_fixed.ps1`)

### Problema: "No se puede resolver el hostname"
**Causa:** La IP en `central_ip.txt` es incorrecta  
**Solución:** Verifica la IP real de PC_A con `ipconfig` y actualiza `central_ip.txt`

### Problema: Engine y Monitor no se ven entre sí
**Causa:** Ambos deben usar `--network host` o la misma red Docker  
**Solución:** Usa `PC_B_RUN_COMPLETO.ps1` que configura ambos correctamente

## Contacto y Soporte

Si sigues teniendo problemas después de seguir esta guía:

1. Ejecuta `.\diagnostico_PC_B.ps1` y copia el resultado
2. Verifica los logs de EV_Central en PC_A
3. Verifica los logs del Monitor en PC_B

## Comandos Útiles

```powershell
# Ver contenedores ejecutándose
docker ps

# Ver logs del Monitor
docker logs monitor

# Ver logs del Engine
docker logs engine

# Detener todo
docker stop engine monitor

# Verificar conectividad desde PC_B
Test-NetConnection -ComputerName 192.168.1.43 -Port 5000
```

## Resumen de Archivos Creados

- `diagnostico_PC_B.ps1` - Diagnóstico completo de conexión
- `PC_B_RUN_COMPLETO.ps1` - Script unificado que lo hace todo (RECOMENDADO)
- `commands_PC_B_engine_fixed.ps1` - Engine con network host
- `commands_PC_B_monitor_fixed.ps1` - Monitor con network host
- `SOLUCION_PROBLEMA_CONEXION.md` - Este documento

