# Genera commands_PC_A.txt con los comandos para PC_A (Central + MySQL)

# Detectar IPv4 local principal usando la ruta por defecto (evita IPs secundarias/virtuales)
$localIp = $null
try {
    $defaultRoute = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Sort-Object -Property RouteMetric, InterfaceMetric |
        Select-Object -First 1
    if ($defaultRoute) {
        $ifIndex = $defaultRoute.ifIndex
        $candidate = Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $ifIndex -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254*' }
        if ($candidate) {
            $localIp = ($candidate | Select-Object -First 1 -ExpandProperty IPAddress)
        }
    }
} catch {}

# Fallback: método anterior si no se obtuvo desde la ruta por defecto
if (-not $localIp) {
    $localIp = (
        Get-NetIPAddress -AddressFamily IPv4 |
            Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254*' } |
            Sort-Object -Property PrefixLength -Descending |
            Select-Object -First 1 -ExpandProperty IPAddress
    )
}
if (-not $localIp) {
    Write-Error 'No se pudo detectar la IP IPv4 local.'
    exit 1
}

# Ruta de salida (coloca el txt en la raíz del proyecto evcharging-sd-2526)
$projectRoot = Split-Path $PSScriptRoot -Parent
$outPath = Join-Path $projectRoot 'commands_PC_A.txt'

# Guardar también la IP detectada en un archivo para que PC_B pueda leerla
$centralIpFile = Join-Path $projectRoot 'central_ip.txt'
try {
    Set-Content -Path $centralIpFile -Value $localIp -NoNewline -Encoding ASCII
} catch {
    Write-Warning "No se pudo escribir central_ip.txt: $_"
}

# Actualizar docker-compose.yml para que Kafka anuncie la IP real (en lugar de host.docker.internal)
$composePath = Join-Path $projectRoot 'docker-compose.yml'
if (Test-Path $composePath) {
    try {
        $compose = Get-Content -Path $composePath -Raw -Encoding UTF8
        $newCompose = $compose -replace 'KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://[^\n\r]+:9092', "KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://$localIp:9092"
        if ($newCompose -ne $compose) {
            [System.IO.File]::WriteAllText($composePath, $newCompose, (New-Object System.Text.UTF8Encoding($false)))
            Write-Host "docker-compose.yml actualizado con KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://$localIp:9092"
        } else {
            Write-Host "docker-compose.yml ya contenía la IP adecuada o no se encontró la línea a reemplazar."
        }
    } catch {
        Write-Warning "No se pudo actualizar docker-compose.yml: $_"
    }
}

$lines = @()
$lines += '# Arrancar Kafka (en el host, accesible desde contenedores vía host.docker.internal)'
$lines += 'docker compose down'
$lines += 'docker compose up -d'
$lines += ''
$lines += '# Crear red y volumen para MySQL'
$lines += 'docker network create evnet'
$lines += 'docker volume create ev_mysql_data'
$lines += ''
$lines += '# Arrancar MySQL (primer arranque ejecuta db/init.sql)'
$lines += 'docker run -d --name mysql --network evnet -p 3306:3306 `'
$lines += '  -e MYSQL_ROOT_PASSWORD=root -e MYSQL_DATABASE=evcharging `'
$lines += '  -v ev_mysql_data:/var/lib/mysql `'
$lines += '  -v ${PWD}\db\init.sql:/docker-entrypoint-initdb.d/01_schema.sql `'
$lines += '  mysql:8'
$lines += ''
$lines += '# Construir imagen de la central (si no existe)'
$lines += 'docker build -t ev_central:local -f ev_central/Dockerfile .'
$lines += ''
$lines += '# Arrancar Central (usa hostname mysql en la misma red y la IP real para Kafka)'
$lines += 'docker run --rm -it --name central --network evnet -p 5000:5000 `'
$lines += '  -e CENTRAL_PORT=5000 `'
$lines += '  -e KAFKA_BROKER="' + $localIp + ':9092" `'
$lines += '  -e DB_URL="mysql:3306:root:root:evcharging" `'
$lines += '  ev_central:local'
$lines += ''
$lines += '# Nota: Kafka debe estar corriendo en el host (puerto 9092) accesible por IP'
$lines += '# Abre puertos 5000 y 9092 en el firewall de este PC.'
$lines += "# IP Central detectada (PC_A): ${localIp}"
$lines += '# Se ha guardado también en central_ip.txt para facilitar la configuración de PC_B.'

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($outPath, $lines, $utf8NoBom)

Write-Host "Generado: $outPath"
Write-Host "IP local detectada: $localIp"
Write-Host "KAFKA_BROKER configurado como: $localIp:9092"
if (Test-Path $centralIpFile) { Write-Host "IP Central escrita en: $centralIpFile" }

# Generar también un script PS1 equivalente para ejecución directa y un BAT que abre una terminal y lo ejecuta
$ps1OutPath = Join-Path $projectRoot 'commands_PC_A.ps1'
[System.IO.File]::WriteAllLines($ps1OutPath, $lines, $utf8NoBom)

$batPath = Join-Path $projectRoot 'run_PC_A.bat'
$batLines = @(
    '@echo off',
    'setlocal',
    'cd /d "%~dp0"',
    'REM Abre una nueva ventana de PowerShell y ejecuta todos los comandos de PC_A',
    'start "Central-PC_A" powershell -NoLogo -NoExit -ExecutionPolicy Bypass -File "%~dp0commands_PC_A.ps1"'
)
$ascii = New-Object System.Text.ASCIIEncoding
[System.IO.File]::WriteAllLines($batPath, $batLines, $ascii)
Write-Host "Generado: $ps1OutPath"
Write-Host "Generado: $batPath"