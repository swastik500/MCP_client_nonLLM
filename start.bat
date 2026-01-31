@echo off
REM Quick start script for MCP Client (Windows)

echo 🚀 MCP Client - Quick Start
echo ============================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed. Please install Python 3.11+
    exit /b 1
)

REM Check if Node.js is installed
node --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Node.js is not installed. Please install Node.js 18+
    exit /b 1
)

echo ✅ Python version:
python --version
echo ✅ Node.js version:
node --version
echo.

REM Backend setup
echo 📦 Setting up backend...
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing Python dependencies...
pip install -q -r config\requirements.txt

echo Downloading spaCy model...
python -m spacy download en_core_web_sm

echo ✅ Backend setup complete!
echo.

REM Frontend setup
echo 📦 Setting up frontend...
cd frontend

if not exist "node_modules" (
    echo Installing Node.js dependencies...
    call npm install
)

echo ✅ Frontend setup complete!
echo.

REM Start services
echo 🎉 Starting services...
echo.
echo Backend will run on: http://localhost:8000
echo Frontend will run on: http://localhost:3000
echo.
echo Press Ctrl+C to stop services
echo.

cd ..

REM Start backend in new window
start "MCP Backend" cmd /k "venv\Scripts\activate.bat && python main.py"

REM Wait for backend to start
timeout /t 3 /nobreak >nul

REM Start frontend
cd frontend
call npm run dev
