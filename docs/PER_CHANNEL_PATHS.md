# Per-Channel Download Paths Example

This example shows how to configure different download locations for each channel.

## Use Case: Organize by Content Type

```yaml
lbrynet:
  api_url: "http://127.0.0.1:5279"

general:
  base_dir: "~/Documents/lbry-downloads"
  max_workers: 2

channels:
  # Tech videos go to external drive
  - input: "https://odysee.com/@TechChannel:1"
    enabled: true
    download_path: "/mnt/media/videos/tech"
  
  # Music goes to Music folder
  - input: "https://odysee.com/@MusicChannel:1"
    enabled: true
    download_path: "~/Music/LBRY"
  
  # Podcasts go to Podcasts folder  
  - input: "https://odysee.com/@PodcastChannel:1"
    enabled: true
    download_path: "~/Podcasts"
  
  # Everything else goes to default location
  - input: "https://odysee.com/@MiscChannel:1"
    enabled: true
    # No download_path - uses general.base_dir/channels/
```

## Use Case: Manage Disk Space

```yaml
channels:
  # Large archive channel goes to big external drive
  - input: "https://odysee.com/@Archive:1"
    enabled: true
    download_path: "/mnt/8tb-drive/archive"
  
  # Frequently accessed channel goes to fast SSD
  - input: "https://odysee.com/@DailyUpdates:1"
    enabled: true
    download_path: "~/Videos/daily"
```

## Use Case: Separate Personal and Work

```yaml
channels:
  # Work-related content
  - input: "https://odysee.com/@TechTalks:1"
    enabled: true
    download_path: "~/Work/Videos"
  
  # Personal entertainment
  - input: "https://odysee.com/@Entertainment:1"
    enabled: true
    download_path: "~/Videos/entertainment"
```

## Setting Up Custom Paths

### 1. Create the directories

```bash
# External drive example
sudo mkdir -p /mnt/media/videos/tech
sudo chown $USER:$USER /mnt/media/videos/tech

# Home directory example
mkdir -p ~/Music/LBRY
mkdir -p ~/Podcasts
```

### 2. Edit config.yaml

```bash
nano ~/Documents/lbry-downloads/config.yaml
```

### 3. Test with dry-run

```bash
python main.py --dry-run
```

Check the output to see where files would be downloaded.

### 4. Run the download

```bash
python main.py
```

## Resulting Directory Structure

With the example above, your files will be organized as:

```
/mnt/media/videos/tech/
  TechChannel__abc123/
    channel.json
    claims/
      video1__def456/
        versions/
          sd_xyz789/
            video.mp4

~/Music/LBRY/
  MusicChannel__ghi789/
    channel.json
    claims/
      song1__jkl012/
        versions/
          sd_mno345/
            song.mp3

~/Podcasts/
  PodcastChannel__pqr678/
    ...

~/Documents/lbry-downloads/channels/
  MiscChannel__stu901/
    ...
```

## Tips

1. **Path expansion**: Use `~` for home directory - it will be expanded automatically
2. **Absolute paths**: Always use absolute paths for external drives
3. **Permissions**: Ensure you have write permissions to custom paths
4. **Existing downloads**: If you move a channel's download location after files have been downloaded, the tool will redownload them to the new location

## State Management

The state database still lives in `~/Documents/lbry-downloads/state/` regardless of where you download files. This keeps all metadata and tracking in one place.
