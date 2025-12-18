# Script PowerShell para instalar todas las dependencias del proyecto

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   INSTALANDO DEPENDENCIAS DEL PROYECTO" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Verificar Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Python detectado: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python no está instalado o no está en el PATH" -ForegroundColor Red
    Write-Host "Por favor, instala Python 3.10 o superior" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Verificar/crear entorno virtual
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "[INFO] Activando entorno virtual existente..." -ForegroundColor Yellow
    & "venv\Scripts\Activate.ps1"
    Write-Host "[OK] Entorno virtual activado" -ForegroundColor Green
    Write-Host ""
} elseif (Test-Path "venv\bin\activate") {
    Write-Host "[ADVERTENCIA] Entorno virtual detectado (Linux/WSL)" -ForegroundColor Yellow
    Write-Host "¿Deseas crear un nuevo entorno virtual para Windows? (S/N)" -ForegroundColor Yellow
    $crear_venv = Read-Host
    if ($crear_venv -eq "S" -or $crear_venv -eq "s") {
        Write-Host ""
        Write-Host "[INFO] Creando nuevo entorno virtual..." -ForegroundColor Yellow
        python -m venv venv
        & "venv\Scripts\Activate.ps1"
        Write-Host "[OK] Entorno virtual creado y activado" -ForegroundColor Green
        Write-Host ""
    }
} else {
    Write-Host "[INFO] No se encontró entorno virtual" -ForegroundColor Yellow
    Write-Host "¿Deseas crear uno? (S/N)" -ForegroundColor Yellow
    $crear_venv = Read-Host
    if ($crear_venv -eq "S" -or $crear_venv -eq "s") {
        Write-Host ""
        Write-Host "[INFO] Creando entorno virtual..." -ForegroundColor Yellow
        python -m venv venv
        & "venv\Scripts\Activate.ps1"
        Write-Host "[OK] Entorno virtual creado y activado" -ForegroundColor Green
        Write-Host ""
    } else {
        Write-Host "[INFO] Instalando en el sistema global (no recomendado)" -ForegroundColor Yellow
        Write-Host ""
    }
}

# Actualizar pip
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "[1/4] Actualizando pip..." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
python -m pip install --upgrade pip
Write-Host ""

# Instalar requirements principal
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "[2/4] Instalando requirements.txt principal..." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
if (Test-Path "requirements.txt") {
    pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Error instalando requirements.txt principal" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] requirements.txt principal instalado" -ForegroundColor Green
} else {
    Write-Host "[ADVERTENCIA] No se encontró requirements.txt" -ForegroundColor Yellow
}
Write-Host ""

# Instalar requirements de EV_Registry
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "[3/4] Instalando requirements de EV_Registry..." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
if (Test-Path "ev_registry\requirements.txt") {
    pip install -r ev_registry\requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Error instalando ev_registry\requirements.txt" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Requirements de EV_Registry instalados" -ForegroundColor Green
} else {
    Write-Host "[ADVERTENCIA] No se encontró ev_registry\requirements.txt" -ForegroundColor Yellow
}
Write-Host ""

# Instalar requirements de EV_Weather
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "[4/4] Instalando requirements de EV_Weather..." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
if (Test-Path "ev_weather\requirements.txt") {
    pip install -r ev_weather\requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Error instalando ev_weather\requirements.txt" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Requirements de EV_Weather instalados" -ForegroundColor Green
} else {
    Write-Host "[ADVERTENCIA] No se encontró ev_weather\requirements.txt" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   INSTALACION COMPLETADA" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Para activar el entorno virtual en el futuro, ejecuta:" -ForegroundColor Yellow
Write-Host "  venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host ""

