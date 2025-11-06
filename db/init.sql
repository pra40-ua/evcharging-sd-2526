CREATE TABLE IF NOT EXISTS charging_points (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cp_id VARCHAR(50) UNIQUE,
  ubicacion VARCHAR(255),
  precio_kwh DECIMAL(10,2),
  estado VARCHAR(32),
  fecha_ultima_conexion DATETIME
);

CREATE TABLE IF NOT EXISTS telemetria_log (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cp_id VARCHAR(50),
  timestamp DOUBLE,
  estado_carga VARCHAR(30),
  kw_entregados DOUBLE,
  tiempo_carga_s INT
);

CREATE TABLE IF NOT EXISTS servicios_activos (
  id INT AUTO_INCREMENT PRIMARY KEY,
  driver_id VARCHAR(50) NOT NULL,
  cp_id VARCHAR(50) NOT NULL,
  estado VARCHAR(32) NOT NULL,
  kw_objetivo DECIMAL(10,2),
  kw_actual DECIMAL(10,2) DEFAULT 0.0,
  fecha_inicio DATETIME NOT NULL,
  fecha_ultima_actualizacion DATETIME NOT NULL,
  tx_id VARCHAR(100),
  INDEX idx_driver_id (driver_id),
  INDEX idx_cp_id (cp_id),
  INDEX idx_estado (estado)
);

CREATE TABLE IF NOT EXISTS tickets_pendientes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  driver_id VARCHAR(50) NOT NULL,
  cp_id VARCHAR(50) NOT NULL,
  energia_kwh DECIMAL(10,2) NOT NULL,
  importe_eur DECIMAL(10,2) NOT NULL,
  duracion_seg INT,
  motivo VARCHAR(255),
  tx_id VARCHAR(100),
  fecha_creacion DATETIME NOT NULL,
  entregado BOOLEAN DEFAULT FALSE,
  fecha_entrega DATETIME,
  INDEX idx_driver_id (driver_id),
  INDEX idx_entregado (entregado)
);