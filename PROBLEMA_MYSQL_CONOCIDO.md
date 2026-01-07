# Problema Conocido: Conexión a MySQL desde Windows

## Descripción del Problema

MySQL 8 en Docker tiene un problema conocido con conexiones desde fuera del contenedor en Windows cuando `skip_name_resolve` está activado. El error es:

```
Access denied for user 'root'@'localhost' (using password: YES)
```

## Causa

Cuando Python se conecta usando `127.0.0.1`, MySQL (con `skip_name_resolve=ON`) resuelve la conexión a `localhost`, pero hay un problema con la autenticación que impide la conexión exitosa.

## Solución Implementada

El sistema está configurado para **funcionar sin base de datos** si falla la conexión. Todas las funcionalidades básicas (comunicación con CPs, Kafka, comandos) seguirán funcionando normalmente.

## Estado Actual

- ✅ Sistema funciona sin BD si falla la conexión
- ✅ PyMySQL instalado y configurado
- ✅ MySQL 8.0 con mysql_native_password
- ⚠️ Conexión desde Python externo no funciona (problema conocido)

## Alternativas

### Opción 1: Usar desde dentro del contenedor
```bash
docker exec -it mysql mysql -u root -proot evcharging
```

### Opción 2: Conectar desde otro equipo en la red
Desde PC_B o PC_C, la conexión funciona usando la IP de PC_A:
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

**El sistema está diseñado para funcionar con o sin base de datos.** Si la conexión falla, simplemente no se guardará la persistencia de datos, pero todas las demás funcionalidades seguirán operativas.



