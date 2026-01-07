-- Script para configurar MySQL 5.7 para conexiones desde Python
-- Este script se ejecuta automáticamente al iniciar MySQL
-- MySQL 5.7 usa mysql_native_password por defecto, compatible con todos los clientes

-- Asegurar que root tiene acceso desde todos los hosts posibles
-- Usar ALTER USER para actualizar contraseñas (más confiable en MariaDB 10.11)

-- Actualizar contraseñas para todos los hosts con mysql_native_password
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'root';
ALTER USER 'root'@'%' IDENTIFIED WITH mysql_native_password BY 'root';

-- Crear root@127.0.0.1 si no existe con mysql_native_password
CREATE USER IF NOT EXISTS 'root'@'127.0.0.1' IDENTIFIED WITH mysql_native_password BY 'root';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION;

-- Asegurar que todos tienen GRANT OPTION
GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost' WITH GRANT OPTION;
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;

FLUSH PRIVILEGES;

SELECT 'MariaDB configurado para conexiones desde Python' AS status;

