@echo off
echo ============================================================
echo Carbon IMS - Setup Script
echo ============================================================
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    py --version >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python is not installed or not in PATH
        echo Please install Python from https://www.python.org/downloads/
        echo.
        pause
        exit /b 1
    )
    set PYTHON_CMD=py
) else (
    set PYTHON_CMD=python
)

echo Python found:
%PYTHON_CMD% --version
echo.

REM Create virtual environment
echo Creating virtual environment...
%PYTHON_CMD% -m venv .venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)
echo Virtual environment created successfully
echo.

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate
echo.

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip
echo.

REM Install requirements
echo Installing dependencies from requirements.txt...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo Dependencies installed successfully
echo.

REM Initialize databases
echo Initializing databases...
python init_databases.py
if errorlevel 1 (
    echo ERROR: Failed to initialize databases
    pause
    exit /b 1
)

echo.
echo ============================================================
echo Setup Complete!
echo ============================================================
echo.
echo To start the application, run: start.bat
echo Or manually:
echo   1. .venv\Scripts\activate
echo   2. python app.py
echo.
pause
