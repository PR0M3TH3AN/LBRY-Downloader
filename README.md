# LBRY Downloader

A Python tool that incrementally syncs downloadable file claims from configured LBRY/Odysee channels into a structured local archive.

## Recommended Defaults

For most users:

- Files only: `lbry-downloader --non-video-only`
- Videos only: `lbry-downloader --video-only`
- Mixed per-channel behavior: set `content_mode` in `config.yaml` and run `lbry-downloader`
- Optional local-node mode: `lbry-downloader --p2p`

## Features

- **Incremental Sync**: Only downloads new claims and updated versions
- **Version Preservation**: Keeps old versions instead of overwriting them
- **Robust Identity**: Uses stable LBRY claim IDs, not display names or titles
- **Atomic State**: Database writes are atomic to prevent corruption
- **Direct Mode by Default**: Uses Odysee's public proxy + CDN without requiring a local node
- **Optional P2P Mode**: Can use a local `lbrynet` daemon when explicitly requested
- **Streaming Fallback**: Automatically uses daemon's streaming endpoint when P2P peers are unavailable
- **Flexible Input**: Accepts Odysee URLs, LBRY URIs, or claim IDs
- **Audit Trail**: Maintains run history in JSONL format
- **Dry-Run Mode**: Test what would happen without downloading
- **Offline Archive Site**: Builds a static browseable website from the download tree, including channel/claim metadata and local file links
- **Metadata Backfill**: Skipped existing downloads still get missing `channel.json`, `claim.json`, `metadata.json`, and image assets when available

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
- ✅ Set up a Python virtual environment
- ✅ Install Python packages
- ✅ Ask for your download location
- ✅ Configure channels to download from
- ✅ Set download limits
- ✅ Create launcher scripts
- ✅ Prepare a direct-first downloader setup that works without a local node
- ✅ Leave `lbrynet` as an optional install only for users who want `--p2p`

**Important:** Direct mode is now the default and does not require `lbrynet`.

If you choose to use `--p2p`, then `lbrynet` requires syncing blockchain **headers** (not full blocks) on first use:
- Downloads ~1.7 million block headers (takes 5-10 minutes)
- Uses minimal storage (headers only, not full blockchain)
- Subsequent starts are much faster
- This is only needed for the optional node-backed mode

### Manual Install

See [LINUX_SETUP.md](LINUX_SETUP.md) for detailed manual installation instructions.

### Uninstall

To remove LBRY Downloader:

```bash
./uninstall.py
```

## Prerequisites

Direct mode is the default, so a local LBRY daemon is not required for normal use.

If you want to use P2P mode explicitly with `--p2p`, then you need to have the LBRY SDK daemon (`lbrynet`) installed and running:

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
  build_offline_site: true
  offline_site_dir: "~/Documents/lbry-downloads/site"
  fetch_missing_metadata_assets: true
  include_reposts: false
  direct_base_urls:
    - "https://odysee.com"
  direct_max_retries_per_url: 2
  direct_retry_backoff_seconds: 2.0
  direct_auto_fallback_to_p2p: false

channels:
  - input: "https://odysee.com/@SomeChannel:1"
    enabled: true
    content_mode: "all"
  - input: "lbry://@AnotherChannel#5"
    enabled: true
    content_mode: "non_video_only"
```

When `build_offline_site` is enabled, the downloader writes a generated static site under `offline_site_dir` after each non-dry run. The site reflects the existing archive structure and links back to the real downloaded files under each channel/claim/version folder.

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

### Per-Channel Content Mode

You can control the download type for each channel independently.

```yaml
channels:
  - input: "https://odysee.com/@VideoChannel:1"
    enabled: true
    content_mode: "video_only"

  - input: "https://odysee.com/@FileArchive:1"
    enabled: true
    content_mode: "non_video_only"

  - input: "https://odysee.com/@MixedChannel:1"
    enabled: true
    content_mode: "all"
```

Available values:

- `all`: Download both video and non-video files for that channel.
- `video_only`: Download only video files such as `.mp4`, `.webm`, and `.mkv`.
- `non_video_only`: Download only non-video files such as `.zip`, PDFs, and similar file claims.

Precedence:

- Per-channel `content_mode` is the normal default for that channel.
- CLI flags `--video-only` and `--non-video-only` override all channels for a single run.

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

### Direct-Mode Rate Limit Fallbacks

If Odysee starts returning `429 Too Many Requests`, you can tune the direct downloader instead of hardcoding random public mirrors.

```yaml
general:
  direct_base_urls:
    - "https://odysee.com"
    # - "https://your-mirror.example"
  direct_max_retries_per_url: 2
  direct_retry_backoff_seconds: 2.0
  direct_auto_fallback_to_p2p: false
```

What these do:

- `direct_base_urls`: direct download bases to try in order. Odysee should normally stay first.
- `direct_max_retries_per_url`: how many retries to allow after HTTP `429` for the same direct URL.
- `direct_retry_backoff_seconds`: base delay for exponential backoff after HTTP `429`.
- `direct_auto_fallback_to_p2p`: if `true`, a direct-mode run will try the local `lbrynet` daemon after repeated rate-limit failures.

Recommended pattern:

- Keep `https://odysee.com` first.
- Add your own mirror only if you actually control or trust it.
- Turn on `direct_auto_fallback_to_p2p: true` only if you also maintain a working local node.

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

**Important:** If you are using `--p2p`, make sure the LBRY daemon is running first:

```bash
# Start the daemon
lbrynet start

# Check if it's running
lbrynet status
```

## Usage

### Recommended Default: Direct + Non-Video Downloads Only

If your main goal is to archive file attachments such as `.zip` bundles and skip video files such as `.mp4`, this should be the primary command you use:

```bash
python3 main.py --non-video-only
```

This mode keeps non-video claim downloads and skips video claims before the per-channel download limit is applied.

### Common Commands

```bash
# Recommended default: download only non-video files such as zip archives
python3 main.py --non-video-only

# Download only video files such as mp4/webm/mkv
python3 main.py --video-only

# Download everything supported by the tool
python3 main.py

# Preview what would be downloaded without downloading anything
python3 main.py --dry-run

# Preview only non-video downloads
python3 main.py --dry-run --non-video-only

# Use a custom config file
python3 main.py --config ./my-config.yaml

# Run explicitly in direct mode (normally unnecessary because this is the default)
python3 main.py --direct

# Use the local LBRY daemon and P2P network instead of direct mode
python3 main.py --p2p

# Use P2P mode but keep only non-video files
python3 main.py --p2p --non-video-only

# Use P2P mode but keep only video files
python3 main.py --p2p --video-only
```

### Flag Reference

- `--non-video-only`: Download only non-video claims such as `.zip`, PDFs, and other non-video files.
- `--video-only`: Download only video claims such as `.mp4`, `.webm`, and `.mkv`.
- `--dry-run`: Show what would be downloaded without changing anything.
- `--direct`: Use direct mode explicitly. This is already the default.
- `--p2p`: Use the local LBRY daemon and peer-to-peer network instead of the default direct mode.
- `--config PATH`: Use a config file other than `~/Documents/lbry-downloads/config.yaml`.

If you configure `content_mode` per channel, you usually only need the CLI content flags when you want a temporary run-wide override.

### Running Through the Launcher

If you installed the launcher script, the same commands work there too:

```bash
lbry-downloader --non-video-only
lbry-downloader --video-only
lbry-downloader --dry-run --non-video-only
lbry-downloader --p2p --non-video-only
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

This only applies when you are using `--p2p`. Direct mode does not require a local daemon.

### "Config file not found"
Create a config at the default location or specify a path:
```bash
python3 main.py --config ./config.yaml
```

### Dry run shows no downloads
Check that your channels are enabled and have downloadable content (streams, not just reposts).

### HTTP 429 / Too Many Requests

If direct mode is being rate-limited:

1. Reduce how aggressively you rerun the downloader.
2. Increase `direct_retry_backoff_seconds`.
3. Keep `direct_max_retries_per_url` modest, such as `2` or `3`.
4. Add a trusted mirror to `direct_base_urls` if you actually have one.
5. Enable `direct_auto_fallback_to_p2p: true` if you want automatic fallback to the local node when direct mode keeps hitting `429`.

## Architecture

- `main.py` - Entry point and orchestration
- `lbry_client.py` - JSON-RPC daemon communication
- `config_loader.py` - Configuration parsing
- `state_db.py` - Persistent state management
- `planner.py` - Download decision logic
- `downloader.py` - Download execution with P2P + streaming fallback
- `models.py` - Data structures
- `utils.py` - Helper functions

## How Downloads Work

The downloader supports two transport modes:

1. **Direct mode (default)**: Uses Odysee's public proxy for metadata and Odysee CDN for the actual download
2. **P2P mode (`--p2p`)**: Uses the local LBRY daemon and peer-to-peer network, with daemon streaming fallback when peers are unavailable

Direct mode is the intended default for most users. P2P mode remains available when you specifically want node-backed downloading.

## License

MIT License
