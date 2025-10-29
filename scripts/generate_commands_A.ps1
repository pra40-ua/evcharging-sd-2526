# Genera commands_PC_A.txt con los comandos para PC_A (Central + MySQL)

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

# Ruta de salida (coloca el txt en la raíz del proyecto evcharging-sd-2526)
$projectRoot = Split-Path $PSScriptRoot -Parent
$outPath = Join-Path $projectRoot 'commands_PC_A.txt'

$lines = @()
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
$lines += 'docker build -t ev_central:local ./ev_central'
$lines += ''
$lines += '# Arrancar Central (usa hostname mysql en la misma red)'
$lines += 'docker run --rm --name central --network evnet -p 5000:5000 `'
$lines += '  -e CENTRAL_PORT=5000 `'
$kafkaBrokerLine = '  -e KAFKA_BROKER="' + $localIp + ':9092" `'
$lines += $kafkaBrokerLine
$dbUrlLine = '  -e DB_URL="mysql:3306:root:root:evcharging" `'
$lines += $dbUrlLine
$lines += '  ev_central:local'
$lines += ''
$lines += "# IP local detectada para KAFKA_BROKER: ${localIp}"
$lines += '# Nota: abre puertos 5000 y 9092 en el firewall de este PC.'

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($outPath, $lines, $utf8NoBom)

Write-Host "Generado: $outPath"
Write-Host "IP local detectada: $localIp"
