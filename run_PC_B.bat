@echo off
setlocal
cd /d "%~dp0"
REM Ventana 1: Build de im??genes y Engine
start "Build+Engine" powershell -NoLogo -NoExit -ExecutionPolicy Bypass -File "%~dp0commands_PC_B_build_engine.ps1"
REM Ventana 2: Monitor
start "Monitor" powershell -NoLogo -NoExit -ExecutionPolicy Bypass -File "%~dp0commands_PC_B_monitor.ps1"
REM Ventana 3: Driver
start "Driver" powershell -NoLogo -NoExit -ExecutionPolicy Bypass -File "%~dp0commands_PC_B_driver.ps1"
