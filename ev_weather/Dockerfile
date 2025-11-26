FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY EV_W.py .

# Ejecutar
CMD ["python", "EV_W.py", "--api-key", "${OPENWEATHER_API_KEY}", "--central-url", "http://ev_central:5000/api"]

