#!/usr/bin/env python3
"""
LBRY Downloader - Non-Interactive Setup Script

For automated/testing installs. Uses environment variables or defaults.
"""

import os
import sys
import subprocess
from pathlib import Path

# Get values from environment or use defaults
INSTALL_DIR = os.environ.get(
    "LBRY_INSTALL_DIR", str(Path.home() / "Documents" / "LBRY-Downloader")
)
DOWNLOAD_DIR = os.environ.get(
    "LBRY_DOWNLOAD_DIR", str(Path.home() / "Documents" / "lbry-downloads")
)
DOWNLOAD_LIMIT = int(os.environ.get("LBRY_DOWNLOAD_LIMIT", "10"))


def run_command(cmd, check=True):
    result = subprocess.run(
        cmd, shell=True, check=check, capture_output=True, text=True
    )
    return result


print("=" * 60)
print("  LBRY Downloader - Non-Interactive Setup")
print("=" * 60)
print()

print(f"Install directory: {INSTALL_DIR}")
print(f"Download directory: {DOWNLOAD_DIR}")
print(f"Download limit: {DOWNLOAD_LIMIT}")
print()

# Create directories
Path(INSTALL_DIR).mkdir(parents=True, exist_ok=True)
Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
(Path(DOWNLOAD_DIR) / "state").mkdir(exist_ok=True)
(Path(DOWNLOAD_DIR) / "channels").mkdir(exist_ok=True)

# Setup virtual environment
venv_path = Path(INSTALL_DIR) / "venv"
if not venv_path.exists():
    print("Creating virtual environment...")
    subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
    print("✓ Virtual environment created")

# Install dependencies
print("Installing dependencies...")
pip_path = venv_path / "bin" / "pip"
subprocess.run([str(pip_path), "install", "-q", "-r", "requirements.txt"], check=True)
print("✓ Dependencies installed")

# Copy files if needed
current_dir = Path(__file__).parent.resolve()
if current_dir != Path(INSTALL_DIR):
    print("Copying files...")
    import shutil

    for pattern in ["*.py", "*.md", "*.txt", "*.toml", "*.example", "Makefile"]:
        for file in current_dir.glob(pattern):
            if file.name != "setup-noninteractive.py":
                shutil.copy2(file, INSTALL_DIR)
    tests_src = current_dir / "tests"
    tests_dst = Path(INSTALL_DIR) / "tests"
    if tests_src.exists() and not tests_dst.exists():
        shutil.copytree(tests_src, tests_dst)
    print("✓ Files copied")

# Create config
config_content = f"""# LBRY Downloader Configuration

lbrynet:
  # Only used when running with --p2p
  api_url: "http://127.0.0.1:5279"
  # Only used when running with --p2p
  timeout_seconds: 60

general:
  base_dir: "{DOWNLOAD_DIR}"
  state_file: "{DOWNLOAD_DIR}/state/database.json"
  max_workers: 2
  log_level: "INFO"
  dry_run: false
  verify_existing_files: true
  write_checksums: true
  filename_mode: "original"
  include_reposts: false
  channel_page_size: 50
  keep_missing_claim_records: true
  download_limit: {DOWNLOAD_LIMIT}

channels:
  # Add your channels here:
  # - input: "https://odysee.com/@ChannelName:1"
  #   enabled: true
  #   content_mode: "non_video_only"
"""

config_path = Path(DOWNLOAD_DIR) / "config.yaml"
config_path.write_text(config_content)
print(f"✓ Config created: {config_path}")

# Create launcher
bin_dir = Path(INSTALL_DIR) / "bin"
bin_dir.mkdir(exist_ok=True)

launcher = bin_dir / "lbry-downloader"
launcher.write_text(f"""#!/bin/bash
cd "{INSTALL_DIR}"
source venv/bin/activate
python main.py "$@"
""")
launcher.chmod(0o755)
print(f"✓ Launcher created: {launcher}")

print()
print("=" * 60)
print("✓ Setup complete!")
print("=" * 60)
print()
print(f"Config file: {config_path}")
print(f"To run: {launcher}")
print()
print("Edit the config to add channels, then run:")
print(f"  {launcher} --dry-run")
print("Recommended first real run:")
print(f"  {launcher} --non-video-only")
print("Optional local-node mode:")
print(f"  {launcher} --p2p")
