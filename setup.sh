#!/bin/bash

# DJ Library Builder v2 - Setup Script
# Installs all dependencies (ffmpeg, BlackHole, Python packages)

set -e

echo "=========================================="
echo "DJ Library Builder v2 - Setup"
echo "=========================================="
echo ""

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Install ffmpeg
echo ""
echo "Installing ffmpeg..."
brew install ffmpeg

# Install BlackHole
echo ""
echo "Installing BlackHole (virtual audio device)..."
brew install blackhole-2ch

# Install Python packages
echo ""
echo "Installing Python packages..."
pip3 install -r requirements.txt

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. python3 app.py"
echo "2. Open http://localhost:5000 in your browser"
echo ""
