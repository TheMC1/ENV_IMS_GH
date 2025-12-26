@echo off
echo ============================================================
echo Carbon IMS - Inventory Management System
echo ============================================================
echo.

REM Check if virtual environment exists
if not exist ".venv" (
    echo Virtual environment not found!
    echo Please run setup.bat first.
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate

REM Check if databases exist
if not exist "ims_users.db" (
    echo.
    echo Databases not initialized!
    echo Running database initialization...
    python init_databases.py
    echo.
)

REM Start the application
echo Starting Carbon IMS...
echo Application will be available at: http://127.0.0.1:5000
echo.
echo Press Ctrl+C to stop the server
echo.
python app.py

pause
