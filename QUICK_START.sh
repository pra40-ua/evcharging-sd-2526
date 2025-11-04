#!/bin/bash
# Script rápido para demostración al profesor
# Lanza 10 CPs y 8 Drivers con dashboard web

echo "========================================"
echo "   DEMO RÁPIDA - SISTEMA EV CHARGING"
echo "========================================"
echo ""
echo "Este script lanzará:"
echo "  - 1 Central (servidor principal)"
echo "  - 1 Dashboard Web (http://localhost:8080)"
echo "  - 10 Puntos de Recarga"
echo "  - 8 Drivers (clientes)"
echo ""
echo "Asegúrate de tener:"
echo "  [X] Kafka corriendo en localhost:9092"
echo "  [X] MySQL corriendo en localhost:3306"
echo "  [X] Base de datos 'evcharging' creada"
echo ""
read -p "Presiona Enter para continuar..."

# Instalar dependencias si es necesario
echo ""
echo "[1/3] Verificando dependencias..."
pip install -r requirements.txt > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "ERROR: No se pudieron instalar las dependencias"
    exit 1
fi

echo "[2/3] Iniciando sistema..."
python3 test_masivo.py --cps 10 --drivers 8 --kafka 127.0.0.1:9092

echo ""
echo "[3/3] Sistema detenido."


