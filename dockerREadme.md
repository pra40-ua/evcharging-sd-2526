Arranca kafka
    docker compose down
    docker compose up -d


🔮​BASE DE DATOS
Arranca MySQL con volumen y el script (solo se ejecuta en el primer arranque del datadir):

  docker network create evnet
docker volume create ev_mysql_data

docker run -d --name mysql --network evnet -p 3306:3306 `
  -e MYSQL_ROOT_PASSWORD=root -e MYSQL_DATABASE=evcharging `
  -v ev_mysql_data:/var/lib/mysql `
  -v ${PWD}\db\init.sql:/docker-entrypoint-initdb.d/01_schema.sql `
  mysql:8
**********************************************
🔮​Lanza la Central usando el hostname mysql (misma red)
docker run --rm --name central --network evnet -p 5000:5000 `
  -e CENTRAL_PORT=5000 `
  -e KAFKA_BROKER=172.27.237.31:9092 `
  -e DB_URL="mysql:3306:root:root:evcharging" `
  ev_central:local
  ********************************************
🔮​Nota: si ya levantaste MySQL antes con el mismo volumen, el script no se ejecutará. En ese caso, borra el contenedor y el volumen y vuelve a crear:
docker rm -f mysql
docker volume rm ev_mysql_data
*******************************************************

**** Ejecutar Engine y Monitor (EN B)
# Imagen Engine y Monitor
docker build --no-cache -t ev_engine:local  -f ev_cp_engine/Dockerfile .
docker build --no-cache

# Imagen driver
docker build -t ev_driver:local -f ev_driver/Dockerfile .

# Arrancar Engine
docker run --rm -p 5001:5001 --name engine -e ENGINE_PORT=5001 -e CP_ID=CP_001 -e KAFKA_SERVER=172.27.237.31:9092 ev_engine:local

# Arrancar Monitor
docker run --rm --name monitor -e CP_ID=CP_001 -e CENTRAL_IP=172.27.237.31 -e CENTRAL_PORT=5000 -e ENGINE_IP=10.191.221.77 -e ENGINE_PORT=5001 ev_monitor:local

# Arrancar Driver
docker run --rm --name driver -e KAFKA_BROKER=10.191.221.61:9092 -e DRIVER_ID=DRIVER_456 -e CP_ID=CP_001 -e MAT=ABC-1234 -e KW=25.0 -e LISTEN=true ev_driver:local

construir la imagen
    docker build -t ev_central:local -f ev_central/Dockerfile .
    docker build -t ev_engine:local -f ev_cp_engine/Dockerfile .
    docker build -t ev_monitor:local -f ev_cp_monitor/Dockerfile .
    docker build -t ev_driver:local -f ev_driver/Dockerfile .

Ejecuta Central en PC_A

  docker run --rm -p 5000:5000 --name central ^
    -e CENTRAL_PORT=5000 ^
    -e KAFKA_BROKER=172.27.237.31:9092 ^
    ev_central:local

    PC_B:
    Ejecutar engine:
       docker run --rm -p 5001:5001 --name engine ^
      -e ENGINE_PORT=5001 -e CP_ID=CP_001 ^
      -e KAFKA_SERVER=172.27.237.31:9092 ^
      ev_engine:local

    Ejecutar el monitor:
      docker run --rm --name monitor ^
      -e CP_ID=CP_001 ^
      -e CENTRAL_IP=172.27.237.31 -e CENTRAL_PORT=5000 ^
      -e ENGINE_IP=<IP_PC_B> -e ENGINE_PORT=5001 ^
      ev_monitor:local

    Ejecutar driver
      docker run --rm --name driver ^
      -e KAFKA_BROKER=<IP_P172.27.141.245C_A>:9092 ^
      -e DRIVER_ID=DRIVER_456 -e CP_ID=CP_001 -e KW=25.0 ^
      ev_driver:local

  Notas:
  Abre puertos 5000 y 5001 en el firewall, y 9092 en PC_A.