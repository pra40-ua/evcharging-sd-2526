-- Script para arreglar autenticación de MySQL
-- Se ejecuta manualmente cuando hay problemas de conexión

-- Forzar mysql_native_password para root
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'root';
ALTER USER 'root'@'%' IDENTIFIED WITH mysql_native_password BY 'root';

-- Asegurar que root tiene todos los privilegios
GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost' WITH GRANT OPTION;
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;

FLUSH PRIVILEGES;

SELECT 'MySQL autenticación arreglada' AS status;



