# Cómo Usar los Logs de PC_B_RUN.bat

## 📋 Ubicación de los Logs

Cada vez que ejecutes `PC_B_RUN.bat`, se creará automáticamente un archivo de log en:

```
logs\PC_B_RUN_YYYYMMDD_HHMMSS.log
```

Por ejemplo: `logs\PC_B_RUN_20250511_143025.log`

## 🔍 Información Registrada

El log contiene información detallada sobre:

1. **Inicio del script**
   - Directorio de ejecución
   - Verificación de Docker
   - Detección de IP de la Central

2. **Selección de modo**
   - Qué opción seleccionó el usuario (1, 2 o 3)

3. **Construcción de imágenes Docker**
   - Comandos ejecutados
   - Salida completa de `docker build`
   - Códigos de error si falló

4. **Lanzamiento de contenedores**
   - Cada CP o Driver que se intenta lanzar
   - Parámetros calculados (puertos, IDs, etc.)
   - Resultado de los comandos `start`

5. **Variables de entorno**
   - CENTRAL_IP
   - KAFKA_SERVER
   - BASE_PORT
   - Etc.

## 📖 Cómo Leer el Log

### Formato de Líneas

Cada línea del log tiene el formato:
```
[DD/MM/YYYY HH:MM:SS,MS] MENSAJE
```

### Buscar Errores

Para encontrar errores rápidamente, busca las palabras:
- `ERROR:`
- `Fallo`
- `Codigo de salida docker build:` seguido de un número distinto de 0

### Verificar Construcción de Imágenes

Busca estas líneas:
```
Ejecutando: docker build -t ev_engine:local -f ev_cp_engine/Dockerfile .
Codigo de salida docker build ev_engine: 0
```

Si el código de salida es **0** = éxito
Si el código de salida es **distinto de 0** = error

### Verificar Lanzamiento de Contenedores

Busca estas líneas:
```
Ejecutando START para Engine CP_001...
Comando START para Engine CP_001 ejecutado (errorlevel: 0)
```

## 🐛 Qué Hacer si Algo Falla

1. **Ejecuta el script** `PC_B_RUN.bat`
2. **Cuando falle**, anota el error que aparece en pantalla
3. **Ve a la carpeta** `logs\`
4. **Abre el archivo de log más reciente**
5. **Envía el contenido del log** para diagnóstico

## 📊 Ejemplo de Log Exitoso

```
[05/11/2025 14:30:25,12] Script iniciado desde: C:\Users\...\evcharging-sd-2526
[05/11/2025 14:30:25,15] Verificando disponibilidad de Docker...
[05/11/2025 14:30:26,20] Docker esta disponible
[05/11/2025 14:30:26,22] Detectando IP de la Central...
[05/11/2025 14:30:26,25] Central IP detectada desde archivo: 192.168.1.43
[05/11/2025 14:30:30,10] Usuario selecciono opcion: 3
[05/11/2025 14:30:30,12] Iniciando modo CLASICO
[05/11/2025 14:30:30,15] Construyendo imagenes Docker para modo CLASICO...
[05/11/2025 14:30:30,18] Ejecutando: docker build -t ev_engine:local -f ev_cp_engine/Dockerfile .
[05/11/2025 14:30:45,22] Codigo de salida docker build ev_engine: 0
[05/11/2025 14:30:45,25] Ejecutando: docker build -t ev_monitor:local -f ev_cp_monitor/Dockerfile .
[05/11/2025 14:31:00,30] Codigo de salida docker build ev_monitor: 0
[... etc ...]
```

## 📊 Ejemplo de Log con Error

```
[05/11/2025 14:30:25,12] Script iniciado desde: C:\Users\...\evcharging-sd-2526
[05/11/2025 14:30:25,15] Verificando disponibilidad de Docker...
[05/11/2025 14:30:26,20] ERROR: Docker no esta disponible
```

En este caso, el problema es que Docker no está instalado o no está corriendo.

## 💡 Consejos

- **No borres los logs antiguos** - pueden ser útiles para comparar
- **Si algo no funciona**, compara el log de una ejecución que funcionó con una que falló
- **Los logs de Docker build** contienen toda la salida del proceso de construcción
- **Las variables calculadas** (puertos, IDs) están todas registradas para verificar que sean correctas

