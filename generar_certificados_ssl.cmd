@echo off
REM ============================================================
REM  GENERADOR DE CERTIFICADOS SSL PARA EV_Registry
REM  Wrapper para ejecutar desde PowerShell
REM ============================================================

cd /d "%~dp0"
call generar_certificados_ssl.bat

