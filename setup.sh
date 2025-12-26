#!/bin/bash

echo "============================================================"
echo "Carbon IMS - Setup Script"
echo "============================================================"
echo ""

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3 from https://www.python.org/downloads/"
    exit 1
fi

echo "Python found:"
python3 --version
echo ""

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv .venv
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create virtual environment"
    exit 1
fi
echo "Virtual environment created successfully"
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate
echo ""

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip
echo ""

# Install requirements
echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi
echo "Dependencies installed successfully"
echo ""

# Initialize databases
echo "Initializing databases..."
python init_databases.py
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to initialize databases"
    exit 1
fi

echo ""
echo "============================================================"
echo "Setup Complete!"
echo "============================================================"
echo ""
echo "To start the application, run: ./start.sh"
echo "Or manually:"
echo "  1. source .venv/bin/activate"
echo "  2. python app.py"
echo ""
