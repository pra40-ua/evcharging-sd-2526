# 📜 Guía Rápida de Scripts

Resumen de todos los scripts disponibles y cuándo usarlos.

---

## 🎬 Scripts de Inicio

### `QUICK_START.bat` ⭐
**Uso más común para demostración**
```batch
QUICK_START.bat
```
- Instala dependencias automáticamente
- Lanza 10 CPs + 8 Drivers + Dashboard
- Todo en un solo comando

### `setup_environment.bat`
**Primera vez en un ordenador nuevo**
```batch
setup_environment.bat
```
- Verifica Python, pip, Docker
- Instala todas las dependencias
- Configura el entorno completo

---

## 🖥️ Scripts por Ordenador

### PC_A (Servidor Central)

```batch
run_PC_A.bat
```
- Instala dependencias Python
- Verifica Docker
- Detecta IP local automáticamente
- Lanza: Central + Kafka + MySQL

### PC_B (Puntos de Recarga)

```batch
run_PC_B.bat
```
- Instala dependencias Python
- Lee IP de Central desde `central_ip.txt`
- Lanza: Engine + Monitor + Driver

---

## 🐍 Scripts Python

### Prueba Masiva Completa
```bash
python test_masivo.py --cps 10 --drivers 8
```

### Lanzar Solo CPs
```bash
python launch_multiple_cps.py --num 10 --central-ip 127.0.0.1 --kafka 127.0.0.1:9092
```

### Lanzar Solo Drivers
```bash
python launch_multiple_drivers.py --num 8 --kafka 127.0.0.1:9092 --cps 10
```

### Dashboard Web
```bash
python web_dashboard.py --kafka 127.0.0.1:9092
```
Accede: http://localhost:8080

---

## 🐳 Docker Compose

### Iniciar Servicios
```batch
docker compose up -d
```
Inicia: Kafka + MySQL + Auto-configuración de topics

### Ver Logs
```batch
docker compose logs -f
```

### Detener Todo
```batch
docker compose down
```

---

## ⚙️ Scripts de Configuración

### Instalar Solo Dependencias
```batch
install_requirements.bat
```

### Crear Topics de Kafka
```batch
setup_kafka_topics.bat
```

### Generar Comandos PC_A
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\generate_commands_A.ps1
```

---

## 🆘 Scripts de Diagnóstico

### Verificar Python
```batch
python --version
python -m pip list
```

### Verificar Docker
```batch
docker --version
docker ps
docker compose ps
```

### Verificar Kafka
```batch
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092
```

### Verificar MySQL
```batch
docker exec mysql mysql -uroot -proot -e "SHOW DATABASES;"
```

---

## 📊 Matriz de Uso

| Escenario | Script a Usar |
|-----------|---------------|
| **Primera vez en nuevo PC** | `setup_environment.bat` |
| **Demo rápida al profesor** | `QUICK_START.bat` |
| **Lanzar PC_A (Central)** | `run_PC_A.bat` |
| **Lanzar PC_B (CPs)** | `run_PC_B.bat` |
| **Solo probar con 5 CPs** | `python test_masivo.py --cps 5 --drivers 3` |
| **Solo dashboard** | `python web_dashboard.py --kafka 127.0.0.1:9092` |
| **Iniciar Kafka+MySQL** | `docker compose up -d` |
| **Crear topics manualmente** | `setup_kafka_topics.bat` |
| **Reinstalar dependencias** | `install_requirements.bat` |

---

## 🔄 Flujo Típico

### Configuración Inicial (Solo Primera Vez)
```
1. setup_environment.bat
2. docker compose up -d
3. (Esperar 30s)
4. setup_kafka_topics.bat (opcional, se crean automáticamente)
```

### Uso Normal (PC_A)
```
1. docker compose up -d  (si no está corriendo)
2. run_PC_A.bat
```

### Uso Normal (PC_B)
```
1. Asegurar que central_ip.txt existe
2. run_PC_B.bat
```

### Demo Completa
```
1. docker compose up -d
2. (Esperar 30s)
3. QUICK_START.bat
4. Abrir http://localhost:8080
```

---

**Elige el script según tu necesidad. Todos instalan dependencias automáticamente. 🚀**


