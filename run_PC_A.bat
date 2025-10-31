@echo off
setlocal
cd /d "%~dp0"
REM Abre una nueva ventana de PowerShell y ejecuta todos los comandos de PC_A
start "Central-PC_A" powershell -NoLogo -NoExit -ExecutionPolicy Bypass -File "%~dp0commands_PC_A.ps1"
