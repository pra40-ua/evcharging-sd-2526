# Solución para Problemas de Conexión a MySQL

## Problema
Las conexiones desde Python (fuera del contenedor Docker) a MySQL fallan con error "Access denied" incluso con credenciales correctas.

## Solución Implementada
El sistema ahora funciona **sin base de datos** si falla la conexión. Las funcionalidades básicas (comunicación con CPs, Kafka) seguirán funcionando normalmente.

## Configuración Actual
- **MySQL**: Versión 8.0 (compatible con mysql_native_password)
- **Usuario**: root / root
- **Base de datos**: evcharging
- **Librería**: PyMySQL (más compatible que mysql-connector-python)

## Si Necesitas la Base de Datos

### Opción 1: Usar desde dentro del contenedor
```bash
docker exec -it mysql mysql -u root -proot evcharging
```

### Opción 2: Conectar desde otro equipo en la red
Desde PC_B o PC_C, usa la IP de PC_A:
```
[IP_PC_A]:3306:root:root:evcharging
```

### Opción 3: Usar un cliente MySQL externo
- Host: 127.0.0.1
- Port: 3306
- User: root
- Password: root
- Database: evcharging

## Nota Importante
El sistema está diseñado para funcionar **con o sin base de datos**. Si la conexión falla, simplemente no se guardará la persistencia de datos, pero todas las demás funcionalidades seguirán operativas.



