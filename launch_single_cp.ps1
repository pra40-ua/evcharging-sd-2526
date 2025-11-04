# ============================================================
# Script PowerShell para lanzar un CP individual
# Uso: ./launch_single_cp.ps1 -CpId "CP_001" -EnginePort 5001 -CentralIp "192.168.1.43"
# ============================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$CpId,
    
    [Parameter(Mandatory=$true)]
    [int]$EnginePort,
    
    [Parameter(Mandatory=$true)]
    [string]$CentralIp,
    
    [int]$CentralPort = 5000
)

$KafkaServer = "${CentralIp}:9092"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Lanzando Charging Point: $CpId" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Engine Port: $EnginePort" -ForegroundColor White
Write-Host "  Central IP:  $CentralIp" -ForegroundColor White
Write-Host "  Kafka:       $KafkaServer" -ForegroundColor White
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Lanzar Engine en una ventana separada
Write-Host "[1/2] Lanzando Engine..." -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command",
    "Write-Host '================================================================' -ForegroundColor Cyan; " +
    "Write-Host '  ENGINE - $CpId (Puerto $EnginePort)' -ForegroundColor Yellow; " +
    "Write-Host '================================================================' -ForegroundColor Cyan; " +
    "Write-Host ''; " +
    "docker run --rm --name engine_$CpId -p ${EnginePort}:${EnginePort} " +
    "-e ENGINE_PORT=$EnginePort " +
    "-e CP_ID=$CpId " +
    "-e KAFKA_SERVER='$KafkaServer' " +
    "ev_engine:local"
)

# Esperar a que el Engine esté listo
Write-Host "Esperando a que Engine esté listo..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Lanzar Monitor en una ventana separada
Write-Host "[2/2] Lanzando Monitor..." -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command",
    "Write-Host '================================================================' -ForegroundColor Cyan; " +
    "Write-Host '  MONITOR - $CpId' -ForegroundColor Green; " +
    "Write-Host '================================================================' -ForegroundColor Cyan; " +
    "Write-Host ''; " +
    "docker run --rm --name monitor_$CpId " +
    "-e CP_ID=$CpId " +
    "-e CENTRAL_IP=$CentralIp " +
    "-e CENTRAL_PORT=$CentralPort " +
    "-e ENGINE_IP=host.docker.internal " +
    "-e ENGINE_PORT=$EnginePort " +
    "ev_monitor:local"
)

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  $CpId lanzado exitosamente!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

