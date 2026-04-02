#!/bin/bash
#
# LBRY Downloader - Quick Installation Script
#
# This script runs the interactive setup.py which handles:
# - Dependency checking and installation
# - Virtual environment setup
# - User configuration (download location, channels, etc.)
# - Launcher script creation
#

set -e

echo "================================================"
echo "  Odysee/LBRY Downloader - Installation"
echo "================================================"
echo ""

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if setup.py exists
if [ ! -f "setup.py" ]; then
    echo "Error: setup.py not found"
    echo "Please ensure you're running this from the LBRY-Downloader directory"
    exit 1
fi

# Run the interactive setup
echo "Starting interactive setup..."
echo "This will guide you through installation and configuration"
echo ""
python3 setup.py

echo ""
echo "================================================"
echo "Installation script completed!"
echo "================================================"
echo "  LBRY Downloader - Linux Installation"
echo "================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if running on Debian-based system
if ! command -v apt-get &> /dev/null; then
    print_error "This script is designed for Debian-based systems (Debian, Ubuntu, Mint)"
    echo "Please install manually following the instructions in LINUX_SETUP.md"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check Python version
echo "Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    REQUIRED_VERSION="3.8"
    
    if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" = "$REQUIRED_VERSION" ]; then
        print_status "Python $PYTHON_VERSION found (3.8+ required)"
    else
        print_error "Python 3.8 or higher required, found $PYTHON_VERSION"
        exit 1
    fi
else
    print_error "Python 3 not found"
    exit 1
fi

# Install system packages
echo ""
echo "Installing system packages..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv git curl wget unzip
print_status "System packages installed"

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
if [ -d "venv" ]; then
    print_warning "Virtual environment already exists"
else
    python3 -m venv venv
    print_status "Created virtual environment"
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
print_status "Python dependencies installed"

echo ""
echo "Checking for optional LBRY SDK (lbrynet)..."
if command -v lbrynet &> /dev/null; then
    print_status "Optional P2P dependency found at: $(which lbrynet)"
    lbrynet --version
else
    print_info "lbrynet not found. Default direct mode does not require it."
    print_info "Install it later only if you want to run with --p2p."
fi

# Initialize configuration
echo ""
echo "Initializing configuration..."
if [ ! -f "$HOME/Documents/lbry-downloads/config.yaml" ]; then
    source venv/bin/activate
    python init.py
else
    print_warning "Configuration already exists at ~/Documents/lbry-downloads/config.yaml"
fi

# Create convenient wrapper script
echo ""
echo "Creating wrapper script..."
mkdir -p ~/bin
cat > ~/bin/lbry-sync << 'EOF'
#!/bin/bash
# LBRY Downloader wrapper script

INSTALL_DIR="$( cd "$( dirname "$(readlink -f "$0")" )" && cd .. && pwd )"
DOWNLOADER_DIR="$INSTALL_DIR/Documents/LBRY-Downloader"

# Check if we're in a different location
if [ ! -f "$DOWNLOADER_DIR/main.py" ]; then
    # Try to find the installation
    if [ -f "$HOME/Documents/LBRY-Downloader/main.py" ]; then
        DOWNLOADER_DIR="$HOME/Documents/LBRY-Downloader"
    elif [ -f "$PWD/main.py" ]; then
        DOWNLOADER_DIR="$PWD"
    else
        echo "Error: Cannot find LBRY-Downloader installation"
        exit 1
    fi
fi

cd "$DOWNLOADER_DIR"
source venv/bin/activate 2>/dev/null || true

python main.py "$@"
EOF

chmod +x ~/bin/lbry-sync

if [[ ":$PATH:" == *":$HOME/bin:"* ]]; then
    print_status "Created wrapper script: ~/bin/lbry-sync"
else
    print_warning "~/bin is not in your PATH"
    echo "Add this to your ~/.bashrc:"
    echo 'export PATH="$HOME/bin:$PATH"'
fi

# Final instructions
echo ""
echo "================================================"
echo -e "${GREEN}Installation Complete!${NC}"
echo "================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Edit configuration to add your channels:"
echo "   nano ~/Documents/lbry-downloads/config.yaml"
echo ""
echo "2. Start the LBRY daemon:"
echo "   Optional only for P2P mode: lbrynet start"
echo ""
echo "3. Test with dry-run:"
echo "   python main.py --dry-run"
echo "   # OR:"
echo "   ~/bin/lbry-sync --dry-run"
echo ""
echo "4. Run the downloader:"
echo "   python main.py --non-video-only"
echo "   # OR:"
echo "   ~/bin/lbry-sync --non-video-only"
echo ""
echo "5. Optional local-node mode:"
echo "   python main.py --p2p"
echo ""
echo "For detailed instructions, see:"
echo "  - LINUX_SETUP.md"
echo "  - QUICKSTART.md"
echo ""
echo "================================================"
