-- Script para configurar permisos de MySQL desde el inicio
-- Permite conexiones desde cualquier IP (necesario para Docker)
-- MySQL 5.7 usa mysql_native_password por defecto, así que no hay problemas de autenticación

-- Crear usuario root que puede conectarse desde cualquier IP
CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY 'root';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;

-- Aplicar cambios
FLUSH PRIVILEGES;
