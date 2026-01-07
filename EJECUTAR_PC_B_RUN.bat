@echo off
REM ============================================================
REM  WRAPPER PARA PC_B_RUN.bat
REM  Este script ejecuta PC_B_RUN.bat y mantiene la ventana abierta
REM ============================================================

cd /d "%~dp0"

echo ============================================================
echo   EJECUTANDO PC_B_RUN.bat
echo ============================================================
echo.
echo Este script ejecutara PC_B_RUN.bat y mantendra la ventana abierta
echo para que puedas ver cualquier error o mensaje.
echo.
echo Si el script se cierra inmediatamente, revisa el archivo de log
echo en la carpeta logs\PC_B_RUN_*.log
echo.
echo Presiona cualquier tecla para continuar...
pause >nul
echo.

REM Ejecutar PC_B_RUN.bat
call PC_B_RUN.bat

REM Capturar el codigo de salida
set EXIT_CODE=%errorlevel%

echo.
echo ============================================================
echo   PC_B_RUN.bat ha terminado
echo ============================================================
echo.
echo Codigo de salida: %EXIT_CODE%
echo.
if %EXIT_CODE% neq 0 (
    echo [ERROR] El script termino con un error (codigo: %EXIT_CODE%)
    echo.
    echo Revisa el archivo de log mas reciente en la carpeta logs\
    echo para ver mas detalles sobre el error.
    echo.
) else (
    echo [OK] El script termino correctamente.
    echo.
)

echo Presiona cualquier tecla para cerrar esta ventana...
pause >nul

exit /b %EXIT_CODE%


