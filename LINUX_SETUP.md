# Linux Setup Guide (Debian/Ubuntu/Mint)

Complete instructions for setting up LBRY Downloader on Debian-based Linux distributions.

## One-Line Install (Easiest)

Install with a single command using curl:

```bash
curl -fsSL https://raw.githubusercontent.com/PR0M3TH3AN/LBRY-Downloader/main/remote-install.sh | bash
```

**Requirements:** Git and Python 3.8+ must be installed.

**What this does:**
1. Downloads the repository
2. Runs the interactive setup script
3. Configures everything automatically

## Interactive Setup

If you prefer to clone manually, use the interactive setup script:

```bash
# Clone the repository
git clone https://github.com/PR0M3TH3AN/LBRY-Downloader.git
cd LBRY-Downloader

# Run the interactive installer
./setup.py
```

This script will:
1. Check and install system dependencies
2. Set up a Python virtual environment
3. Install Python packages
4. Ask for your download location
5. Configure channels to download from
6. Set download limits
7. Create launcher scripts

**Want to uninstall later?** Just run `./uninstall.py`

---

## Manual Installation

If you prefer to set things up manually, follow the steps below.

## Prerequisites

### 1. System Packages

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and required system packages
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget

# Verify Python installation
python3 --version  # Should be 3.8 or higher
pip3 --version
```

### 2. Install LBRY SDK (lbrynet daemon)

The LBRY SDK is required to communicate with the LBRY network.

#### Option A: Download Pre-built Binary (Recommended)

```bash
# Create directory for lbrynet
mkdir -p ~/.local/bin
cd ~/.local/bin

# Download latest release (check https://github.com/lbryio/lbry-sdk/releases for latest)
# For x86_64 systems:
LBRY_VERSION="0.113.0"  # Check for latest version
wget "https://github.com/lbryio/lbry-sdk/releases/download/v${LBRY_VERSION}/lbry-sdk-linux.zip"

# Extract
unzip lbry-sdk-linux.zip
rm lbry-sdk-linux.zip

# Make executable
chmod +x lbrynet

# Add to PATH if not already there
if ! echo $PATH | grep -q "$HOME/.local/bin"; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    source ~/.bashrc
fi

# Verify installation
lbrynet --version
```

#### Option B: Build from Source (Advanced)

```bash
# Install build dependencies
sudo apt install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    python3-venv

# Clone and build (not recommended for most users)
git clone https://github.com/lbryio/lbry-sdk.git
cd lbry-sdk
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

## Installation

### 1. Clone the Repository

```bash
# Navigate to where you want to install
cd ~/Documents  # or wherever you prefer

# Clone (if you have git access) or extract the zip
git clone https://github.com/yourusername/LBRY-Downloader.git
# OR if you downloaded a zip:
# unzip LBRY-Downloader.zip -d LBRY-Downloader

cd LBRY-Downloader
```

### 2. Set Up Python Environment

```bash
# Option A: Using system Python (simpler)
pip3 install --user -r requirements.txt

# Option B: Using virtual environment (recommended for developers)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Verify Installation

```bash
# Test Python imports
python3 -c "from main import run_sync; print('✓ Imports OK')"

# Test CLI
python3 main.py --help
```

## Configuration

### 1. Initialize Configuration

```bash
# Run initialization script
python3 init.py

# This creates:
# ~/Documents/lbry-downloads/config.yaml
# ~/Documents/lbry-downloads/state/
# ~/Documents/lbry-downloads/channels/
```

### 2. Edit Configuration

```bash
# Open config in your preferred editor
nano ~/Documents/lbry-downloads/config.yaml
# OR
gedit ~/Documents/lbry-downloads/config.yaml
# OR
vim ~/Documents/lbry-downloads/config.yaml
```

### 3. Add Your Channels

Edit the `channels:` section:

```yaml
channels:
  - input: "https://odysee.com/@SomeChannel:1"
    enabled: true
    tags_include: []
    tags_exclude: []
  
  - input: "lbry://@AnotherChannel#5"
    enabled: true
    tags_include: []
    tags_exclude: []
```

**Finding Channel URLs:**
- Go to Odysee.com and navigate to a channel
- Copy the URL from your browser
- Paste it into the config

### 4. Configure Per-Channel Download Locations (Optional)

By default, all downloads go to `~/Documents/lbry-downloads/channels/`. You can specify custom locations for each channel:

```yaml
channels:
  # Downloads to default location
  - input: "https://odysee.com/@RegularChannel:1"
    enabled: true
  
  # Downloads to custom location (external drive)
  - input: "https://odysee.com/@LargeVideos:1"
    enabled: true
    download_path: "/mnt/media/videos"
  
  # Downloads to custom location (home directory)
  - input: "https://odysee.com/@Music:1"
    enabled: true
    download_path: "~/Music/LBRY"
```

**Why use custom locations?**
- Store large channels on external drives
- Organize content by type (videos, music, etc.)
- Manage disk space across multiple drives
- Keep important channels on fast SSD, archive on slow HDD

**Note:** Make sure the custom path exists and you have write permissions:
```bash
mkdir -p /mnt/media/videos
# Check permissions
ls -la /mnt/media/
```

### 5. Configure Download Limits (Optional)

Limit how many new items to download per channel. This is especially useful for:
- **Testing** - Download just a few files first
- **Large channels** - Channels with thousands of videos
- **Bandwidth control** - Limit data usage per run

```yaml
general:
  # Default: download 10 most recent items per channel
  download_limit: 10
  
  # To download everything (use with caution!):
  # download_limit: 0
  
  # For testing, download only 2-3 items:
  # download_limit: 3
```

The tool downloads **most recent items first** (sorted by publish date), so:
- `download_limit: 10` = Download the 10 newest videos
- Older items remain in the channel but won't be downloaded yet
- On next run, it will download the next 10 (if new items were published)

**Recommended approach for large channels:**
```yaml
general:
  download_limit: 10  # Start with a small number

channels:
  - input: "https://odysee.com/@HugeArchive:1"
    enabled: true
    # Downloads only 10 most recent to test
```

Once you're happy with how it works, increase the limit or set to 0.

## Running the Daemon

The LBRY daemon (`lbrynet`) must be running before using the downloader.

### Start the Daemon

```bash
# Start lbrynet
lbrynet start

# Check status
lbrynet status

# You should see JSON output with daemon information
```

### Running as a Systemd Service (Optional)

Create a systemd service to auto-start lbrynet:

```bash
# Create service file
sudo tee /etc/systemd/system/lbrynet.service > /dev/null <<EOF
[Unit]
Description=LBRY SDK Daemon
After=network.target

[Service]
Type=simple
User=$USER
ExecStart=$HOME/.local/bin/lbrynet start
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable lbrynet
sudo systemctl start lbrynet

# Check status
sudo systemctl status lbrynet

# View logs
sudo journalctl -u lbrynet -f
```

### Stop the Daemon

```bash
# If running manually
lbrynet stop

# If running as systemd service
sudo systemctl stop lbrynet
```

## Using the Downloader

### First Run (Dry Run)

Always test with dry-run first:

```bash
cd ~/Documents/LBRY-Downloader  # or wherever you installed it

python3 main.py --dry-run
```

This shows what would be downloaded without actually downloading anything.

### Normal Run

```bash
# Make sure lbrynet is running
lbrynet status

# Run the downloader
python3 main.py
```

### Custom Config Location

```bash
python3 main.py --config /path/to/custom/config.yaml
```

### Viewing Progress

The tool outputs progress to the console:

```
2024-03-15 14:30:00 - INFO - LBRY Downloader starting
2024-03-15 14:30:01 - INFO - Daemon is healthy
2024-03-15 14:30:02 - INFO - Resolved channel: @SomeChannel (abc123...)
2024-03-15 14:30:05 - INFO -   Total claims found: 150
2024-03-15 14:30:06 - INFO - New claim: interesting-video (download_new)
...

Run complete.
Channels scanned: 2
Claims examined: 150
New downloads: 3
New versions: 1
Skipped existing: 146
Failures: 0
```

## Directory Structure

After running, your downloads will be organized as:

```
~/Documents/lbry-downloads/
├── config.yaml                    # Your configuration
├── state/
│   ├── database.json             # State database (don't edit)
│   └── run-history.jsonl         # Audit log
└── channels/
    └── SomeChannel__abc123/      # Channel folder
        ├── channel.json          # Channel metadata
        └── claims/
            └── interesting-video__def456/
                ├── claim.json    # Claim metadata
                └── versions/
                    └── sd_abc789/
                        ├── interesting-video.mp4
                        ├── metadata.json
                        ├── download.json
                        └── checksums.txt
```

## Automation (Optional)

### Create a Wrapper Script

```bash
# Create convenient wrapper
tee ~/bin/lbry-sync > /dev/null <<'EOF'
#!/bin/bash
cd ~/Documents/LBRY-Downloader
source venv/bin/activate 2>/dev/null || true

# Check if lbrynet is running
if ! curl -s http://127.0.0.1:5279 > /dev/null 2>&1; then
    echo "Starting lbrynet daemon..."
    lbrynet start &
    sleep 5
fi

# Run downloader
python3 main.py "$@"
EOF

chmod +x ~/bin/lbry-sync

# Now you can just run:
# lbry-sync
# lbry-sync --dry-run
```

### Cron Job for Regular Syncs

```bash
# Edit crontab
crontab -e

# Add line to run daily at 3 AM:
0 3 * * * cd ~/Documents/LBRY-Downloader && python3 main.py >> ~/lbry-sync.log 2>&1

# Or weekly on Sundays at 2 AM:
0 2 * * 0 cd ~/Documents/LBRY-Downloader && python3 main.py >> ~/lbry-sync.log 2>&1
```

## Troubleshooting

### "Could not connect to LBRY daemon"

```bash
# Check if lbrynet is running
lbrynet status

# If not running, start it
lbrynet start

# Check if it's listening on the expected port
netstat -tlnp | grep 5279
# OR
ss -tlnp | grep 5279

# Check daemon logs (if running as systemd)
sudo journalctl -u lbrynet -n 50
```

### "Permission denied" when running lbrynet

```bash
# Ensure lbrynet is executable
chmod +x ~/.local/bin/lbrynet

# Check PATH
echo $PATH
# Should include /home/YOURUSERNAME/.local/bin
```

### "ModuleNotFoundError" for Python packages

```bash
# Reinstall dependencies
cd ~/Documents/LBRY-Downloader

# If using system Python:
pip3 install --user --force-reinstall -r requirements.txt

# If using venv:
source venv/bin/activate
pip install --force-reinstall -r requirements.txt
```

### "Config file not found"

```bash
# Run initialization again
python3 init.py

# Or manually create the directory
mkdir -p ~/Documents/lbry-downloads/state
mkdir -p ~/Documents/lbry-downloads/channels

# And create a config file from the example
cp config.yaml.example ~/Documents/lbry-downloads/config.yaml
```

### Downloads are slow

LBRY downloads can be slow depending on network conditions. This is normal:

```yaml
# In config.yaml, reduce max_workers if needed
general:
  max_workers: 1  # Download one at a time
  timeout_seconds: 300  # Increase timeout
```

### Disk space issues

Check the download directory size:

```bash
du -sh ~/Documents/lbry-downloads/channels/
du -sh ~/Documents/lbry-downloads/channels/* | sort -hr | head -20
```

## Updating

### Update the Downloader

```bash
cd ~/Documents/LBRY-Downloader

# If using git:
git pull

# If manual download, re-download and replace files

# Update Python dependencies
pip3 install --user --upgrade -r requirements.txt
# OR if using venv:
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

### Update lbrynet

```bash
# Stop current daemon
lbrynet stop

# Download new version (see installation section)
cd ~/.local/bin
# ... download and extract new version ...

# Restart
lbrynet start
```

## Uninstallation

```bash
# Stop daemon
lbrynet stop

# Remove downloader
rm -rf ~/Documents/LBRY-Downloader
rm -rf ~/Documents/lbry-downloads

# Remove lbrynet (if installed locally)
rm ~/.local/bin/lbrynet

# Remove systemd service (if created)
sudo systemctl stop lbrynet
sudo systemctl disable lbrynet
sudo rm /etc/systemd/system/lbrynet.service
sudo systemctl daemon-reload

# Remove cron job
crontab -e
# Delete the line with lbry-downloader
```

## Getting Help

1. Check the logs: `~/Documents/lbry-downloads/state/run-history.jsonl`
2. Run with debug logging: Set `log_level: "DEBUG"` in config.yaml
3. Test daemon connectivity:
   ```bash
   curl -X POST http://127.0.0.1:5279 \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"status","params":{},"id":1}'
   ```

## Uninstallation

To remove LBRY Downloader:

```bash
# Run the uninstall script
./uninstall.py
```

This will:
- Find your installation and download directories
- Ask for confirmation before removing
- Show you what's being deleted
- Optionally help clean up PATH entries

**Manual uninstall:**

```bash
# Stop the daemon
lbrynet stop

# Remove installation directory
rm -rf ~/Documents/LBRY-Downloader

# Remove downloads (optional - backup first!)
rm -rf ~/Documents/lbry-downloads

# Remove lbrynet (optional)
rm ~/.local/bin/lbrynet

# Remove from PATH if you added it
# Edit ~/.bashrc and remove the lbry-downloader PATH line
```

## Launching the Application

After installation, there are several ways to launch LBRY Downloader:

### Method 1: Launcher Script (Recommended)

The setup script creates launcher scripts in `~/Documents/LBRY-Downloader/bin/`:

```bash
# Navigate to install directory
cd ~/Documents/LBRY-Downloader

# Run the downloader
./bin/lbry-downloader --dry-run

# Or run without changing directory
~/Documents/LBRY-Downloader/bin/lbry-downloader --dry-run
```

### Method 2: Add to PATH

Add the bin directory to your PATH to run from anywhere:

```bash
# Add to PATH (one-time setup)
echo 'export PATH="$HOME/Documents/LBRY-Downloader/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Now run from any directory
lbry-downloader --dry-run
lbry-downloader
```

### Method 3: Using Virtual Environment

```bash
cd ~/Documents/LBRY-Downloader
source venv/bin/activate
python main.py --dry-run
```

### Method 4: Quick Test

```bash
cd ~/Documents/LBRY-Downloader
./bin/lbry-test  # Automatically runs with --dry-run
```

### Prerequisites: Start the Daemon

**Important:** Always start the LBRY daemon before running the downloader:

```bash
# Check if daemon is running
lbrynet status

# Start if not running
lbrynet start

# Or if using systemd
sudo systemctl start lbrynet
```

## Quick Reference

```bash
# Automated Setup (one-time)
curl -fsSL https://raw.githubusercontent.com/PR0M3TH3AN/LBRY-Downloader/main/remote-install.sh -o install-lbry.sh && bash install-lbry.sh

# Manual Setup (one-time)
sudo apt install python3 python3-pip
pip3 install --user -r requirements.txt
python3 init.py

# Daily use
lbrynet start                                          # Start daemon
~/Documents/LBRY-Downloader/bin/lbry-downloader --dry-run  # Test first
~/Documents/LBRY-Downloader/bin/lbry-downloader            # Run sync
lbrynet stop                                           # Stop daemon (optional)

# Or if in PATH
lbry-downloader --dry-run
lbry-downloader

# Locations
Install:   ~/Documents/LBRY-Downloader/
Config:    ~/Documents/lbry-downloads/config.yaml
Downloads: ~/Documents/lbry-downloads/channels/
State:     ~/Documents/lbry-downloads/state/
Logs:      ~/Documents/lbry-downloads/state/run-history.jsonl
```
