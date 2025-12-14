-- Script para crear las tablas faltantes en la base de datos evcharging
-- Ejecutar: docker exec mysql mysql -u root -proot evcharging < db/fix_tables.sql

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

