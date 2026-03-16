# LBRY Downloader

A Python tool that incrementally syncs downloadable file claims from configured LBRY/Odysee channels into a structured local archive.

## Features

- **Incremental Sync**: Only downloads new claims and updated versions
- **Version Preservation**: Keeps old versions instead of overwriting them
- **Robust Identity**: Uses stable LBRY claim IDs, not display names or titles
- **Atomic State**: Database writes are atomic to prevent corruption
- **Daemon-Based**: Talks directly to local `lbrynet` daemon via JSON-RPC
- **Flexible Input**: Accepts Odysee URLs, LBRY URIs, or claim IDs
- **Audit Trail**: Maintains run history in JSONL format
- **Dry-Run Mode**: Test what would happen without downloading

## Installation

### One-Line Install (Easiest)

Install with a single command:

```bash
curl -fsSL https://raw.githubusercontent.com/PR0M3TH3AN/LBRY-Downloader/main/remote-install.sh -o install-lbry.sh && bash install-lbry.sh
```

**Requirements:** Git and Python 3.8+ must be installed.

### Easy Install (Recommended)

Run the interactive setup script that handles everything:

```bash
# Clone the repository
git clone https://github.com/PR0M3TH3AN/LBRY-Downloader.git
cd LBRY-Downloader

# Run the interactive installer
./setup.py
```

The setup script will:
- ✅ Check and install system dependencies
- ✅ Download and install LBRY SDK (lbrynet) - **No blockchain sync required!**
- ✅ Set up a Python virtual environment
- ✅ Install Python packages
- ✅ Ask for your download location
- ✅ Configure channels to download from
- ✅ Set download limits
- ✅ Create launcher scripts

**Note:** The LBRY SDK is a light client - it connects to the network and downloads content **without** needing to sync the entire blockchain (unlike Bitcoin). It only downloads the content you request.

### Manual Install

See [LINUX_SETUP.md](LINUX_SETUP.md) for detailed manual installation instructions.

### Uninstall

To remove LBRY Downloader:

```bash
./uninstall.py
```

## Prerequisites

You need to have the LBRY SDK daemon (`lbrynet`) installed and running:

```bash
# The daemon should be accessible at http://127.0.0.1:5279
# Check if it's running:
curl -X POST http://127.0.0.1:5279 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"status","params":{},"id":1}'
```

To install `lbrynet`, see: https://lbry.com/get

## Configuration

Copy the example config and edit it:

```bash
cp config.yaml.example ~/Documents/lbry-downloads/config.yaml
# Edit the file to add your channels
```

Example configuration:

```yaml
lbrynet:
  api_url: "http://127.0.0.1:5279"
  timeout_seconds: 60

general:
  base_dir: "~/Documents/lbry-downloads"
  max_workers: 2
  dry_run: false
  include_reposts: false

channels:
  - input: "https://odysee.com/@SomeChannel:1"
    enabled: true
  - input: "lbry://@AnotherChannel#5"
    enabled: true
```

### Finding Channel URLs

**Yes, you can get channel info from Odysee!** Here's how:

#### Method 1: From Odysee Website (Easiest)

1. Go to https://odysee.com
2. Search for the channel you want to download from
3. Click on the channel name to go to the channel page
4. Copy the URL from your browser's address bar
   - Example: `https://odysee.com/@TechChannel:1`
   - Example: `https://odysee.com/@DocumentaryFilms:2`
5. Paste this URL into your config.yaml

#### Method 2: From Any Video Page

1. Find a video from the channel you want
2. Click on the channel name below the video
3. Copy the URL from the address bar

#### Method 3: Using LBRY Desktop App

1. Open the LBRY desktop app
2. Navigate to the channel
3. Right-click on the channel name
4. Select "Copy Link" or look at the URL bar

#### URL Formats Supported

The tool accepts multiple URL formats:

```yaml
channels:
  # Odysee URL (most common)
  - input: "https://odysee.com/@ChannelName:1"
    enabled: true
  
  # LBRY URI format
  - input: "lbry://@ChannelName#1"
    enabled: true
  
  # Short form
  - input: "@ChannelName:1"
    enabled: true
  
  # Channel claim ID (most stable)
  - input: "f3b9b2b7c1c3d8e9a1234567890abcdef123456"
    enabled: true
```

**Tip:** The Odysee URL is the easiest to find and use. Just copy-paste from your browser!

### Per-Channel Download Locations

You can specify a custom download location for each channel:

```yaml
channels:
  - input: "https://odysee.com/@TechVideos:1"
    enabled: true
    download_path: "/mnt/media/tech"  # Downloads go here instead of base_dir
  
  - input: "https://odysee.com/@Music:1"
    enabled: true
    download_path: "~/Music/LBRY"
  
  - input: "https://odysee.com/@DefaultLocation:1"
    enabled: true
    # No download_path - uses general.base_dir/channels/
```

### Download Limit

Limit how many new downloads per channel (downloads most recent first):

```yaml
general:
  # Download only 10 most recent items per channel (default)
  download_limit: 10
  
  # Or set to 0 to download everything
  # download_limit: 0
```

This is useful for:
- **Testing**: Download just a few files to verify everything works
- **Large channels**: Gradually sync channels with thousands of videos
- **Bandwidth**: Control how much data is downloaded per run

## Launching the Application

After installation, you can launch LBRY Downloader in several ways:

### Method 1: Using the Launcher Script (Recommended)

```bash
# Run from install directory
cd ~/Documents/LBRY-Downloader
./bin/lbry-downloader

# Or if you added it to your PATH (see below)
lbry-downloader
```

### Method 2: Using the Virtual Environment

```bash
cd ~/Documents/LBRY-Downloader
source venv/bin/activate
python main.py
```

### Method 3: Quick Test Script

```bash
cd ~/Documents/LBRY-Downloader
./bin/lbry-test  # Automatically runs with --dry-run
```

### Add to PATH (Run from Anywhere)

Add this to your `~/.bashrc` or `~/.zshrc`:

```bash
export PATH="$HOME/Documents/LBRY-Downloader/bin:$PATH"
```

Then reload your shell:
```bash
source ~/.bashrc  # or source ~/.zshrc
```

Now you can run `lbry-downloader` from any directory!

### Prerequisites Before Running

**Important:** Make sure the LBRY daemon is running first:

```bash
# Start the daemon
lbrynet start

# Check if it's running
lbrynet status
```

## Usage

```bash
# Run with default config
python main.py

# Use custom config
python main.py --config ./my-config.yaml

# Dry run - see what would happen
python main.py --dry-run
```

## Directory Structure

Downloads are organized as:

```
~/Documents/lbry-downloads/
  config.yaml
  state/
    database.json
    run-history.jsonl
  channels/
    <channel_name>__<channel_claim_id>/
      channel.json
      claims/
        <claim_name>__<claim_id>/
          claim.json
          versions/
            <version_token>/
              <downloaded_file>
              metadata.json
              download.json
              checksums.txt
```

## How It Works

1. **Channel Resolution**: Converts URLs/URIs to stable channel claim IDs
2. **Claim Enumeration**: Paginates through all claims in each channel
3. **Version Detection**: Uses `sd_hash` to detect updated content
4. **Smart Skipping**: Only downloads new claims or changed versions
5. **Metadata Preservation**: Stores normalized metadata beside each file

## State Management

The tool maintains state in `state/database.json`:
- Tracks which channels have been scanned
- Records claim metadata and version history
- Prevents duplicate downloads
- Detects missing files for re-download

## Troubleshooting

### "Could not connect to LBRY daemon"
Make sure `lbrynet` is running:
```bash
lbrynet start
```

### "Config file not found"
Create a config at the default location or specify a path:
```bash
python main.py --config ./config.yaml
```

### Dry run shows no downloads
Check that your channels are enabled and have downloadable content (streams, not just reposts).

## Architecture

- `main.py` - Entry point and orchestration
- `lbry_client.py` - JSON-RPC daemon communication
- `config_loader.py` - Configuration parsing
- `state_db.py` - Persistent state management
- `planner.py` - Download decision logic
- `downloader.py` - Download execution
- `models.py` - Data structures
- `utils.py` - Helper functions

## License

MIT License
