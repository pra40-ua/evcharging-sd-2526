-- Script para corregir/verificar usuario ev_user en contenedores existentes
-- Ejecutar manualmente si hay problemas de autenticación:
-- docker exec -i mariadb mysql -u root -proot < db/fix_ev_user.sql
-- O desde dentro del contenedor:
-- docker exec -it mariadb mysql -u root -proot evcharging
-- Luego copiar y pegar el contenido de este script

-- Asegurar que la base de datos existe
CREATE DATABASE IF NOT EXISTS evcharging;

-- Eliminar todas las instancias del usuario ev_user para recrearlo limpiamente
DROP USER IF EXISTS 'ev_user'@'%';
DROP USER IF EXISTS 'ev_user'@'localhost';
DROP USER IF EXISTS 'ev_user'@'127.0.0.1';

-- Crear usuario ev_user con plugin mysql_native_password
-- El usuario '%' es CRÍTICO: permite conexiones desde cualquier host
CREATE USER 'ev_user'@'%' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';
CREATE USER 'ev_user'@'localhost' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';
CREATE USER 'ev_user'@'127.0.0.1' IDENTIFIED WITH mysql_native_password BY 'ev_user_pass';

-- Otorgar permisos en la base de datos evcharging
-- El usuario '%' es el más importante para conexiones remotas
GRANT SELECT, INSERT, UPDATE, DELETE ON evcharging.* TO 'ev_user'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON evcharging.* TO 'ev_user'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON evcharging.* TO 'ev_user'@'127.0.0.1';

-- Aplicar cambios
FLUSH PRIVILEGES;

-- Verificar la configuración
SELECT '✓ Usuario ev_user corregido/verificado' AS resultado;
SELECT CONCAT('Usuario: ', User, '@', Host, ' | Plugin: ', plugin, ' | Contraseña: ', IF(authentication_string='', 'NO', 'SÍ')) AS detalle
FROM mysql.user 
WHERE User = 'ev_user'
ORDER BY Host;

-- Verificar permisos
SHOW GRANTS FOR 'ev_user'@'%';



