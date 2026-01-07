@echo off
REM Script para verificar y configurar MariaDB para conexiones remotas en PC_A

echo ========================================================================
echo           VERIFICAR MARIADB PARA CONEXIONES REMOTAS
echo ========================================================================
echo.

REM Verificar contenedor
docker ps --filter "name=mariadb" --format "{{.Names}}" | findstr /C:"mariadb" >nul
if %errorlevel% neq 0 (
    echo [ERROR] El contenedor mariadb no esta corriendo.
    echo Ejecuta: docker-compose up -d mariadb
    pause
    exit /b 1
)

echo [PASO 1/4] Verificando que MariaDB esta corriendo...
docker ps --filter "name=mariadb" --format "table {{.Names}}\t{{.Status}}"
echo.

echo [PASO 2/4] Verificando que MariaDB escucha en todas las interfaces...
docker exec mariadb netstat -tlnp 2>nul | findstr ":3306" >nul
if %errorlevel% neq 0 (
    echo [ADVERTENCIA] No se pudo verificar con netstat
) else (
    docker exec mariadb netstat -tlnp 2>nul | findstr ":3306"
    echo [OK] MariaDB esta escuchando
)
echo.

echo [PASO 3/4] Verificando usuarios root para conexiones remotas...
docker exec mariadb mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "SELECT User, Host FROM mysql.user WHERE User='root' ORDER BY Host;" 2>&1
echo.

echo [PASO 4/4] Configurando root@%% para conexiones remotas...
docker exec mariadb mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "DROP USER IF EXISTS 'root'@'%%';" 2>nul
docker exec mariadb mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "CREATE USER 'root'@'%%' IDENTIFIED BY '';" 2>&1
docker exec mariadb mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'%%' WITH GRANT OPTION;" 2>&1
docker exec mariadb mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "FLUSH PRIVILEGES;" 2>&1
echo [OK] root@%% configurado para conexiones remotas
echo.

echo ========================================================================
echo           VERIFICACION COMPLETADA
echo ========================================================================
echo.
echo IMPORTANTE: Verifica que el firewall permite conexiones al puerto 3306
echo.
echo En PowerShell como Administrador, ejecuta:
echo   New-NetFirewallRule -DisplayName "MySQL" -Direction Inbound -LocalPort 3306 -Protocol TCP -Action Allow
echo.
echo Para verificar la regla:
echo   Get-NetFirewallRule -DisplayName "MySQL"
echo.
pause



