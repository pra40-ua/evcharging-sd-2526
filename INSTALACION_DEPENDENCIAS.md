# 📦 Guía de Instalación de Dependencias

## Para Diferentes Ordenadores

Este documento explica cómo instalar automáticamente todas las dependencias necesarias para ejecutar el sistema en **diferentes ordenadores** (PC_A, PC_B, etc.).

---

## 🚀 Instalación Automática Rápida

### Opción 1: Script de Setup Completo (RECOMENDADO)

```batch
setup_environment.bat
```

Este script:
- ✅ Verifica Python instalado
- ✅ Actualiza pip
- ✅ Instala todas las dependencias de `requirements.txt`
- ✅ Verifica Docker
- ✅ Configura topics de Kafka

### Opción 2: Solo Instalar Dependencias Python

```batch
install_requirements.bat
```

Instala solo las dependencias de Python con manejo de errores.

---

## 📋 Scripts Mejorados con Auto-Instalación

### Para PC_A (Servidor Central)

```batch
run_PC_A.bat
```

**Ahora incluye:**
1. ✅ Verificación automática de Python
2. ✅ Instalación automática de dependencias Python
3. ✅ Verificación de Docker
4. ✅ Generación de comandos con IP actual
5. ✅ Lanzamiento de Central + Kafka + MySQL

### Para PC_B (Puntos de Recarga)

```batch
run_PC_B.bat
```

**Ahora incluye:**
1. ✅ Verificación automática de Python
2. ✅ Instalación automática de dependencias Python
3. ✅ Verificación opcional de Docker
4. ✅ Lectura automática de IP de Central desde `central_ip.txt`
5. ✅ Lanzamiento de Engine + Monitor + Driver

### Para Demo Rápida

```batch
QUICK_START.bat
```

**Ahora incluye:**
1. ✅ Verificación de Python
2. ✅ Instalación automática de dependencias
3. ✅ Verificación de Kafka/MySQL
4. ✅ Lanzamiento de 10 CPs + 8 Drivers + Dashboard

---

## 🐳 Docker Compose Mejorado

El archivo `docker-compose.yml` **ahora incluye**:

### 1. Kafka con Health Check
```yaml
kafka:
  healthcheck:
    test: ["CMD", "kafka-broker-api-versions", ...]
    interval: 10s
```

### 2. MySQL Incluido
```yaml
mysql:
  image: mysql:8
  environment:
    - MYSQL_ROOT_PASSWORD=root
    - MYSQL_DATABASE=evcharging
  volumes:
    - ./db/init.sql:/docker-entrypoint-initdb.d/01_schema.sql
```

### 3. Creación Automática de Topics
```yaml
kafka-setup:
  command: >
    bash -c "
      kafka-topics --create --topic telemetria_cp ...
      kafka-topics --create --topic driver_requests ...
      kafka-topics --create --topic central_commands ...
    "
```

**Uso:**
```batch
docker compose up -d
```

Esto arrancará:
- ✅ Kafka (puerto 9092)
- ✅ MySQL (puerto 3306)
- ✅ Creará topics automáticamente

---

## 📦 Dependencias Incluidas

### `requirements.txt` (actualizado)

```txt
confluent-kafka==2.11.1     # Streaming de Eventos
mysql-connector-python      # Base de datos
kafka-python==2.0.2         # Cliente Kafka
rich                        # TUI mejorada
flask==3.0.0                # Dashboard web
flask-cors==4.0.0           # CORS para API
```

### Instalación Manual (si es necesario)

```bash
# Actualizar pip
python -m pip install --upgrade pip

# Instalar todas las dependencias
pip install -r requirements.txt

# O instalar una por una
pip install kafka-python==2.0.2
pip install mysql-connector-python
pip install flask==3.0.0
pip install flask-cors==4.0.0
pip install rich
pip install confluent-kafka==2.11.1
```

---

## 🔧 Verificación de Instalación

### Verificar Python y Pip
```batch
python --version
python -m pip --version
```

### Verificar Dependencias Instaladas
```batch
python -m pip list | findstr /I "kafka mysql flask rich"
```

**Salida esperada:**
```
confluent-kafka        2.11.1
Flask                  3.0.0
flask-cors             4.0.0
kafka-python           2.0.2
mysql-connector-python 8.x.x
rich                   13.x.x
```

### Verificar Docker
```batch
docker --version
docker compose --version
docker ps
```

### Verificar Kafka
```batch
# Crear topic de prueba
docker exec kafka kafka-topics --create --topic test --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1

# Listar topics
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092

# Eliminar topic de prueba
docker exec kafka kafka-topics --delete --topic test --bootstrap-server localhost:9092
```

---

## 🆘 Solución de Problemas

### Python no está instalado
```batch
# Descargar desde:
https://www.python.org/downloads/

# Durante instalación:
☑️ Marcar "Add Python to PATH"
```

### Pip no funciona
```bash
# Reinstalar pip
python -m ensurepip --default-pip
python -m pip install --upgrade pip
```

### Error instalando confluent-kafka (Windows)
```bash
# Usar alternativa kafka-python (ya incluida)
pip install kafka-python==2.0.2

# El sistema funcionará correctamente con kafka-python
```

### Docker no está corriendo
```batch
# Iniciar Docker Desktop manualmente
# Esperar a ver "Docker Desktop is running"
# Verificar:
docker ps
```

### Kafka no responde
```batch
# Verificar contenedor
docker ps | findstr kafka

# Ver logs
docker logs kafka

# Reiniciar
docker compose restart kafka

# Esperar 30 segundos
timeout /t 30
```

### MySQL no conecta
```bash
# Verificar contenedor
docker ps | findstr mysql

# Probar conexión
docker exec mysql mysql -uroot -proot -e "SHOW DATABASES;"

# Ver logs
docker logs mysql
```

### Firewall bloquea puertos
```powershell
# Windows Firewall: Abrir puertos
New-NetFirewallRule -DisplayName "Kafka" -Direction Inbound -LocalPort 9092 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Central" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "MySQL" -Direction Inbound -LocalPort 3306 -Protocol TCP -Action Allow
```

---

## 📝 Checklist para Nuevo Ordenador

### PC_A (Servidor Central)
- [ ] Instalar Python 3.10+ (con "Add to PATH")
- [ ] Instalar Docker Desktop
- [ ] Clonar repositorio
- [ ] Ejecutar `setup_environment.bat`
- [ ] Ejecutar `run_PC_A.bat`
- [ ] Verificar en navegador: Dashboard web funcionando

### PC_B (Puntos de Recarga)
- [ ] Instalar Python 3.10+ (con "Add to PATH")
- [ ] Instalar Docker Desktop (opcional)
- [ ] Clonar repositorio
- [ ] Copiar `central_ip.txt` desde PC_A (o crear manualmente)
- [ ] Ejecutar `setup_environment.bat`
- [ ] Ejecutar `run_PC_B.bat`
- [ ] Verificar ventanas: Engine, Monitor, Driver

### PC_C (Solo Dashboard o Drivers)
- [ ] Instalar Python 3.10+
- [ ] Clonar repositorio
- [ ] Ejecutar `install_requirements.bat`
- [ ] Para Dashboard: `python web_dashboard.py --kafka <IP_KAFKA>:9092`
- [ ] Para Drivers: `python launch_multiple_drivers.py --num 5 --kafka <IP_KAFKA>:9092 --cps 10`

---

## 🌐 Configuración Multi-Ordenador

### 1. PC_A (Central)
```batch
# Generar comandos con IP actual
powershell -ExecutionPolicy Bypass -File .\scripts\generate_commands_A.ps1

# Esto crea:
# - commands_PC_A.ps1
# - central_ip.txt (contiene IP de PC_A)
```

### 2. Compartir IP de Central
```batch
# Opción A: Copiar archivo
copy central_ip.txt \\PC_B\proyecto\

# Opción B: Leer IP manualmente
type central_ip.txt
# Ejemplo: 192.168.1.43
```

### 3. PC_B (Puntos de Recarga)
```batch
# El archivo central_ip.txt debe existir en la raíz
# O editar manualmente commands_PC_B_*.ps1 con la IP correcta
run_PC_B.bat
```

### 4. Otros PCs (Drivers adicionales)
```bash
# Usar la IP de PC_A
python launch_multiple_drivers.py \
  --num 5 \
  --kafka 192.168.1.43:9092 \
  --cps 10
```

---

## 🎯 Resumen de Scripts Nuevos/Mejorados

| Script | Función | Auto-Instalación |
|--------|---------|------------------|
| `setup_environment.bat` | Setup completo inicial | ✅ Sí |
| `install_requirements.bat` | Solo dependencias Python | ✅ Sí |
| `setup_kafka_topics.bat` | Crear topics Kafka | ❌ No (requiere Kafka corriendo) |
| `run_PC_A.bat` | Lanzar PC_A | ✅ Sí |
| `run_PC_B.bat` | Lanzar PC_B | ✅ Sí |
| `QUICK_START.bat` | Demo rápida | ✅ Sí |
| `docker-compose.yml` | Servicios Docker | ✅ Sí (incluye setup) |

---

## ✅ Flujo Recomendado

### Primera Vez en un Ordenador Nuevo

```batch
1. Instalar Python desde https://www.python.org/downloads/
   (Marcar "Add Python to PATH")

2. Instalar Docker Desktop desde https://www.docker.com/products/docker-desktop/
   (Reiniciar tras instalación)

3. Clonar repositorio:
   git clone <repo_url>
   cd evcharging-sd-2526

4. Ejecutar setup:
   setup_environment.bat

5. Lanzar según rol:
   - PC_A: run_PC_A.bat
   - PC_B: run_PC_B.bat
   - Demo: QUICK_START.bat
```

### Ejecuciones Posteriores

```batch
# PC_A
run_PC_A.bat

# PC_B
run_PC_B.bat

# Las dependencias se verifican automáticamente
```

---

**¡Sistema listo para ejecutar en múltiples ordenadores! 🚀**

Para más información:
- **README.md**: Documentación general
- **GUIA_USO_MASIVO.md**: Uso con múltiples instancias
- **RESUMEN_IMPLEMENTACION.md**: Resumen técnico


