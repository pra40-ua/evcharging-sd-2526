# Solución: Error 1045 Access denied para ev_user

## Problema

Error al conectar con MariaDB desde Python:
```
[CENTRAL] ⚠️ PyMySQL falló: (1045, "Access denied for user 'ev_user'@'localhost' (using password: YES)")
[CENTRAL] ❌ Error conectando con mysql.connector: 1045 (28000): Access denied for user 'ev_user'@'localhost' (using password: YES)
```

## Causas Identificadas

### Causa 1: Host Permitido Incorrecto (MÁS PROBABLE)
- El usuario `ev_user` estaba creado solo para `localhost`
- La aplicación Python se conecta desde otro host (127.0.0.1, IP remota, etc.)
- **Solución**: Crear usuario con host `%` que permite conexiones desde cualquier host

### Causa 2: Plugin de Autenticación Incompatible
- MariaDB puede usar plugins como `unix_socket` o `ed25519` por defecto
- Los drivers de Python (PyMySQL, mysql.connector) requieren `mysql_native_password`
- **Solución**: Forzar el plugin `mysql_native_password` explícitamente

## Solución Implementada

### 1. Script SQL Automático (`db/create_ev_user.sql`)
Se ejecuta automáticamente al iniciar el contenedor MariaDB y crea:
- Usuario `ev_user@'%'` - Permite conexiones desde **cualquier host**
- Usuario `ev_user@'localhost'` - Para conexiones locales
- Usuario `ev_user@'127.0.0.1'` - Para conexiones desde 127.0.0.1
- Todos con plugin `mysql_native_password` explícitamente
- Permisos completos en la base de datos `evcharging`

### 2. Scripts de Reparación Manual

#### Opción A: Script Batch (Windows)
```batch
REPARAR_EV_USER.bat
```

#### Opción B: Script PowerShell
```powershell
.\REPARAR_EV_USER.ps1
```

#### Opción C: Comando Docker Directo
```bash
docker exec -i mariadb mysql -u root -proot < db/fix_ev_user.sql
```

#### Opción D: Desde dentro del contenedor
```bash
docker exec -it mariadb mysql -u root -proot evcharging
```
Luego ejecutar:
```sql
DROP USER IF EXISTS 'ev_user'@'%';
DROP USER IF EXISTS 'ev_user'@'localhost';
DROP USER IF EXISTS 'ev_user'@'127.0.0.1';

CREATE USER 'ev_user'@'%' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';
CREATE USER 'ev_user'@'localhost' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';
CREATE USER 'ev_user'@'127.0.0.1' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';

GRANT SELECT, INSERT, UPDATE, DELETE ON evcharging.* TO 'ev_user'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON evcharging.* TO 'ev_user'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON evcharging.* TO 'ev_user'@'127.0.0.1';

FLUSH PRIVILEGES;
```

## Configuración Actualizada

### Archivos Modificados:
1. **`RUN_CENTRAL.bat`**: Usa `ev_user:ev_user_pass` en lugar de `root:root`
2. **`PC_A_RUN.bat`**: `web_dashboard.py` también usa `ev_user`
3. **`docker-compose.yml`**: Incluye el script `create_ev_user.sql` en la inicialización

### Credenciales:
- **Usuario**: `ev_user`
- **Contraseña**: `ev_user_pass`
- **Base de datos**: `evcharging`
- **Host**: `127.0.0.1` (o la IP del contenedor)
- **Puerto**: `3306`

### Formato de conexión:
```
127.0.0.1:3306:ev_user:ev_user_pass:evcharging
```

## Verificación

Para verificar que el usuario está correctamente configurado:

```bash
docker exec mariadb mysql -u root -proot -e "SELECT User, Host, plugin FROM mysql.user WHERE User = 'ev_user';"
```

Deberías ver:
```
+---------+-----------+-----------------------+
| User    | Host      | plugin               |
+---------+-----------+-----------------------+
| ev_user | %         | mysql_native_password|
| ev_user | 127.0.0.1 | mysql_native_password|
| ev_user | localhost | mysql_native_password|
+---------+-----------+-----------------------+
```

## Si el Problema Persiste

1. **Verificar que el contenedor está corriendo**:
   ```bash
   docker ps --filter "name=mariadb"
   ```

2. **Verificar que la base de datos existe**:
   ```bash
   docker exec mariadb mysql -u root -proot -e "SHOW DATABASES LIKE 'evcharging';"
   ```

3. **Probar conexión manual**:
   ```bash
   docker exec mariadb mysql -u ev_user -pev_user_pass evcharging -e "SHOW TABLES;"
   ```

4. **Si falla, ejecutar el script de reparación**:
   ```bash
   .\REPARAR_EV_USER.bat
   ```

5. **Reiniciar el contenedor si es necesario**:
   ```bash
   docker-compose restart mariadb
   ```

## Notas Importantes

- El usuario `%` permite conexiones desde **cualquier host**, lo cual es necesario para conexiones remotas
- El plugin `mysql_native_password` es **compatible** con PyMySQL y mysql.connector
- Después de ejecutar `FLUSH PRIVILEGES`, los cambios se aplican inmediatamente
- Si recreas el contenedor desde cero, el script se ejecutará automáticamente



