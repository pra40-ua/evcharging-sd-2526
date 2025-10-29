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
$lines += '# Arrancar Central (usa hostname mysql en la misma red y host.docker.internal para Kafka)'
$lines += 'docker run --rm -it --name central --network evnet -p 5000:5000 `'
$lines += '  -e CENTRAL_PORT=5000 `'
$lines += '  -e KAFKA_BROKER="host.docker.internal:9092" `'
$lines += '  -e DB_URL="mysql:3306:root:root:evcharging" `'
$lines += '  ev_central:local'
$lines += ''
$lines += '# Nota: Kafka debe estar corriendo en el host (puerto 9092) accesible vía host.docker.internal'
$lines += '# Abre puertos 5000 y 9092 en el firewall de este PC.'
$lines += "# IP Central detectada (PC_A): ${localIp}"
$lines += '# Se ha guardado también en central_ip.txt para facilitar la configuración de PC_B.'

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($outPath, $lines, $utf8NoBom)

Write-Host "Generado: $outPath"
Write-Host "IP local detectada: $localIp"
Write-Host "KAFKA_BROKER configurado como: host.docker.internal:9092"
if (Test-Path $centralIpFile) { Write-Host "IP Central escrita en: $centralIpFile" }
