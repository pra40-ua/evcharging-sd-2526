param(
    [string]$CentralIp = ''
)

# Genera commands_PC_B.txt con los comandos para PC_B (Engine, Monitor y Driver)

# Si no se pasa -CentralIp, intentar leerlo de central_ip.txt (generado en PC_A)
if ([string]::IsNullOrWhiteSpace($CentralIp)) {
    $projectRoot = Split-Path $PSScriptRoot -Parent
    $centralIpFile = Join-Path $projectRoot 'central_ip.txt'
    if (Test-Path $centralIpFile) {
        try {
            $CentralIp = (Get-Content -Path $centralIpFile -Raw).Trim()
            if (-not [string]::IsNullOrWhiteSpace($CentralIp)) {
                Write-Host "Leído CENTRAL_IP desde central_ip.txt: $CentralIp" -ForegroundColor Green
            }
        } catch {
            Write-Warning "No se pudo leer central_ip.txt: $_"
        }
    }

    if ([string]::IsNullOrWhiteSpace($CentralIp)) {
        Write-Host 'Uso: .\generate_commands_B.ps1 -CentralIp <IP_DE_PC_A>' -ForegroundColor Yellow
        Write-Host 'No se proporcionó CentralIp y no se encontró central_ip.txt. El fichero contendrá marcadores <CENTRAL_IP> que deberás reemplazar.' -ForegroundColor Yellow
    }
}

# Detectar IPv4 local (no loopback/APIPA)
$localIp = (
    Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254*' } |
        Sort-Object -Property PrefixLength |
        Select-Object -First 1 -ExpandProperty IPAddress
)
if (-not $localIp) {
    Write-Error 'No se pudo detectar la IP IPv4 local.'
    exit 1
}

$centralIpForText = if ([string]::IsNullOrWhiteSpace($CentralIp)) { '<CENTRAL_IP>' } else { $CentralIp }
$sameHost = ($centralIpForText -ne '<CENTRAL_IP>') -and ($CentralIp -eq $localIp)

# Ruta de salida (coloca el txt en la raíz del proyecto evcharging-sd-2526)
$projectRoot = Split-Path $PSScriptRoot -Parent
$outPath = Join-Path $projectRoot 'commands_PC_B.txt'

$lines = @()
$lines += '# Construir imágenes (si no existen)'
$lines += 'docker build -t ev_engine:local -f ev_cp_engine/Dockerfile .'
$lines += 'docker build -t ev_monitor:local -f ev_cp_monitor/Dockerfile .'
$lines += 'docker build -t ev_driver:local -f ev_driver/Dockerfile .'
$lines += ''
$lines += '# Arrancar Engine'
if ($sameHost) {
    $lines += 'docker run --rm --network evnet -p 5001:5001 --name engine `'
    $lines += '  -e ENGINE_PORT=5001 -e CP_ID=CP_001 `'
    $lines += '  -e KAFKA_SERVER="host.docker.internal:9092" `'
    $lines += '  ev_engine:local'
} else {
    $lines += 'docker run --rm -p 5001:5001 --name engine `'
    $lines += '  -e ENGINE_PORT=5001 -e CP_ID=CP_001 `'
    $kafkaServerLine = '  -e KAFKA_SERVER="' + $centralIpForText + ':9092" `'
    $lines += $kafkaServerLine
    $lines += '  ev_engine:local'
}
$lines += ''
$lines += '# Arrancar Monitor'
if ($sameHost) {
    $lines += 'docker run --rm --network evnet --name monitor `'
    $lines += '  -e CP_ID=CP_001 `'
    $lines += '  -e CENTRAL_IP=central -e CENTRAL_PORT=5000 `'
    $lines += '  -e ENGINE_IP=engine -e ENGINE_PORT=5001 `'
    $lines += '  ev_monitor:local'
} else {
    $lines += 'docker run --rm --name monitor `'
    $lines += '  -e CP_ID=CP_001 `'
    $centralIpLine = '  -e CENTRAL_IP=' + $centralIpForText + ' -e CENTRAL_PORT=5000 `'
    $lines += $centralIpLine
    # Usar host.docker.internal para conectar desde contenedor al host (Windows/Mac)
    $lines += '  -e ENGINE_IP=host.docker.internal -e ENGINE_PORT=5001 `'
    $lines += '  ev_monitor:local'
}
$lines += ''
$lines += '# Arrancar Driver'
if ($sameHost) {
    $lines += 'docker run --rm --name driver `'
    $lines += '  -e KAFKA_BROKER="host.docker.internal:9092" `'
    $lines += '  -e DRIVER_ID=DRIVER_456 -e CP_ID=CP_001 -e MAT=ABC-1234 -e KW=1.0 -e LISTEN=true `'
    $lines += '  ev_driver:local'
} else {
    $lines += 'docker run --rm --name driver `'
    $kafkaBrokerLineDriver = '  -e KAFKA_BROKER="' + $centralIpForText + ':9092" `'
    $lines += $kafkaBrokerLineDriver
    $lines += '  -e DRIVER_ID=DRIVER_456 -e CP_ID=CP_001 -e MAT=ABC-1234 -e KW=1.0 -e LISTEN=true `'
    $lines += '  ev_driver:local'
}
$lines += ''
$lines += "# IP local detectada (PC_B): ${localIp}"
$lines += $( if (-not [string]::IsNullOrWhiteSpace($CentralIp)) { "# IP Central usada (PC_A): ${CentralIp}" } else { "# IP Central: <CENTRAL_IP> (reemplazar por la IP de PC_A)" } )
$lines += '# Nota: abre puertos 5001 en este PC y 9092 en PC_A.'

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($outPath, $lines, $utf8NoBom)

Write-Host "Generado: $outPath"
Write-Host "IP local detectada: $localIp"
if (-not [string]::IsNullOrWhiteSpace($CentralIp)) { Write-Host "IP Central usada: $CentralIp" }

# =====================
# Generar PS1 por bloques y un BAT que abre 3 terminales
# =====================

# 1) Bloque build + engine
$buildAndEngine = @()
$buildAndEngine += '# Construir imágenes (si no existen)'
$buildAndEngine += 'docker build -t ev_engine:local -f ev_cp_engine/Dockerfile .'
$buildAndEngine += 'docker build -t ev_monitor:local -f ev_cp_monitor/Dockerfile .'
$buildAndEngine += 'docker build -t ev_driver:local -f ev_driver/Dockerfile .'
$buildAndEngine += ''
$buildAndEngine += '# Arrancar Engine'
if ($sameHost) {
    $buildAndEngine += 'docker run --rm --network evnet -p 5001:5001 --name engine `'
    $buildAndEngine += '  -e ENGINE_PORT=5001 -e CP_ID=CP_001 `'
    $buildAndEngine += '  -e KAFKA_SERVER="host.docker.internal:9092" `'
    $buildAndEngine += '  ev_engine:local'
} else {
    $buildAndEngine += 'docker run --rm -p 5001:5001 --name engine `'
    $buildAndEngine += '  -e ENGINE_PORT=5001 -e CP_ID=CP_001 `'
    $buildAndEngine += ('  -e KAFKA_SERVER="' + $centralIpForText + ':9092" `')
    $buildAndEngine += '  ev_engine:local'
}

# 2) Bloque monitor
$monitorLines = @()
$monitorLines += '# Arrancar Monitor'
if ($sameHost) {
    $monitorLines += 'docker run --rm --network evnet --name monitor `'
    $monitorLines += '  -e CP_ID=CP_001 `'
    $monitorLines += '  -e CENTRAL_IP=central -e CENTRAL_PORT=5000 `'
    $monitorLines += '  -e ENGINE_IP=engine -e ENGINE_PORT=5001 `'
    $monitorLines += '  ev_monitor:local'
} else {
    $monitorLines += 'docker run --rm --name monitor `'
    $monitorLines += '  -e CP_ID=CP_001 `'
    $monitorLines += ('  -e CENTRAL_IP=' + $centralIpForText + ' -e CENTRAL_PORT=5000 `')
    # Usar host.docker.internal para conectar desde contenedor al host (Windows/Mac)
    $monitorLines += '  -e ENGINE_IP=host.docker.internal -e ENGINE_PORT=5001 `'
    $monitorLines += '  ev_monitor:local'
}

# 3) Bloque driver
$driverLines = @()
$driverLines += '# Arrancar Driver'
if ($sameHost) {
    $driverLines += 'docker run --rm --name driver `'
    $driverLines += '  -e KAFKA_BROKER="host.docker.internal:9092" `'
    $driverLines += '  -e DRIVER_ID=DRIVER_456 -e CP_ID=CP_001 -e MAT=ABC-1234 -e KW=1.0 -e LISTEN=true `'
    $driverLines += '  ev_driver:local'
} else {
    $driverLines += 'docker run --rm --name driver `'
    $driverLines += ('  -e KAFKA_BROKER="' + $centralIpForText + ':9092" `')
    $driverLines += '  -e DRIVER_ID=DRIVER_456 -e CP_ID=CP_001 -e MAT=ABC-1234 -e KW=1.0 -e LISTEN=true `'
    $driverLines += '  ev_driver:local'
}

$projectRoot = Split-Path $PSScriptRoot -Parent
$ps1BuildEngine = Join-Path $projectRoot 'commands_PC_B_build_engine.ps1'
$ps1Monitor = Join-Path $projectRoot 'commands_PC_B_monitor.ps1'
$ps1Driver = Join-Path $projectRoot 'commands_PC_B_driver.ps1'
[System.IO.File]::WriteAllLines($ps1BuildEngine, $buildAndEngine, $utf8NoBom)
[System.IO.File]::WriteAllLines($ps1Monitor, $monitorLines, $utf8NoBom)
[System.IO.File]::WriteAllLines($ps1Driver, $driverLines, $utf8NoBom)

$batPath = Join-Path $projectRoot 'run_PC_B.bat'
$batLines = @(
    '@echo off',
    'setlocal',
    'cd /d "%~dp0"',
    'echo Iniciando componentes del Charging Point (PC_B)...',
    'echo.',
    'REM Ventana 1: Build de imagenes y Engine',
    'echo [1/3] Iniciando Build+Engine...',
    'start "Build+Engine" powershell -NoLogo -NoExit -ExecutionPolicy Bypass -File "%~dp0commands_PC_B_build_engine.ps1"',
    'echo Esperando 10 segundos para que Engine este listo...',
    'timeout /t 10 /nobreak >nul',
    'REM Ventana 2: Monitor',
    'echo [2/3] Iniciando Monitor...',
    'start "Monitor" powershell -NoLogo -NoExit -ExecutionPolicy Bypass -File "%~dp0commands_PC_B_monitor.ps1"',
    'echo Esperando 5 segundos...',
    'timeout /t 5 /nobreak >nul',
    'REM Ventana 3: Driver',
    'echo [3/3] Iniciando Driver...',
    'start "Driver" powershell -NoLogo -NoExit -ExecutionPolicy Bypass -File "%~dp0commands_PC_B_driver.ps1"',
    'echo.',
    'echo Todos los componentes han sido iniciados.',
    'echo Presiona cualquier tecla para cerrar esta ventana...',
    'pause >nul'
)
$ascii = New-Object System.Text.ASCIIEncoding
[System.IO.File]::WriteAllLines($batPath, $batLines, $ascii)

Write-Host "Generado: $ps1BuildEngine"
Write-Host "Generado: $ps1Monitor"
Write-Host "Generado: $ps1Driver"
Write-Host "Generado: $batPath"