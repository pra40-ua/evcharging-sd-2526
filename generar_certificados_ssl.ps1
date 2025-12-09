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
$certPEM = "-----BEGIN CERTIFICATE-----`n"
$certPEM += ($certBase64 -replace '(.{64})', '$1`n')
$certPEM += "`n-----END CERTIFICATE-----"
[System.IO.File]::WriteAllText($certPath, $certPEM)

Write-Host "[OK] Certificado exportado: $certPath" -ForegroundColor Green

Write-Host "[3/3] Exportando clave privada..." -ForegroundColor Yellow

# Para la clave privada, necesitamos usar OpenSSL o convertir desde PFX
# Por ahora, generamos un script para extraerla
$extractKeyScript = @"
# Extraer clave privada desde PFX usando OpenSSL
# Ejecutar: openssl pkcs12 -in registry.pfx -nocerts -nodes -out registry_key.pem
# Contraseña: evregistry123
"@

Write-Host "[INFO] Clave privada está en el archivo PFX" -ForegroundColor Yellow
Write-Host "       Para extraerla, ejecuta:" -ForegroundColor Yellow
Write-Host "       openssl pkcs12 -in certificados\registry.pfx -nocerts -nodes -out certificados\registry_key.pem" -ForegroundColor Cyan
Write-Host "       Contraseña: evregistry123" -ForegroundColor Cyan
Write-Host ""

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
Write-Host "  - registry.pfx       (Certificado + Clave privada)" -ForegroundColor White
Write-Host "  - README.txt         (Instrucciones)" -ForegroundColor White
Write-Host ""
Write-Host "IMPORTANTE:" -ForegroundColor Yellow
Write-Host "  - Estos son certificados autofirmados (solo para desarrollo)" -ForegroundColor White
Write-Host "  - Los navegadores mostrarán advertencias de seguridad" -ForegroundColor White
Write-Host "  - Para producción, use certificados de una CA reconocida" -ForegroundColor White
Write-Host ""
Write-Host "Para extraer la clave privada:" -ForegroundColor Yellow
Write-Host "  openssl pkcs12 -in certificados\registry.pfx -nocerts -nodes -out certificados\registry_key.pem" -ForegroundColor Cyan
Write-Host ""
pause



