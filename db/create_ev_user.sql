-- Script para crear usuario ev_user con plugin mysql_native_password
-- Este script se ejecuta automáticamente al iniciar MySQL
-- Soluciona problemas de autenticación con drivers de Python (PyMySQL, mysql.connector)
-- IMPORTANTE: El usuario '%' permite conexiones desde cualquier host (localhost, 127.0.0.1, IPs remotas, etc.)

-- Asegurar que la base de datos existe
CREATE DATABASE IF NOT EXISTS evcharging;

-- Eliminar usuario si existe (para recrearlo con el plugin correcto)
-- Esto asegura que se recrea con la configuración correcta
DROP USER IF EXISTS 'ev_user'@'%';
DROP USER IF EXISTS 'ev_user'@'localhost';
DROP USER IF EXISTS 'ev_user'@'127.0.0.1';

-- Crear usuario ev_user con plugin mysql_native_password explícitamente
-- El usuario '%' permite conexiones desde CUALQUIER host (localhost, 127.0.0.1, IPs remotas, etc.)
-- Este plugin es compatible con todos los drivers de Python (PyMySQL, mysql.connector)
CREATE USER 'ev_user'@'%' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';
CREATE USER 'ev_user'@'localhost' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';
CREATE USER 'ev_user'@'127.0.0.1' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';

-- Otorgar permisos necesarios en la base de datos evcharging
-- Permisos completos para gestionar CPs, telemetría, claves de cifrado, auditoría, etc.
-- El usuario '%' es el más importante ya que permite conexiones remotas
GRANT SELECT, INSERT, UPDATE, DELETE ON evcharging.* TO 'ev_user'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON evcharging.* TO 'ev_user'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON evcharging.* TO 'ev_user'@'127.0.0.1';

-- Aplicar cambios inmediatamente
FLUSH PRIVILEGES;

-- Verificar que el usuario se creó correctamente y mostrar información
SELECT 'Usuario ev_user creado con mysql_native_password' AS status;
SELECT CONCAT('Usuario: ', User, '@', Host, ' | Plugin: ', plugin) AS usuario_info 
FROM mysql.user 
WHERE User = 'ev_user';
SELECT 'Listo para conexiones desde Python (PyMySQL y mysql.connector)' AS mensaje;

