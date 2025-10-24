CREATE TABLE IF NOT EXISTS charging_points (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cp_id VARCHAR(50) UNIQUE,
  ubicacion VARCHAR(255),
  precio_kwh DECIMAL(10,2),
  estado VARCHAR(32),
  fecha_ultima_conexion DATETIME
);