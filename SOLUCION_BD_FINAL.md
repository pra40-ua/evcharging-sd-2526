# Solución para Usar Base de Datos MySQL

## Problema Actual
MySQL 8 en Docker en Windows tiene un problema conocido con conexiones desde Python usando `127.0.0.1` o `localhost`. El error es:
```
Access denied for user 'root'@'localhost' (using password: YES)
```

## Solución Implementada

El sistema ahora:
1. **Intenta conectarse a la BD primero** (PyMySQL y mysql.connector)
2. **Si falla, usa archivos JSON como fallback** automáticamente
3. **Mantiene persistencia** en ambos casos

## Para Forzar el Uso de BD

Si quieres usar la BD exclusivamente, tienes estas opciones:

### Opción 1: Usar desde otro equipo en la red
Desde PC_B o PC_C, la conexión funciona usando la IP de PC_A:
```
[IP_PC_A]:3306:root:root:evcharging
```

### Opción 2: Configurar MySQL manualmente
Ejecuta estos comandos dentro del contenedor MySQL:

```bash
docker exec -it mysql mysql -u root -proot
```

Luego en MySQL:
```sql
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'root';
ALTER USER 'root'@'%' IDENTIFIED WITH mysql_native_password BY 'root';
CREATE USER IF NOT EXISTS 'root'@'127.0.0.1' IDENTIFIED WITH mysql_native_password BY 'root';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION;
FLUSH PRIVILEGES;
```

### Opción 3: Usar un cliente MySQL externo
- MySQL Workbench
- DBeaver
- HeidiSQL
- phpMyAdmin

Conecta con:
- Host: 127.0.0.1
- Port: 3306
- User: root
- Password: root
- Database: evcharging

## Estado Actual

✅ **EV_Central**: Intenta BD, fallback a archivos
✅ **EV_Registry**: Intenta BD, fallback a archivos  
✅ **Claves de cifrado**: Guardadas en BD o archivos
✅ **Registros de CPs**: Guardados en BD o archivos
✅ **Credenciales**: Guardadas en BD o archivos

## Nota Importante

El sistema está diseñado para funcionar **con o sin BD**. Si la conexión falla, automáticamente usa archivos JSON como respaldo, manteniendo toda la funcionalidad.



