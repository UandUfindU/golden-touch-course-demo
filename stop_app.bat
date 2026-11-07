@echo off
echo ===================================================
echo       Stopping Golden Touch Quant OS
echo ===================================================

echo [1/1] Stopping Backend...
taskkill /F /FI "WINDOWTITLE eq Golden Touch Backend*" /T >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo    - Window closed.
)
:: Also try killing uvicorn if running background
taskkill /F /IM "uvicorn.exe" /T >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo    - Uvicorn process terminated.
)

echo.
echo Backend service stopped.
echo Press any key to exit...
pause >nul
