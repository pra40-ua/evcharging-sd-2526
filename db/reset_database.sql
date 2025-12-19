-- Script para eliminar y recrear completamente la base de datos y usuario
-- Ejecutar: docker exec -i mysql mysql -u root -proot < db/reset_database.sql
-- O desde PowerShell: Get-Content db\reset_database.sql | docker exec -i mysql mysql -u root -proot

-- Eliminar base de datos si existe
DROP DATABASE IF EXISTS evcharging;

-- Eliminar base de datos si existe
DROP DATABASE IF EXISTS evcharging;

-- Crear base de datos
CREATE DATABASE evcharging CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- Crear o actualizar usuario root@% para conexiones desde Docker
-- Intentar crear, si ya existe se actualizará con ALTER USER después
DROP USER IF EXISTS 'root'@'%';
CREATE USER 'root'@'%' IDENTIFIED BY 'root';

-- Actualizar contraseña de root@localhost
ALTER USER 'root'@'localhost' IDENTIFIED BY 'root';

-- Otorgar todos los privilegios
GRANT ALL PRIVILEGES ON evcharging.* TO 'root'@'%';
GRANT ALL PRIVILEGES ON evcharging.* TO 'root'@'localhost';

-- Aplicar cambios
FLUSH PRIVILEGES;

-- Usar la base de datos
USE evcharging;

-- Crear todas las tablas necesarias
CREATE TABLE IF NOT EXISTS charging_points (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cp_id VARCHAR(50) UNIQUE,
  ubicacion VARCHAR(255),
  precio_kwh DECIMAL(10,2),
  estado VARCHAR(32),
  fecha_ultima_conexion DATETIME
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS telemetria_log (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cp_id VARCHAR(50),
  timestamp DOUBLE,
  estado_carga VARCHAR(30),
  kw_entregados DOUBLE,
  tiempo_carga_s INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla para claves de cifrado simétrico por CP
CREATE TABLE IF NOT EXISTS cp_encryption_keys (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cp_id VARCHAR(50) UNIQUE NOT NULL,
  encryption_key VARCHAR(255) NOT NULL,
  fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
  fecha_ultima_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  activo BOOLEAN DEFAULT TRUE,
  INDEX idx_cp_id (cp_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla de auditoría de eventos
CREATE TABLE IF NOT EXISTS audit_log (
  id INT AUTO_INCREMENT PRIMARY KEY,
  fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
  origen_ip VARCHAR(45),
  cp_id VARCHAR(50),
  accion VARCHAR(100) NOT NULL,
  descripcion TEXT,
  resultado VARCHAR(50),
  INDEX idx_fecha_hora (fecha_hora),
  INDEX idx_cp_id (cp_id),
  INDEX idx_accion (accion)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla para alertas climatológicas
CREATE TABLE IF NOT EXISTS weather_alerts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cp_id VARCHAR(50) NOT NULL,
  temperatura DECIMAL(5,2),
  alerta_activa BOOLEAN DEFAULT FALSE,
  fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_cp_id (cp_id),
  INDEX idx_alerta_activa (alerta_activa)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Verificar que todo se creó correctamente
SELECT 'Base de datos y tablas creadas correctamente' AS resultado;
SHOW TABLES;

