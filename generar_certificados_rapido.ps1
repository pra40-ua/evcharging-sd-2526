# ============================================================
#  GENERADOR RÁPIDO DE CERTIFICADOS SSL (PowerShell)
#  Para usar en cualquier ordenador con PowerShell
# ============================================================

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  GENERADOR DE CERTIFICADOS SSL PARA EV_Registry" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Buscar OpenSSL
$opensslPath = $null

# Buscar en ubicaciones comunes
$possiblePaths = @(
    "C:\Program Files\OpenSSL-Win64\bin\openssl.exe",
    "C:\Program Files (x86)\OpenSSL-Win64\bin\openssl.exe",
    "C:\OpenSSL-Win64\bin\openssl.exe",
    "C:\Program Files\OpenSSL\bin\openssl.exe"
)

foreach ($path in $possiblePaths) {
    if (Test-Path $path) {
        $opensslPath = $path
        break
    }
}

# Verificar si está en PATH
if (-not $opensslPath) {
    try {
        $null = Get-Command openssl -ErrorAction Stop
        $opensslPath = "openssl"
    } catch {
        # OpenSSL no encontrado
    }
}

if (-not $opensslPath) {
    Write-Host "[ERROR] OpenSSL no encontrado" -ForegroundColor Red
    Write-Host ""
    Write-Host "OPCIONES:" -ForegroundColor Yellow
    Write-Host "  1. Instalar OpenSSL desde: https://slproweb.com/products/Win32OpenSSL.html"
    Write-Host "  2. O usar el método manual (ver GENERAR_CERTIFICADOS_OTRO_PC.md)"
    Write-Host ""
    Write-Host "Si OpenSSL está instalado en otra ubicación, edita este script" -ForegroundColor Yellow
    Write-Host "y agrega la ruta en la variable `$possiblePaths" -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}

Write-Host "[OK] OpenSSL encontrado: $opensslPath" -ForegroundColor Green
& $opensslPath version
Write-Host ""

# Crear directorio
$certDir = Join-Path $PSScriptRoot "certificados"
if (-not (Test-Path $certDir)) {
    New-Item -ItemType Directory -Path $certDir | Out-Null
}

Set-Location $certDir

Write-Host "[1/2] Generando clave privada RSA 2048 bits..." -ForegroundColor Yellow
& $opensslPath genrsa -out registry_key.pem 2048
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Fallo al generar clave privada" -ForegroundColor Red
    pause
    exit 1
}
Write-Host "[OK] Clave privada generada: registry_key.pem" -ForegroundColor Green
Write-Host ""

Write-Host "[2/2] Generando certificado autofirmado (válido 365 días)..." -ForegroundColor Yellow
& $opensslPath req -new -x509 -key registry_key.pem -out registry_cert.pem -days 365 -subj "/C=ES/ST=Madrid/L=Madrid/O=EV_Registry/CN=localhost"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Fallo al generar certificado" -ForegroundColor Red
    pause
    exit 1
}
Write-Host "[OK] Certificado generado: registry_cert.pem" -ForegroundColor Green
Write-Host ""

Set-Location $PSScriptRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  CERTIFICADOS GENERADOS EXITOSAMENTE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Archivos generados en: certificados\" -ForegroundColor Yellow
Write-Host "  - registry_cert.pem  (Certificado)" -ForegroundColor White
Write-Host "  - registry_key.pem    (Clave privada)" -ForegroundColor White
Write-Host ""
Write-Host "Para verificar:" -ForegroundColor Yellow
Write-Host "  Get-ChildItem certificados\registry*.pem" -ForegroundColor Cyan
Write-Host ""
Write-Host "Para usar en EV_Registry:" -ForegroundColor Yellow
Write-Host "  .\INICIAR_REGISTRY.bat" -ForegroundColor Cyan
Write-Host ""
pause

