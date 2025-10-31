# Arrancar Kafka (en el host, accesible desde contenedores vÃ­a host.docker.internal)
docker compose down
docker compose up -d

# Crear red y volumen para MySQL
docker network create evnet
docker volume create ev_mysql_data

# Arrancar MySQL (primer arranque ejecuta db/init.sql)
docker run -d --name mysql --network evnet -p 3306:3306 `
  -e MYSQL_ROOT_PASSWORD=root -e MYSQL_DATABASE=evcharging `
  -v ev_mysql_data:/var/lib/mysql `
  -v ${PWD}\db\init.sql:/docker-entrypoint-initdb.d/01_schema.sql `
  mysql:8

# Construir imagen de la central (si no existe)
docker build -t ev_central:local -f ev_central/Dockerfile .

# Arrancar Central (usa hostname mysql en la misma red y la IP real para Kafka)
docker run --rm -it --name central --network evnet -p 5000:5000 `
  -e CENTRAL_PORT=5000 `
  -e KAFKA_BROKER="172.21.42.5:9092" `
  -e DB_URL="mysql:3306:root:root:evcharging" `
  ev_central:local

# Nota: Kafka debe estar corriendo en el host (puerto 9092) accesible por IP
# Abre puertos 5000 y 9092 en el firewall de este PC.
# IP Central detectada (PC_A): 172.21.42.5
# Se ha guardado tambiÃ©n en central_ip.txt para facilitar la configuraciÃ³n de PC_B.
