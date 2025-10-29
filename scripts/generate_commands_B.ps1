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
$lines += 'docker run --rm -p 5001:5001 --name engine `'
$lines += '  -e ENGINE_PORT=5001 -e CP_ID=CP_001 `'
$kafkaServerLine = '  -e KAFKA_SERVER="' + $centralIpForText + ':9092" `'
$lines += $kafkaServerLine
$lines += '  ev_engine:local'
$lines += ''
$lines += '# Arrancar Monitor'
$lines += 'docker run --rm --name monitor `'
$lines += '  -e CP_ID=CP_001 `'
$centralIpLine = '  -e CENTRAL_IP=' + $centralIpForText + ' -e CENTRAL_PORT=5000 `'
$lines += $centralIpLine
$engineIpLine = '  -e ENGINE_IP=' + $localIp + ' -e ENGINE_PORT=5001 `'
$lines += $engineIpLine
$lines += '  ev_monitor:local'
$lines += ''
$lines += '# Arrancar Driver'
$lines += 'docker run --rm --name driver `'
$kafkaBrokerLineDriver = '  -e KAFKA_BROKER="' + $centralIpForText + ':9092" `'
$lines += $kafkaBrokerLineDriver
$lines += '  -e DRIVER_ID=DRIVER_456 -e CP_ID=CP_001 -e MAT=ABC-1234 -e KW=25.0 -e LISTEN=true `'
$lines += '  ev_driver:local'
$lines += ''
$lines += "# IP local detectada (PC_B): ${localIp}"
$lines += (if (-not [string]::IsNullOrWhiteSpace($CentralIp)) { "# IP Central usada (PC_A): ${CentralIp}" } else { "# IP Central: <CENTRAL_IP> (reemplazar por la IP de PC_A)" })
$lines += '# Nota: abre puertos 5001 en este PC y 9092 en PC_A.'

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($outPath, $lines, $utf8NoBom)

Write-Host "Generado: $outPath"
Write-Host "IP local detectada: $localIp"
if (-not [string]::IsNullOrWhiteSpace($CentralIp)) { Write-Host "IP Central usada: $CentralIp" }
