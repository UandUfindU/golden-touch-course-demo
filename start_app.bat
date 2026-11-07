@echo off
echo ===================================================
echo       Golden Touch Quant OS - Backend Startup
echo ===================================================

:: Define Conda Path
set CONDA_ACTIVATE=C:\Users\fyy\tools\miniconda\Scripts\activate.bat

:: Start Backend
echo [1/1] Starting Backend Server (Port 8000)...
start "Golden Touch Backend" cmd /k "if exist "%CONDA_ACTIVATE%" (call "%CONDA_ACTIVATE%") & cd backend & uvicorn app.main:app --reload --port 8000"

echo.
echo Backend is starting in a new window...
echo ---------------------------------------
echo [Backend API] http://localhost:8000/docs
echo ---------------------------------------
echo Press any key to close this launcher...
pause >nul
