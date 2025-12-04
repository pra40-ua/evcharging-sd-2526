# ============================================================
#  GENERADOR DE CERTIFICADOS SSL PARA EV_Registry (PowerShell)
# ============================================================
#  Genera certificados SSL autofirmados usando PowerShell
#  (No requiere OpenSSL instalado)
# ============================================================

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  GENERADOR DE CERTIFICADOS SSL PARA EV_Registry" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Crear directorio para certificados
$certDir = Join-Path $PSScriptRoot "certificados"
if (-not (Test-Path $certDir)) {
    New-Item -ItemType Directory -Path $certDir | Out-Null
}

Write-Host "[1/3] Generando certificado SSL autofirmado..." -ForegroundColor Yellow

# Generar certificado autofirmado válido por 365 días
$cert = New-SelfSignedCertificate `
    -Subject "CN=localhost, O=EV_Registry, C=ES" `
    -KeyAlgorithm RSA `
    -KeyLength 2048 `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -NotAfter (Get-Date).AddDays(365) `
    -KeyUsage DigitalSignature, KeyEncipherment `
    -Type SSLServerAuthentication

if (-not $cert) {
    Write-Host "[ERROR] Fallo al generar certificado" -ForegroundColor Red
    pause
    exit 1
}

Write-Host "[OK] Certificado generado en el almacén de Windows" -ForegroundColor Green

# Exportar certificado y clave privada
$certPath = Join-Path $certDir "registry_cert.pem"
$keyPath = Join-Path $certDir "registry_key.pem"
$pfxPath = Join-Path $certDir "registry.pfx"

Write-Host "[2/3] Exportando certificado..." -ForegroundColor Yellow

# Exportar como PFX (incluye clave privada)
$password = ConvertTo-SecureString -String "evregistry123" -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $password | Out-Null

# Exportar certificado en formato PEM
$certBytes = $cert.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert)
$certBase64 = [System.Convert]::ToBase64String($certBytes)
$certPEM = "-----BEGIN CERTIFICATE-----" + [Environment]::NewLine
$certPEM += ($certBase64 -replace '(.{64})', '$1' + [Environment]::NewLine)
$certPEM += [Environment]::NewLine + "-----END CERTIFICATE-----" + [Environment]::NewLine
[System.IO.File]::WriteAllText($certPath, $certPEM, [System.Text.Encoding]::UTF8)

Write-Host "[OK] Certificado exportado: $certPath" -ForegroundColor Green

Write-Host "[3/3] Exportando clave privada..." -ForegroundColor Yellow

# Intentar extraer la clave privada usando Python (más confiable que OpenSSL)
$pythonScript = @"
import sys
import os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

pfx_path = r"$pfxPath"
output_path = r"$keyPath"
password = "evregistry123"

try:
    with open(pfx_path, 'rb') as f:
        pfx_data = f.read()
    
    private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
        pfx_data, password.encode('utf-8'))
    
    if private_key is None:
        sys.exit(1)
    
    pem_key = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption())
    
    with open(output_path, 'wb') as f:
        f.write(pem_key)
    
    sys.exit(0)
except Exception:
    sys.exit(1)
"@

# Guardar script temporal
$tempScript = Join-Path $env:TEMP "extract_key_$(Get-Random).py"
$pythonScript | Out-File -FilePath $tempScript -Encoding UTF8

# Intentar ejecutar con Python
$pythonFound = $false
$pythonCmds = @("python", "python3", "py")

foreach ($cmd in $pythonCmds) {
    $pythonCmd = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        Write-Host "[INFO] Extrayendo clave privada usando Python..." -ForegroundColor Yellow
        $result = & $cmd $tempScript 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Clave privada extraida: $keyPath" -ForegroundColor Green
            $pythonFound = $true
            break
        }
    }
}

# Limpiar script temporal
Remove-Item $tempScript -ErrorAction SilentlyContinue

if (-not $pythonFound) {
    Write-Host "[ADVERTENCIA] No se pudo extraer la clave privada automaticamente" -ForegroundColor Yellow
    Write-Host "              La clave privada esta en el archivo PFX" -ForegroundColor Yellow
    Write-Host "              Para extraerla manualmente:" -ForegroundColor Yellow
    Write-Host "              python extraer_clave_privada.py" -ForegroundColor Cyan
    Write-Host "              O con OpenSSL:" -ForegroundColor Yellow
    Write-Host "              openssl pkcs12 -in certificados\registry.pfx -nocerts -nodes -out certificados\registry_key.pem" -ForegroundColor Cyan
    Write-Host "              Contrasena: evregistry123" -ForegroundColor Cyan
    Write-Host ""
}

# Guardar información del certificado
$certInfo = @"
Certificado SSL generado para EV_Registry
==========================================
Fecha: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Thumbprint: $($cert.Thumbprint)
Válido hasta: $($cert.NotAfter)
Archivos:
  - Certificado: $certPath
  - PFX (cert+key): $pfxPath
  - Clave privada: $keyPath (extraer con OpenSSL)

Para usar en EV_Registry:
  python ev_registry\EV_Registry.py --ssl-cert certificados\registry_cert.pem --ssl-key certificados\registry_key.pem
"@

$infoPath = Join-Path $certDir "README.txt"
[System.IO.File]::WriteAllText($infoPath, $certInfo)

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  CERTIFICADOS SSL GENERADOS EXITOSAMENTE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Archivos generados en: certificados\" -ForegroundColor Yellow
Write-Host "  - registry_cert.pem  (Certificado)" -ForegroundColor White
if (Test-Path $keyPath) {
    Write-Host "  - registry_key.pem   (Clave privada) [OK]" -ForegroundColor Green
} else {
    Write-Host "  - registry_key.pem   (Clave privada) [Pendiente]" -ForegroundColor Yellow
}
Write-Host "  - registry.pfx       (Certificado + Clave privada)" -ForegroundColor White
Write-Host "  - README.txt         (Instrucciones)" -ForegroundColor White
Write-Host ""
Write-Host "IMPORTANTE:" -ForegroundColor Yellow
Write-Host "  - Estos son certificados autofirmados (solo para desarrollo)" -ForegroundColor White
Write-Host "  - Los navegadores mostraran advertencias de seguridad" -ForegroundColor White
Write-Host "  - Para produccion, use certificados de una CA reconocida" -ForegroundColor White
Write-Host ""
pause



