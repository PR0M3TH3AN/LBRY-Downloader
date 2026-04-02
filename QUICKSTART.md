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

### Finding Channel URLs (from Odysee)

1. Go to https://odysee.com
2. Search for and navigate to the channel you want
3. Copy the URL from your browser's address bar
   - Example: `https://odysee.com/@TechChannel:1`
4. Add it to your config.yaml

### Edit Config File

Edit `~/Documents/lbry-downloads/config.yaml`:

```yaml
channels:
  - input: "https://odysee.com/@YourFavoriteChannel:1"
    enabled: true
    content_mode: "non_video_only"
  - input: "https://odysee.com/@AnotherChannel:5"
    enabled: true
    content_mode: "video_only"
```

**Tip:** Just paste the Odysee URL exactly as it appears in your browser!

### Per-Channel Content Mode

You can choose what each channel downloads:

- `content_mode: "all"` downloads video and non-video files
- `content_mode: "video_only"` downloads only video files
- `content_mode: "non_video_only"` downloads only zip/PDF/other non-video files

Most users who want file bundles and archives should start with:

```yaml
channels:
  - input: "https://odysee.com/@YourFavoriteChannel:1"
    enabled: true
    content_mode: "non_video_only"
```

## Launching

### Optional: Start the LBRY Daemon First

You only need the LBRY daemon if you plan to use `--p2p`. The default direct mode does not require it.

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

# Recommended default: download only non-video files such as zip bundles
lbry-downloader --non-video-only

# Actually download using each channel's configured content_mode
lbry-downloader

# Download only videos for every channel for this run
lbry-downloader --video-only

# Download only non-video files for every channel for this run
lbry-downloader --non-video-only

# Use the local LBRY node instead of the default direct mode
lbry-downloader --p2p

# Use custom config file
lbry-downloader --config ./my-config.yaml

# View help
lbry-downloader --help
```

CLI flags `--video-only` and `--non-video-only` override per-channel `content_mode` for that run only. `--p2p` overrides the default direct transport mode for that run only.

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

### Download Process

When downloading, you'll see one of these patterns:

**Fast Download (P2P Available):**
```
📥 Downloading: ExampleFile
   File appeared: ExampleFile.zip
✓ Downloaded: ExampleFile -> ExampleFile.zip
```

**Streaming Download (No P2P Peers):**
```
⏳ P2P download incomplete, trying daemon streaming endpoint...
📥 Downloading: ExampleFile
   Size: 28.61 MB
   [████████████████████████░░░░░░░░░░░░░░░░] 62%
✓ Download complete: ExampleFile.zip
```

The tool automatically handles both scenarios - you don't need to do anything special!

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

This only applies when you are using `--p2p`. Default direct mode does not require `lbrynet`.

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
