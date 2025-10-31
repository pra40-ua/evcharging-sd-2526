@echo off
setlocal
cd /d "%~dp0"

echo Construyendo imagen del Engine...
docker build -t ev_engine:local -f ev_cp_engine/Dockerfile .
if errorlevel 1 (
  echo ERROR: Fallo al construir la imagen ev_engine:local
  exit /b 1
)
echo Imagen ev_engine:local construida correctamente.
exit /b 0


