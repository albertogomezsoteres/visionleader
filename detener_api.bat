@echo off
REM Script para detener la API en el puerto 8000

echo Deteniendo procesos en puerto 8000...
echo.

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo Proceso encontrado: PID %%a
    taskkill /F /PID %%a >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] No se pudo detener el proceso %%a
    ) else (
        echo [OK] Proceso %%a detenido
    )
)

echo.
echo Verificando...
netstat -ano | findstr :8000 | findstr LISTENING
if errorlevel 1 (
    echo [OK] Puerto 8000 liberado
) else (
    echo [INFO] Aun hay procesos en el puerto 8000
)

pause
