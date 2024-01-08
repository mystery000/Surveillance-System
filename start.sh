#!/bin/bash

# Activate virtual environment if not activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
    echo "Virtual environment activated."
fi

# Execute python3 webcam.py
echo "Starting webcam.py..."
python3 webcam.py

# Deactivate virtual environment
deactivate
echo "Virtual environment deactivated."
