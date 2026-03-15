#!/bin/bash
#
# LBRY Downloader - Remote Installation Script
#
# This script downloads and sets up LBRY Downloader.
#
# USAGE:
#   Option 1 - Download and run (Recommended):
#     curl -fsSL https://raw.githubusercontent.com/PR0M3TH3AN/LBRY-Downloader/main/remote-install.sh -o install-lbry.sh && bash install-lbry.sh
#
#   Option 2 - Clone manually:
#     git clone https://github.com/PR0M3TH3AN/LBRY-Downloader.git
#     cd LBRY-Downloader
#     ./setup.py
#

set -e

REPO_URL="https://github.com/PR0M3TH3AN/LBRY-Downloader.git"
INSTALL_DIR="${HOME}/Documents/LBRY-Downloader"

echo "=========================================="
echo "  LBRY Downloader - Remote Installer"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check for required tools
if ! command -v git &> /dev/null; then
    print_error "Git is required but not installed"
    echo "Please install Git first:"
    echo "  sudo apt-get install git  # Debian/Ubuntu/Mint"
    echo "  sudo dnf install git      # Fedora"
    echo "  sudo pacman -S git        # Arch"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is required but not installed"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
REQUIRED="3.8"

if [ "$(printf '%s\n' "$REQUIRED" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED" ]; then
    print_error "Python 3.8+ required, found $PYTHON_VERSION"
    exit 1
fi

print_status "Python $PYTHON_VERSION found"

# Check if running in interactive mode
INTERACTIVE=false
if [ -t 0 ]; then
    INTERACTIVE=true
fi

# Check if already installed
if [ -d "$INSTALL_DIR" ]; then
    print_warning "LBRY Downloader already exists at $INSTALL_DIR"
    read -p "Reinstall? This will backup your config. (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Backup config if it exists
        if [ -f "$HOME/Documents/lbry-downloads/config.yaml" ]; then
            BACKUP_DIR="$HOME/.lbry-downloader-backup-$(date +%Y%m%d-%H%M%S)"
            mkdir -p "$BACKUP_DIR"
            cp -r "$HOME/Documents/lbry-downloads" "$BACKUP_DIR/"
            print_status "Backed up config to $BACKUP_DIR"
        fi
        rm -rf "$INSTALL_DIR"
    else
        echo "Installation cancelled"
        exit 0
    fi
fi

# Clone repository
print_status "Downloading LBRY Downloader..."
git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"

# Run setup
print_status "Starting setup..."
cd "$INSTALL_DIR"
./setup.py

echo ""
echo "=========================================="
print_status "Installation complete!"
echo "=========================================="
echo ""
echo "You can now run LBRY Downloader:"
echo "  cd $INSTALL_DIR && ./bin/lbry-downloader"
echo ""
echo "Or add to your PATH:"
echo "  echo 'export PATH=\"$INSTALL_DIR/bin:\$PATH\"' >> ~/.bashrc"
echo ""
