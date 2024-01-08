#!/bin/bash

# Function to display loading messages
function show_loading() {
    local message=$1
    echo -n "$message"
    while :; do
        echo -n "."
        sleep 1
    done
}

# Check Python version and install if needed
echo "Checking Python version..."
current_python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
required_python_version="3.7"
echo "Current Python version: $current_python_version"

if [ "$(printf '%s\n' "$required_python_version" "$current_python_version" | sort -V | head -n1)" != "$required_python_version" ]; then
    echo "Installing Python $required_python_version..."
    sudo apt-get update
    sudo apt-get install -y python3.7
    sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.7 1
    echo "Python $required_python_version installed successfully."
else
    echo "Python version is Okay"
fi

# Activate virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Activating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Virtual environment activated."
fi

# Install requirements
echo "Installing requirements..."
#show_loading "Please wait"
pip install -r requirements.txt
echo "Requirements installed successfully."

# Clean up loading message
kill $!

# Deactivate virtual environment
deactivate
echo "Virtual environment deactivated."

echo "Installation complete!"
