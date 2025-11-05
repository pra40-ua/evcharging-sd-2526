# ============================================================
# SCRIPT COMPLETO PC_B - Sistema de Punto de Carga
# ============================================================
# Este script unificado:
#  1. Verifica conexion con PC_A
#  2. Construye imagenes Docker (si no existen)
#  3. Lanza Engine y Monitor
# ============================================================

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  PC_B - SISTEMA DE PUNTO DE CARGA (CP_001)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================
# [1/5] VERIFICAR CENTRAL_IP.TXT
# ============================================================
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "[1/5] VERIFICANDO ARCHIVO central_ip.txt" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path "central_ip.txt")) {
    Write-Host "[ERROR] No se encuentra central_ip.txt" -ForegroundColor Red
    Write-Host ""
    Write-Host "ACCION REQUERIDA:" -ForegroundColor Yellow
    Write-Host "  1. En PC_A: Ejecuta PC_A_RUN.bat" 
    Write-Host "  2. Copia el archivo central_ip.txt desde PC_A a este directorio"
    Write-Host "  3. Ejecuta este script nuevamente"
    Write-Host ""
    pause
    exit 1
}

$CENTRAL_IP = (Get-Content "central_ip.txt" -First 1).Trim()
Write-Host "[OK] IP del Central leida: $CENTRAL_IP" -ForegroundColor Green
Write-Host ""

# ============================================================
# [2/5] VERIFICAR CONEXION CON PC_A
# ============================================================
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "[2/5] VERIFICANDO CONEXION CON PC_A" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host ""

Write-Host "Probando conectividad (PING)..." -NoNewline
$pingResult = Test-Connection -ComputerName $CENTRAL_IP -Count 2 -Quiet
if ($pingResult) {
    Write-Host " [OK]" -ForegroundColor Green
} else {
    Write-Host " [ERROR]" -ForegroundColor Red
    Write-Host ""
    Write-Host "No se puede alcanzar PC_A en $CENTRAL_IP" -ForegroundColor Red
    Write-Host ""
    Write-Host "POSIBLES CAUSAS:" -ForegroundColor Yellow
    Write-Host "  1. PC_A esta apagado"
    Write-Host "  2. PC_A no esta en la misma red"
    Write-Host "  3. La IP en central_ip.txt es incorrecta"
    Write-Host ""
    pause
    exit 1
}

Write-Host "Probando puerto 5000 (EV_Central)..." -NoNewline
try {
    $tcpClient = New-Object System.Net.Sockets.TcpClient
    $connect = $tcpClient.BeginConnect($CENTRAL_IP, 5000, $null, $null)
    $wait = $connect.AsyncWaitHandle.WaitOne(5000, $false)
    
    if ($wait -and $tcpClient.Connected) {
        Write-Host " [OK]" -ForegroundColor Green
        $tcpClient.Close()
    } else {
        Write-Host " [ERROR]" -ForegroundColor Red
        Write-Host ""
        Write-Host "EV_Central NO responde en ${CENTRAL_IP}:5000" -ForegroundColor Red
        Write-Host ""
        Write-Host "ACCIONES EN PC_A:" -ForegroundColor Yellow
        Write-Host "  1. Verifica que EV_Central este ejecutandose"
        Write-Host "  2. Abre PowerShell como ADMINISTRADOR y ejecuta:"
        Write-Host ""
        Write-Host "     New-NetFirewallRule -DisplayName 'Central' -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow" -ForegroundColor Cyan
        Write-Host "     New-NetFirewallRule -DisplayName 'Kafka' -Direction Inbound -LocalPort 9092 -Protocol TCP -Action Allow" -ForegroundColor Cyan
        Write-Host ""
        $tcpClient.Close()
        pause
        exit 1
    }
} catch {
    Write-Host " [ERROR]" -ForegroundColor Red
    Write-Host ""
    Write-Host "No se pudo conectar al puerto 5000" -ForegroundColor Red
    pause
    exit 1
}

Write-Host ""

# ============================================================
# [3/5] VERIFICAR DOCKER
# ============================================================
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "[3/5] VERIFICANDO DOCKER" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host ""

docker --version 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker NO esta instalado" -ForegroundColor Red
    Write-Host ""
    Write-Host "Instala Docker Desktop desde: https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
    pause
    exit 1
}

docker ps 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker NO esta ejecutandose" -ForegroundColor Red
    Write-Host ""
    Write-Host "Inicia Docker Desktop primero" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "[OK] Docker esta funcionando" -ForegroundColor Green
Write-Host ""

# ============================================================
# [4/5] CONSTRUIR IMAGENES DOCKER (SI NO EXISTEN)
# ============================================================
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "[4/5] VERIFICANDO IMAGENES DOCKER" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host ""

$imageEngine = docker images -q ev_engine:local
$imageMonitor = docker images -q ev_monitor:local

$needBuild = $false

if (-not $imageEngine) {
    Write-Host "[!] Imagen ev_engine:local NO existe, se construira..." -ForegroundColor Yellow
    $needBuild = $true
}

if (-not $imageMonitor) {
    Write-Host "[!] Imagen ev_monitor:local NO existe, se construira..." -ForegroundColor Yellow
    $needBuild = $true
}

if ($needBuild) {
    Write-Host ""
    Write-Host "Construyendo imagenes Docker..." -ForegroundColor Cyan
    Write-Host "(Esto puede tardar 1-2 minutos la primera vez)" -ForegroundColor Yellow
    Write-Host ""
    
    if (-not $imageEngine) {
        Write-Host "Construyendo ev_engine:local..." -ForegroundColor Cyan
        docker build -t ev_engine:local -f ev_cp_engine/Dockerfile .
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] Fallo al construir ev_engine:local" -ForegroundColor Red
            pause
            exit 1
        }
        Write-Host "[OK] ev_engine:local construido" -ForegroundColor Green
    }
    
    if (-not $imageMonitor) {
        Write-Host "Construyendo ev_monitor:local..." -ForegroundColor Cyan
        docker build -t ev_monitor:local -f ev_cp_monitor/Dockerfile .
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] Fallo al construir ev_monitor:local" -ForegroundColor Red
            pause
            exit 1
        }
        Write-Host "[OK] ev_monitor:local construido" -ForegroundColor Green
    }
    
    Write-Host ""
} else {
    Write-Host "[OK] Todas las imagenes ya existen" -ForegroundColor Green
    Write-Host ""
}

# ============================================================
# [5/5] LANZAR SISTEMA
# ============================================================
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "[5/5] INICIANDO SISTEMA DE PUNTO DE CARGA" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host ""
Write-Host "CONFIGURACION:" -ForegroundColor Yellow
Write-Host "  - CP ID:       CP_001"
Write-Host "  - Central:     ${CENTRAL_IP}:5000"
Write-Host "  - Kafka:       ${CENTRAL_IP}:9092"
Write-Host "  - Engine:      localhost:5001"
Write-Host "  - Modo Red:    host (acceso directo a red del PC)"
Write-Host ""

# Detener contenedores previos si existen
Write-Host "Limpiando contenedores previos..." -ForegroundColor Cyan
docker stop engine 2>$null | Out-Null
docker stop monitor 2>$null | Out-Null
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  INICIANDO ENGINE (Ventana 1)" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Presiona cualquier tecla para abrir el Engine en nueva ventana..." -ForegroundColor Yellow
pause

# Lanzar Engine en nueva ventana con network host
$engineCmd = @"
Write-Host 'Iniciando Engine (CP_001)...' -ForegroundColor Cyan
Write-Host ''
Write-Host 'Configuracion:' -ForegroundColor Yellow
Write-Host '  - Puerto: 5001'
Write-Host '  - Kafka:  ${CENTRAL_IP}:9092'
Write-Host '  - CP ID:  CP_001'
Write-Host ''
Write-Host 'El Engine esta iniciando...' -ForegroundColor Green
Write-Host 'Presiona Ctrl+C para detener' -ForegroundColor Yellow
Write-Host ''
docker run --rm --network host --name engine ``
  -e ENGINE_PORT=5001 -e CP_ID=CP_001 ``
  -e KAFKA_SERVER=`"${CENTRAL_IP}:9092`" ``
  ev_engine:local
Write-Host ''
Write-Host 'Engine detenido. Presiona cualquier tecla para cerrar esta ventana...' -ForegroundColor Yellow
pause
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $engineCmd

Write-Host "[OK] Engine iniciado en nueva ventana" -ForegroundColor Green
Write-Host ""
Write-Host "Esperando 5 segundos a que el Engine este listo..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  INICIANDO MONITOR (Ventana 2)" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Presiona cualquier tecla para abrir el Monitor en nueva ventana..." -ForegroundColor Yellow
pause

# Lanzar Monitor en nueva ventana con network host
$monitorCmd = @"
Write-Host 'Iniciando Monitor (CP_001)...' -ForegroundColor Cyan
Write-Host ''
Write-Host 'Configuracion:' -ForegroundColor Yellow
Write-Host '  - Central: ${CENTRAL_IP}:5000'
Write-Host '  - Engine:  localhost:5001'
Write-Host '  - CP ID:   CP_001'
Write-Host ''
Write-Host 'El Monitor esta iniciando y registrandose con el Central...' -ForegroundColor Green
Write-Host 'Presiona Ctrl+C para detener' -ForegroundColor Yellow
Write-Host ''
docker run --rm --network host --name monitor ``
  -e CP_ID=CP_001 ``
  -e CENTRAL_IP=${CENTRAL_IP} -e CENTRAL_PORT=5000 ``
  -e ENGINE_IP=localhost -e ENGINE_PORT=5001 ``
  ev_monitor:local
Write-Host ''
Write-Host 'Monitor detenido. Presiona cualquier tecla para cerrar esta ventana...' -ForegroundColor Yellow
pause
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $monitorCmd

Write-Host "[OK] Monitor iniciado en nueva ventana" -ForegroundColor Green
Write-Host ""

# ============================================================
# RESUMEN FINAL
# ============================================================
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  SISTEMA PC_B INICIADO CORRECTAMENTE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Componentes activos:" -ForegroundColor Yellow
Write-Host "  [X] Engine  (CP_001) - Puerto 5001"
Write-Host "  [X] Monitor (CP_001) - Conectado a Central en ${CENTRAL_IP}:5000"
Write-Host ""
Write-Host "Ventanas abiertas:" -ForegroundColor Yellow
Write-Host "  - Engine  (logs en tiempo real)"
Write-Host "  - Monitor (logs en tiempo real)"
Write-Host ""
Write-Host "IMPORTANTE:" -ForegroundColor Cyan
Write-Host "  - El Monitor debe mostrar 'REGISTRO EXITOSO' en su ventana"
Write-Host "  - Si ves errores de conexion, verifica el firewall de PC_A"
Write-Host "  - Para detener: Presiona Ctrl+C en cada ventana"
Write-Host ""
Write-Host "Dashboard Web (en PC_A):" -ForegroundColor Yellow
Write-Host "  - URL: http://${CENTRAL_IP}:8080"
Write-Host ""
Write-Host "Para detener todo el sistema:" -ForegroundColor Yellow
Write-Host "  1. Presiona Ctrl+C en cada ventana (Engine y Monitor)"
Write-Host "  2. O ejecuta: docker stop engine monitor"
Write-Host ""
Write-Host "Presiona cualquier tecla para cerrar esta ventana..." -ForegroundColor Green
Write-Host "(Los componentes seguiran ejecutandose en sus ventanas)" -ForegroundColor Yellow
Write-Host ""
pause

exit 0


