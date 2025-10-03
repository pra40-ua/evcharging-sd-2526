# EVCharging (Sistemas Distribuidos 25/26)

Alcance: el objetivo es realizar un sistema que simula la gestión de una red de postere recargar (charging point) de vehículos eléctricos

Partiendo de un mapa fiction tendremos una serie de puntos de recarga de vehículos eléctricos en los que los usuarios (conductores) podrán hacer uso.
Nos basaremos en una serie de componentes distribuidos que estarán interconectados.

CENTRAL
Tendremos un cuadro de mandos donde se podrá observar el funcionamiento en timepo real de todo el sistema, incluyendo putnos de recarga, peticiones de suministro y estado del sistema central.
La información a visualizar será: ID del punto de recarga, precio al que tiene el suministro €/Kwh / Estado.
El Estado puede ser:
.Activado (disponible): El CP funciona correctamente y a la espera de solicitud de recarga. Se mostrará con un fondo de color verde.
.Parado(fuera de servicio): El cp está en correcto funcionamiento, pero no puede usarse deliberadamente por orden de la central. Color Naranja y con la leyenda "Out of Order"
.Suministrando: El PR funciona correctamente, y está suministrando energía a un vehículo. Color verde y los siguientes datos: Consumo en KW en tiempo real, importe en € en tiempo real, id del conductor al que se está suministrando.
.Averiado: EL PR está conectado al sistema central, pero tiene una avería y no se puede usar. Color rojo
.Desconectado: El PR no está conectado al sistema central (por cualquier motivo). Color gris.

CONDUCTORES
los usuarios tendrán una aplicación que permita recargar su vehiculo en un punto determinado. Dicha app enviará a la central la petición de un servicio y esta responderá autorizándolo.

PUNTOS DE RECARGA
Los estados en los que puede estar son los expresados anteriormente.
Perminten las siguientes funcionalidades:
.Registrarse en la central: Enviarán su id y ubicación a la central.
.Activarse o pararse
.Suministrar: Dos formas: Manualmente mediante una opción en el propio punto; a través de una petición proviniente de la aplicación del conductor (via central)
Además los PR tienen un módulo independiente que permite monitorizar localmente el hardware y software del local.

MECANICA DE LA SOLUCIÓN
Central permanecerá en ejecución sin límite de tiempo sin apagarse nunca. Entonces pasará la siguiente secuencia:
1- Ante cualquier ejecución o reinicio, central comprobará (en su BD) si ya tiene puntos de recarga disponibles registrados y los mostrará en el panel de monitorización y control en su estado. Importante: hasta que un PR no conecte con central, esta no podrá conocer el estado real del punto. En ese caso, lo mostrará como desconectado.

2- Central siempre estará a la espera de: Recibir peticiones de registro y alta de un nuevo punto de recarga; Recibir peticiones de autorización de un suministro.

....
...
..



Comando Central:  python EV_Central.py --port 5000 --kafka "localhost:9092" --db "mysql://user:pass@host/db"

Comando monitor: python EV_CP_M.py --engine_ip 127.0.0.1 --engine_port 5001 --central_ip 127.0.0.1 --central_port 5000 --cp_id CP001
