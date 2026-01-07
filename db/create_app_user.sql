-- Script para configurar MySQL 5.7
-- Este script se ejecuta automáticamente al iniciar MySQL
-- MySQL 5.7 usa mysql_native_password por defecto, compatible con todos los clientes

-- Asegurar que root tiene acceso desde todos los hosts
ALTER USER 'root'@'localhost' IDENTIFIED BY 'root';
ALTER USER 'root'@'%' IDENTIFIED BY 'root';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;

-- Crear usuario de aplicación con acceso remoto y local
-- Este usuario es usado por EV_Registry y EV_Central según los requisitos de autenticación

DROP USER IF EXISTS 'evcharging_app'@'%';
DROP USER IF EXISTS 'evcharging_app'@'localhost';
DROP USER IF EXISTS 'evcharging_app'@'127.0.0.1';

CREATE USER 'evcharging_app'@'%' IDENTIFIED WITH mysql_native_password BY 'evcharging_app_pass';
CREATE USER 'evcharging_app'@'localhost' IDENTIFIED WITH mysql_native_password BY 'evcharging_app_pass';
CREATE USER 'evcharging_app'@'127.0.0.1' IDENTIFIED WITH mysql_native_password BY 'evcharging_app_pass';

-- Permisos para EV_Registry: WRITE, UPDATE (registrar CPs, dar de baja, almacenar credenciales)
-- Permisos para EV_Central: READ, UPDATE, DELETE (leer credenciales, gestionar claves)
-- Se otorgan todos los privilegios en evcharging.* para permitir ambas operaciones
GRANT SELECT, INSERT, UPDATE, DELETE ON evcharging.* TO 'evcharging_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON evcharging.* TO 'evcharging_app'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON evcharging.* TO 'evcharging_app'@'127.0.0.1';

FLUSH PRIVILEGES;

SELECT 'MySQL configurado con mysql_native_password - root y evcharging_app disponibles' AS status;

