-- Script simplificado: SIN AUTENTICACIÓN - root sin contraseña
-- Este script se ejecuta automáticamente al iniciar MySQL
-- MODO DESARROLLO: Acceso sin contraseña
-- IMPORTANTE: Este script se ejecuta como root con contraseña temporal 'root'

-- Asegurar que la base de datos existe con charset utf8mb4
CREATE DATABASE IF NOT EXISTS evcharging CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- Configurar charset por defecto para la sesión
SET NAMES utf8mb4 COLLATE utf8mb4_general_ci;

-- Eliminar usuarios root existentes y recrearlos SIN CONTRASEÑA
-- Usar ALTER USER primero (más confiable) y luego DROP/CREATE si es necesario
ALTER USER 'root'@'localhost' IDENTIFIED BY '';
ALTER USER 'root'@'%' IDENTIFIED BY '';

-- Eliminar y recrear para asegurar configuración correcta
DROP USER IF EXISTS 'root'@'localhost';
DROP USER IF EXISTS 'root'@'%';
DROP USER IF EXISTS 'root'@'127.0.0.1';

-- Crear root SIN CONTRASEÑA (contraseña vacía)
CREATE USER 'root'@'localhost' IDENTIFIED BY '';
CREATE USER 'root'@'%' IDENTIFIED BY '';
CREATE USER 'root'@'127.0.0.1' IDENTIFIED BY '';

-- Otorgar TODOS los privilegios sin restricciones
GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost' WITH GRANT OPTION;
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;
GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION;

-- Aplicar cambios
FLUSH PRIVILEGES;

-- Verificar configuración
SELECT 'MariaDB configurado: root SIN CONTRASEÑA (sin autenticacion)' AS status;
SELECT CONCAT('Usuario: ', User, '@', Host) AS usuario_info 
FROM mysql.user 
WHERE User = 'root' AND Host IN ('localhost', '%', '127.0.0.1')
ORDER BY Host;

