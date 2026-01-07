FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY EV_Registry.py .
COPY certificados ./certificados

# Exponer puerto
EXPOSE 6000

# Ejecutar
CMD ["python", "EV_Registry.py", "--db-host", "mysql", "--db-port", "3306", "--db-user", "root", "--db-password", "root", "--db-name", "evcharging", "--port", "6000", "--ssl", "--ssl-cert", "certificados/registry_cert.pem", "--ssl-key", "certificados/registry_key.pem"]

