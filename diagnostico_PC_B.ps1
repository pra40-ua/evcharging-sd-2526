# ============================================================
# SCRIPT DE DIAGNOSTICO DE CONEXION PC_B -> PC_A
# ============================================================

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  DIAGNOSTICO DE CONEXION PC_B -> PC_A" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Leer la IP del Central desde central_ip.txt
if (Test-Path "central_ip.txt") {
    $CENTRAL_IP = (Get-Content "central_ip.txt" -First 1).Trim()
    Write-Host "[OK] IP del Central leida: $CENTRAL_IP" -ForegroundColor Green
} else {
    Write-Host "[ERROR] No se encuentra central_ip.txt" -ForegroundColor Red
    Write-Host "        Copia este archivo desde PC_A primero." -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host ""
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "[1/5] VERIFICANDO CONECTIVIDAD DE RED (PING)" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host ""

$pingResult = Test-Connection -ComputerName $CENTRAL_IP -Count 2 -Quiet
if ($pingResult) {
    Write-Host "[OK] PC_A ($CENTRAL_IP) responde a PING" -ForegroundColor Green
} else {
    Write-Host "[ERROR] PC_A ($CENTRAL_IP) NO responde a PING" -ForegroundColor Red
    Write-Host ""
    Write-Host "POSIBLES CAUSAS:" -ForegroundColor Yellow
    Write-Host "  1. PC_A esta apagado o no conectado a la red"
    Write-Host "  2. La IP en central_ip.txt es incorrecta"
    Write-Host "  3. El firewall de PC_A bloquea ICMP (ping)"
    Write-Host ""
    Write-Host "ACCION: Verifica que PC_A este encendido y en la misma red" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host ""
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "[2/5] VERIFICANDO PUERTO 5000 (EV_CENTRAL)" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host ""

try {
    $tcpClient = New-Object System.Net.Sockets.TcpClient
    $connect = $tcpClient.BeginConnect($CENTRAL_IP, 5000, $null, $null)
    $wait = $connect.AsyncWaitHandle.WaitOne(3000, $false)
    
    if ($wait -and $tcpClient.Connected) {
        Write-Host "[OK] Puerto 5000 (EV_Central) esta ABIERTO y aceptando conexiones" -ForegroundColor Green
        $tcpClient.Close()
    } else {
        Write-Host "[ERROR] Puerto 5000 (EV_Central) NO responde" -ForegroundColor Red
        Write-Host ""
        Write-Host "POSIBLES CAUSAS:" -ForegroundColor Yellow
        Write-Host "  1. EV_Central NO esta ejecutandose en PC_A"
        Write-Host "  2. El firewall de PC_A bloquea el puerto 5000"
        Write-Host ""
        Write-Host "ACCION EN PC_A:" -ForegroundColor Yellow
        Write-Host "  1. Verifica que EV_Central este ejecutandose (ventana abierta)"
        Write-Host "  2. Ejecuta como Administrador:" -ForegroundColor Cyan
        Write-Host "     New-NetFirewallRule -DisplayName 'Central' -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow"
        Write-Host ""
        $tcpClient.Close()
        pause
        exit 1
    }
} catch {
    Write-Host "[ERROR] No se pudo conectar al puerto 5000" -ForegroundColor Red
    Write-Host "Error: $_" -ForegroundColor Red
    pause
    exit 1
}

Write-Host ""
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "[3/5] VERIFICANDO PUERTO 9092 (KAFKA)" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host ""

try {
    $tcpClient = New-Object System.Net.Sockets.TcpClient
    $connect = $tcpClient.BeginConnect($CENTRAL_IP, 9092, $null, $null)
    $wait = $connect.AsyncWaitHandle.WaitOne(3000, $false)
    
    if ($wait -and $tcpClient.Connected) {
        Write-Host "[OK] Puerto 9092 (Kafka) esta ABIERTO" -ForegroundColor Green
        $tcpClient.Close()
    } else {
        Write-Host "[ADVERTENCIA] Puerto 9092 (Kafka) NO responde" -ForegroundColor Yellow
        Write-Host "              El sistema puede no funcionar correctamente" -ForegroundColor Yellow
        $tcpClient.Close()
    }
} catch {
    Write-Host "[ADVERTENCIA] No se pudo conectar al puerto 9092 (Kafka)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "[4/5] VERIFICANDO DOCKER EN PC_B" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host ""

docker --version 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Docker esta instalado" -ForegroundColor Green
    docker ps 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Docker daemon esta ejecutandose" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Docker NO esta ejecutandose" -ForegroundColor Red
        Write-Host "        Inicia Docker Desktop primero" -ForegroundColor Yellow
        pause
        exit 1
    }
} else {
    Write-Host "[ERROR] Docker NO esta instalado" -ForegroundColor Red
    pause
    exit 1
}

Write-Host ""
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "[5/5] VERIFICANDO IMAGENES DOCKER" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host ""

$imageEngine = docker images -q ev_engine:local
$imageMonitor = docker images -q ev_monitor:local

if ($imageEngine) {
    Write-Host "[OK] Imagen ev_engine:local existe" -ForegroundColor Green
} else {
    Write-Host "[ADVERTENCIA] Imagen ev_engine:local NO existe" -ForegroundColor Yellow
    Write-Host "              Necesitas ejecutar commands_PC_B_build_engine.ps1 primero" -ForegroundColor Yellow
}

if ($imageMonitor) {
    Write-Host "[OK] Imagen ev_monitor:local existe" -ForegroundColor Green
} else {
    Write-Host "[ADVERTENCIA] Imagen ev_monitor:local NO existe" -ForegroundColor Yellow
    Write-Host "              Necesitas ejecutar commands_PC_B_build_engine.ps1 primero" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  DIAGNOSTICO COMPLETADO" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

if ($pingResult -and $wait -and $tcpClient.Connected) {
    Write-Host "[RESULTADO] La conexion PC_B -> PC_A esta FUNCIONANDO" -ForegroundColor Green
    Write-Host ""
    Write-Host "El problema puede estar en la configuracion de red del contenedor." -ForegroundColor Yellow
    Write-Host "Intenta ejecutar el monitor con '--network host':" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "docker run --rm --network host --name monitor ``" -ForegroundColor Cyan
    Write-Host "  -e CP_ID=CP_001 ``" -ForegroundColor Cyan
    Write-Host "  -e CENTRAL_IP=$CENTRAL_IP -e CENTRAL_PORT=5000 ``" -ForegroundColor Cyan
    Write-Host "  -e ENGINE_IP=localhost -e ENGINE_PORT=5001 ``" -ForegroundColor Cyan
    Write-Host "  ev_monitor:local" -ForegroundColor Cyan
    Write-Host ""
} else {
    Write-Host "[RESULTADO] HAY PROBLEMAS DE CONEXION PC_B -> PC_A" -ForegroundColor Red
    Write-Host ""
    Write-Host "ACCIONES REQUERIDAS EN PC_A:" -ForegroundColor Yellow
    Write-Host "  1. Verifica que EV_Central este ejecutandose"
    Write-Host "  2. Abre el firewall (como Administrador):"
    Write-Host "     New-NetFirewallRule -DisplayName 'Central' -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow"
    Write-Host "     New-NetFirewallRule -DisplayName 'Kafka' -Direction Inbound -LocalPort 9092 -Protocol TCP -Action Allow"
    Write-Host ""
}

Write-Host ""
pause

