<#
.SYNOPSIS
    Verifica si un puerto está abierto y accesible
.DESCRIPTION
    Este script verifica si un puerto TCP está abierto y accesible desde la red.
    No requiere permisos de administrador.
.PARAMETER ComputerName
    La IP o hostname del equipo a verificar (opcional, por defecto verifica localhost)
.PARAMETER Port
    El puerto a verificar (obligatorio)
.EXAMPLE
    .\check_port.ps1 -Port 5000
    Verifica si el puerto 5000 está abierto localmente
.EXAMPLE
    .\check_port.ps1 -ComputerName 192.168.1.100 -Port 5000
    Verifica si puede acceder al puerto 5000 en el equipo 192.168.1.100
#>

param(
    [string]$ComputerName = "localhost",
    [Parameter(Mandatory=$true)]
    [int]$Port
)

Write-Host "=" * 60
Write-Host "Verificando puerto $Port en $ComputerName" -ForegroundColor Cyan
Write-Host "=" * 60

# Verificar si es localhost
if ($ComputerName -eq "localhost" -or $ComputerName -eq "127.0.0.1") {
    Write-Host "`n[1] Verificando puertos locales en uso..." -ForegroundColor Yellow
    $localConnections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($localConnections) {
        Write-Host "✓ El puerto $Port está ESCUCHANDO localmente" -ForegroundColor Green
        $localConnections | Format-Table LocalAddress, LocalPort, State -AutoSize
    } else {
        Write-Host "✗ El puerto $Port NO está escuchando localmente" -ForegroundColor Red
    }
    
    # Verificar también con netstat
    Write-Host "`n[2] Verificando con netstat..." -ForegroundColor Yellow
    $netstatResult = netstat -an | Select-String ":$Port"
    if ($netstatResult) {
        Write-Host "✓ Encontrado en netstat:" -ForegroundColor Green
        $netstatResult
    } else {
        Write-Host "✗ No encontrado en netstat" -ForegroundColor Red
    }
} else {
    Write-Host "`n[1] Verificando conectividad remota..." -ForegroundColor Yellow
    
    try {
        $result = Test-NetConnection -ComputerName $ComputerName -Port $Port -WarningAction SilentlyContinue
        
        if ($result.TcpTestSucceeded) {
            Write-Host "✓ Puerto $Port está ABIERTO y accesible en $ComputerName" -ForegroundColor Green
            Write-Host "  - Tiempo de respuesta: $($result.RoundtripTime) ms" -ForegroundColor Gray
        } else {
            Write-Host "✗ Puerto $Port NO es accesible en $ComputerName" -ForegroundColor Red
            Write-Host "  Posibles causas:" -ForegroundColor Yellow
            Write-Host "    - El servicio no está ejecutándose" -ForegroundColor Yellow
            Write-Host "    - El firewall está bloqueando el puerto" -ForegroundColor Yellow
            Write-Host "    - La IP es incorrecta" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "✗ Error al verificar: $_" -ForegroundColor Red
    }
    
    Write-Host "`n[2] Verificando con conexión TCP directa..." -ForegroundColor Yellow
    $tcpClient = New-Object System.Net.Sockets.TcpClient
    $tcpClient.ReceiveTimeout = 3000
    $tcpClient.SendTimeout = 3000
    
    try {
        $tcpClient.Connect($ComputerName, $Port)
        Write-Host "✓ Conexión TCP exitosa" -ForegroundColor Green
        $tcpClient.Close()
    } catch {
        Write-Host "✗ No se pudo establecer conexión TCP: $_" -ForegroundColor Red
    }
}

Write-Host "`n" + ("=" * 60)

