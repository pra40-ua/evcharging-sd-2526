# Configuración Sin Autenticación - Modo Desarrollo

## Resumen

El proyecto ha sido configurado para funcionar **sin restricciones de autenticación** en la base de datos. Todos los componentes usan `root:root` para acceder a MariaDB.

## Cambios Realizados

### 1. Scripts de Ejecución

#### `RUN_CENTRAL.bat`
- **Antes**: `ev_user:ev_user_pass`
- **Ahora**: `root:root`
- **Conexión**: `127.0.0.1:3306:root:root:evcharging`

#### `PC_A_RUN.bat`
- **Dashboard Web**: Usa `root:root`
- **Configuración MariaDB**: Solo configura root sin restricciones
- **Mensajes informativos**: Actualizados para reflejar modo sin autenticación

#### `INICIAR_REGISTRY.bat`
- **Antes**: `evcharging_app:evcharging_app_pass`
- **Ahora**: `root:root`

### 2. Scripts SQL

#### `db/setup_sin_autenticacion.sql` (NUEVO)
- Configura `root` para acceso desde cualquier host
- Otorga **TODOS los privilegios** sin restricciones
- Usa `mysql_native_password` para compatibilidad con Python
- Se ejecuta automáticamente al iniciar el contenedor

#### `docker-compose.yml`
- Simplificado para usar solo `setup_sin_autenticacion.sql`
- Eliminados scripts de creación de usuarios específicos

### 3. Componentes del Sistema

Todos los componentes ahora usan `root:root`:

- **EV_Central**: `root:root`
- **EV_Registry**: `root:root` (ya estaba configurado)
- **web_dashboard**: `root:root`

## Configuración de Base de Datos

### Credenciales
- **Usuario**: `root`
- **Contraseña**: `root`
- **Base de datos**: `evcharging`
- **Host**: `127.0.0.1` o `localhost`
- **Puerto**: `3306`

### Formato de Conexión
```
127.0.0.1:3306:root:root:evcharging
```

### Permisos
- **ALL PRIVILEGES** en todas las bases de datos
- Acceso desde cualquier host (`%`)
- Acceso desde `localhost`
- Acceso desde `127.0.0.1`

## Uso

### Iniciar el Sistema

1. **PC_A (Servidor Central)**:
   ```batch
   PC_A_RUN.bat
   ```
   - Inicia Kafka + MariaDB
   - Inicia EV_Central (usa `root:root`)
   - Inicia Dashboard Web (usa `root:root`)

2. **EV_Registry** (si se ejecuta por separado):
   ```batch
   INICIAR_REGISTRY.bat
   ```
   - Usa `root:root` automáticamente

### Verificar Configuración

Para verificar que root tiene acceso sin restricciones:

```bash
docker exec mariadb mysql -u root -proot -e "SHOW GRANTS FOR 'root'@'%';"
```

Deberías ver:
```
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION
```

## Notas Importantes

⚠️ **MODO DESARROLLO**: Esta configuración es solo para desarrollo. En producción, deberías:
- Usar usuarios específicos con permisos limitados
- Implementar autenticación adecuada
- Restringir acceso por host/IP
- Usar contraseñas seguras

✅ **Ventajas del Modo Sin Autenticación**:
- Sin problemas de autenticación 1045
- Fácil de configurar y mantener
- Acceso directo para desarrollo y pruebas
- Registry puede acceder sin restricciones

## Solución de Problemas

### Si aparece error 1045 Access denied

1. **Verificar que el contenedor está corriendo**:
   ```bash
   docker ps --filter "name=mariadb"
   ```

2. **Verificar configuración de root**:
   ```bash
   docker exec mariadb mysql -u root -proot -e "SELECT User, Host, plugin FROM mysql.user WHERE User = 'root';"
   ```

3. **Recrear el contenedor** (si es necesario):
   ```bash
   docker-compose down
   docker-compose up -d mariadb
   ```

4. **Aplicar configuración manualmente**:
   ```bash
   docker exec mariadb mysql -u root -proot -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION; FLUSH PRIVILEGES;"
   ```

## Archivos Modificados

- ✅ `RUN_CENTRAL.bat`
- ✅ `PC_A_RUN.bat`
- ✅ `INICIAR_REGISTRY.bat`
- ✅ `docker-compose.yml`
- ✅ `db/setup_sin_autenticacion.sql` (nuevo)

## Archivos No Modificados (pero compatibles)

- ✅ `INICIAR_REGISTRY.ps1` (ya usaba root:root)
- ✅ `ev_registry/EV_Registry.py` (acepta root:root como parámetro)
- ✅ `ev_central/EV_Central.py` (acepta cualquier usuario como parámetro)



