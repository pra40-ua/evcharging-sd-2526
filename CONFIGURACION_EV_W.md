# Guía de Configuración de EV_W (Weather Control Office)

## Paso 1: Obtener API Key de OpenWeather

1. Ve a https://openweathermap.org/api
2. Crea una cuenta gratuita (si no tienes una)
3. Una vez registrado, ve a tu panel de control
4. En la sección "API keys", copia tu API key
5. La cuenta gratuita permite 60 llamadas por minuto (suficiente para nuestro uso)

## Paso 2: Crear archivo de configuración

En el ordenador **PC_B**, crea un archivo llamado `OPENWEATHER_API_KEY.txt` en la raíz del proyecto (mismo directorio que `PC_B_RUN.bat`).

El archivo debe contener **solo** tu API key, sin espacios ni saltos de línea:

```
tu_api_key_aqui
```

**Ejemplo:**
```
a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```

## Paso 3: Ejecutar PC_B_RUN.bat

Cuando ejecutes `PC_B_RUN.bat`, EV_W se iniciará automáticamente si encuentra el archivo `OPENWEATHER_API_KEY.txt`.

## Paso 4: Configurar localizaciones de CPs

Una vez que EV_W esté ejecutándose, verás un menú interactivo en la ventana de EV_W:

```
======================================================================
  EV_W - Weather Control Office
======================================================================
  [1] Añadir localización de CP
  [2] Eliminar localización de CP
  [3] Listar localizaciones
  [4] Consultar temperatura de una localización
  [5] Estado de alertas
  [h] Ayuda
  [q] Salir
======================================================================
```

### Añadir una localización:

1. Selecciona la opción `[1]`
2. Ingresa el ID del CP (ej: `CP_001`, `CP_002`, etc.)
3. Ingresa la localización en formato: `Ciudad,País` (ej: `Madrid,ES`, `Barcelona,ES`, `London,GB`)

**Ejemplos de localizaciones válidas:**
- `Madrid,ES` (Madrid, España)
- `Barcelona,ES` (Barcelona, España)
- `London,GB` (Londres, Reino Unido)
- `Paris,FR` (París, Francia)
- `New York,US` (Nueva York, Estados Unidos)

### Verificar configuración:

- Usa la opción `[3]` para listar todas las localizaciones configuradas
- Usa la opción `[4]` para probar una localización antes de añadirla

## Paso 5: Funcionamiento automático

Una vez configuradas las localizaciones:

- EV_W consultará la temperatura de cada CP cada 4 segundos
- Si la temperatura baja de 0°C, enviará una alerta a EV_Central
- EV_Central pondrá el CP "fuera de servicio"
- Cuando la temperatura vuelva a subir por encima de 0°C, EV_W notificará a EV_Central para restaurar el servicio

## Notas importantes:

1. **Formato de localización**: Debe ser exactamente `Ciudad,País` con la coma como separador
2. **Código de país**: Usa códigos ISO de 2 letras (ES, GB, FR, US, etc.)
3. **ID de CP**: Debe coincidir con el ID que usas en los Monitores (ej: `CP_001`, `CP_002`)
4. **Sin reinicio necesario**: Puedes añadir/eliminar localizaciones en cualquier momento sin reiniciar EV_W

## Solución de problemas:

- **"No se encontró OPENWEATHER_API_KEY.txt"**: Crea el archivo en la raíz del proyecto
- **"API Key inválida"**: Verifica que la API key sea correcta y que no haya espacios
- **"Ciudad no encontrada"**: Verifica el formato `Ciudad,País` y el código de país
- **"No hay localizaciones configuradas"**: Añade al menos una localización usando la opción `[1]`

