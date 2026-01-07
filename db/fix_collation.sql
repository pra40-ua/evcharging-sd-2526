-- Script para corregir collation de tablas existentes
-- Compatible con MySQL 5.7 (usa utf8mb4_general_ci en lugar de utf8mb4_0900_ai_ci)

-- Usar la base de datos
USE evcharging;

-- Configurar charset por defecto
SET NAMES utf8mb4 COLLATE utf8mb4_general_ci;

-- Corregir collation de la base de datos
ALTER DATABASE evcharging CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- Corregir collation de tablas existentes
ALTER TABLE charging_points CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
ALTER TABLE telemetria_log CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
ALTER TABLE cp_encryption_keys CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
ALTER TABLE audit_log CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
ALTER TABLE weather_alerts CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

SELECT 'Collation corregida a utf8mb4_general_ci (compatible con MySQL 5.7)' AS status;

