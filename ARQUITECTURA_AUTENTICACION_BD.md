# Arquitectura de Autenticación de Base de Datos

## Resumen

El sistema utiliza un usuario de aplicación dedicado (`evcharging_app`) para controlar el acceso a la base de datos según los requisitos de seguridad. Cada módulo tiene permisos específicos según su función.

## Usuario de Aplicación

**Usuario**: `evcharging_app`  
**Contraseña**: `evcharging_app_pass`  
**Base de datos**: `evcharging`

### Permisos Otorgados

El usuario `evcharging_app` tiene los siguientes permisos en la base de datos `evcharging`:
- **SELECT**: Lectura de datos (requerido por EV_Central para autenticación)
- **INSERT**: Inserción de nuevos registros (requerido por EV_Registry para registrar CPs)
- **UPDATE**: Actualización de registros existentes (requerido por ambos módulos)
- **DELETE**: Eliminación de registros (requerido por EV_Central para revocar claves)

**Nota**: Aunque se otorgan `ALL PRIVILEGES` en `evcharging.*`, estos se limitan únicamente a la base de datos `evcharging`, cumpliendo con el principio de mínimo privilegio a nivel de base de datos.

## Módulos y sus Requisitos

### 1. EV_Registry (Registro)

**Propósito**: Gestión de alta y baja de CPs, almacenamiento de credenciales

**Permisos requeridos**:
- ✅ **WRITE (INSERT)**: Registrar nuevos CPs con su ID, localización y credenciales
- ✅ **UPDATE**: Actualizar información de CPs existentes, dar de baja (marcar como inactivos)

**Operaciones**:
- Registrar nuevos CPs: `INSERT INTO cp_registry`, `INSERT INTO cp_credentials`
- Dar de baja CPs: `UPDATE cp_registry SET activo = FALSE`
- Actualizar credenciales: `UPDATE cp_credentials SET ...`

**Configuración**:
- Script: `INICIAR_REGISTRY.bat` (PC_A) o `INICIAR_REGISTRY_PC_B.bat` (PC_B)
- Usuario BD: `evcharging_app:evcharging_app_pass`
- Host BD: `127.0.0.1:3306` (PC_A) o `[IP_PC_A]:3306` (PC_B)

### 2. EV_Central (Central de Control)

**Propósito**: Validación de identidad de CPs, gestión del ciclo de vida de claves

**Permisos requeridos**:
- ✅ **READ (SELECT)**: Leer credenciales almacenadas por EV_Registry para autenticar CPs
- ✅ **UPDATE**: Actualizar información de CPs, estados, telemetría
- ✅ **DELETE**: Borrar o revocar claves de cifrado si se detecta vulnerabilidad

**Operaciones**:
- Autenticación de CPs: `SELECT * FROM cp_credentials WHERE cp_id = ?`
- Lectura de registros: `SELECT * FROM cp_registry WHERE cp_id = ?`
- Gestión de claves: `DELETE FROM cp_encryption_keys WHERE cp_id = ?`
- Actualización de estados: `UPDATE charging_points SET estado = ? WHERE cp_id = ?`

**Configuración**:
- Script: `RUN_CENTRAL.bat` o `PC_A_RUN.bat`
- Usuario BD: `evcharging_app:evcharging_app_pass`
- Host BD: `127.0.0.1:3306`

## Tablas y Accesos

### Tablas que EV_Registry modifica:
- `cp_registry`: Registro de CPs (ID, ubicación, estado activo/inactivo)
- `cp_credentials`: Credenciales de autenticación (username, password_hash, salt)

### Tablas que EV_Central lee/modifica:
- `cp_registry`: Lectura para validar que CP está registrado
- `cp_credentials`: Lectura para autenticar CPs durante conexión
- `cp_encryption_keys`: Lectura/escritura/eliminación para gestión de claves
- `charging_points`: Actualización de estados de CPs
- `telemetria_log`: Escritura de historial de telemetría
- `audit_log`: Escritura de eventos de auditoría
- `weather_alerts`: Lectura/escritura de alertas climatológicas

## Seguridad

### Principio de Mínimo Privilegio
El usuario `evcharging_app` solo tiene acceso a la base de datos `evcharging`, no a otras bases de datos del sistema.

### Separación de Responsabilidades
- **EV_Registry**: Responsable de la gestión de registros y credenciales (alta/baja)
- **EV_Central**: Responsable de la validación y gestión operativa (autenticación, claves)

### Fallback
Si la conexión a la BD falla, ambos módulos usan almacenamiento en archivos JSON como respaldo, manteniendo la funcionalidad completa.

## Configuración Actual

### Usuario Root
El usuario `root` se mantiene para:
- Administración de la base de datos
- Scripts de inicialización y reparación
- Acceso desde herramientas externas (MySQL Workbench, etc.)

### Usuario de Aplicación
El usuario `evcharging_app` es el utilizado por:
- ✅ EV_Registry (PC_A y PC_B)
- ✅ EV_Central
- ✅ Dashboard Web

## Notas de Implementación

- Los permisos se configuran automáticamente al iniciar MariaDB mediante `db/create_app_user.sql`
- El usuario se crea para múltiples hosts (`%`, `localhost`, `127.0.0.1`) para compatibilidad
- Si la BD no está disponible, ambos módulos usan archivos JSON como fallback

