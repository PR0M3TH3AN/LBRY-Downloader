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

# Check if lbrynet is installed
if ! command -v lbrynet &> /dev/null; then
    print_warning "LBRY SDK (lbrynet) not found"
    echo ""
    echo "The LBRY SDK is required to download content from the LBRY network."
    echo "It can be downloaded from: https://github.com/lbryio/lbry-sdk/releases"
    echo ""
    read -p "Download and install lbrynet automatically? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        print_status "Installing LBRY SDK..."
        
        # Create bin directory
        mkdir -p ~/.local/bin
        
        # Download latest lbrynet for Linux
        LBRY_VERSION="0.113.0"
        DOWNLOAD_URL="https://github.com/lbryio/lbry-sdk/releases/download/v${LBRY_VERSION}/lbrynet-linux.zip"
        
        cd ~/.local/bin
        
        # Download with progress
        echo "Downloading lbrynet v${LBRY_VERSION}..."
        if wget --progress=bar:force "$DOWNLOAD_URL" -O lbrynet-linux.zip 2>&1; then
            print_status "Downloaded lbrynet"
            
            # Check if file exists and has content
            if [ -f "lbrynet-linux.zip" ] && [ -s "lbrynet-linux.zip" ]; then
                # Extract
                if unzip -q lbrynet-linux.zip; then
                    rm lbrynet-linux.zip
                    chmod +x lbrynet
                    print_status "Extracted lbrynet"
                    
                    # Add to PATH if not already there
                    if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
                        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
                        print_status "Added ~/.local/bin to PATH"
                        export PATH="$HOME/.local/bin:$PATH"
                    fi
                    
                    print_status "LBRY SDK installed successfully!"
                    print_info "lbrynet installed to: ~/.local/bin/lbrynet"
                else
                    print_error "Failed to extract lbrynet"
                    rm -f lbrynet-linux.zip
                fi
            else
                print_error "Download failed - file not found or empty"
            fi
        else
            print_error "Failed to download lbrynet"
            echo "Please install manually from:"
            echo "  https://github.com/lbryio/lbry-sdk/releases"
        fi
        
        # Return to original directory
        cd - > /dev/null
    else
        print_warning "Skipping lbrynet installation"
        echo "You'll need to install it manually before using the downloader"
    fi
else
    print_status "lbrynet found at: $(which lbrynet)"
fi

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
echo "🎉 Setup finished! The command 'lbry-downloader' has been added to your PATH."
echo ""
echo "📋 NEXT STEPS:"
echo ""
echo "1️⃣  Reload your shell (IMPORTANT):"
echo "    source ~/.bashrc"
echo ""
echo "2️⃣  Test the downloader (daemon starts automatically):"
echo "    lbry-downloader --dry-run"
echo ""
echo "3️⃣  Download content:"
echo "    lbry-downloader"
echo ""
echo "💡 If 'lbry-downloader' command not found after reload, use:"
echo "    ~/Documents/LBRY-Downloader/bin/lbry-downloader"
echo ""
echo "⚠️  If lbrynet was not installed automatically, install it from:"
echo "    https://github.com/lbryio/lbry-sdk/releases"
echo "    Then run: lbrynet start"
echo "    ~/Documents/LBRY-Downloader/bin/lbry-downloader"
echo ""
echo "📁 Config file: ~/Documents/lbry-downloads/config.yaml"
echo ""
