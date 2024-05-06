# I struggeled with getting the sense hat to work in the 
# viritual environment, so I made this handy install script. 


# Install the senseHAT library
sudo apt-get install sense-hat

# Check if the virtual environment exists
if [ ! -d "venv" ]; then
    python3 -m venv --system-site-packages venv
else
    echo "Virtual environment already exists."
fi

# Activate the virtual environment
echo "Activating the virtual environment..."
source venv/bin/activate

# Install the required packages
echo "Installing the required packages..."
pip install -r requirements.txt

# Setup complete
echo "Setup complete. Enjoy."
