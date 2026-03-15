# Quick Start Guide

## One-Line Install

```bash
curl -fsSL https://raw.githubusercontent.com/PR0M3TH3AN/LBRY-Downloader/main/remote-install.sh -o install-lbry.sh && bash install-lbry.sh
```

**Requirements:** Git and Python 3.8+ must be installed.

## Manual Installation

```bash
# Clone or download the repository
cd LBRY-Downloader

# Install dependencies
pip install -r requirements.txt

# Initialize configuration
python init.py
```

## Configuration

Edit `~/Documents/lbry-downloads/config.yaml`:

```yaml
channels:
  - input: "https://odysee.com/@YourFavoriteChannel:1"
    enabled: true
  - input: "lbry://@AnotherChannel#5"
    enabled: true
```

## Launching

### Start the LBRY Daemon First

**Important:** The LBRY daemon must be running before using the downloader:

```bash
# Start the daemon
lbrynet start

# Check if it's running
lbrynet status
```

### Launch LBRY Downloader

**Method 1: Using the Launcher (Recommended)**
```bash
cd ~/Documents/LBRY-Downloader
./bin/lbry-downloader --dry-run
```

**Method 2: Add to PATH and run from anywhere**
```bash
# One-time setup
echo 'export PATH="$HOME/Documents/LBRY-Downloader/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Now run from anywhere
lbry-downloader --dry-run
```

**Method 3: Using Virtual Environment**
```bash
cd ~/Documents/LBRY-Downloader
source venv/bin/activate
python main.py --dry-run
```

### Common Commands

```bash
# Test what would be downloaded (dry run) - ALWAYS DO THIS FIRST
lbry-downloader --dry-run

# Actually download content
lbry-downloader

# Use custom config file
lbry-downloader --config ./my-config.yaml

# View help
lbry-downloader --help
```

## Understanding Output

```
Run complete.
Channels scanned: 2
Claims examined: 150
New downloads: 3
New versions: 1
Skipped existing: 146
Failures: 0
```

## Directory Structure

Downloads are saved to:
```
~/Documents/lbry-downloads/
  channels/
    ChannelName__abc123/
      channel.json
      claims/
        video-name__def456/
          claim.json
          versions/
            sd_hash789/
              video.mp4
              metadata.json
              download.json
              checksums.txt
```

## Troubleshooting

**"Could not connect to LBRY daemon"**
```bash
lbrynet start
```

**"Config file not found"**
```bash
python init.py
```

**"No channels enabled"**
Check that at least one channel has `enabled: true`

**Want to see more details?**
Edit config.yaml and set `log_level: "DEBUG"`

## Updates

The tool is designed to be run repeatedly. It will:
- Skip already downloaded files
- Detect new versions of existing claims
- Download only what's new or changed

## Support

See README.md for detailed documentation.
