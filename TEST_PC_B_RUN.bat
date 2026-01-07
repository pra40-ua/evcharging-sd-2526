@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo   TEST: PC_B_RUN.bat - VERSION DE PRUEBA
echo ============================================================
echo.
echo Este script ejecutara PC_B_RUN.bat y mantendra la ventana abierta
echo para que puedas ver cualquier error.
echo.
echo Presiona cualquier tecla para continuar...
pause >nul
echo.

REM Cambiar al directorio del script
cd /d "%~dp0"

REM Ejecutar PC_B_RUN.bat
call PC_B_RUN.bat

REM Si llegamos aqui, el script termino
echo.
echo ============================================================
echo   El script PC_B_RUN.bat ha terminado.
echo ============================================================
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
pause >nul


