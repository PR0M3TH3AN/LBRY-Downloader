#!/usr/bin/env python3
"""
Initialize Odysee/LBRY Downloader configuration.

This script creates the initial configuration file and directory structure.
"""

import sys
from pathlib import Path

from config_loader import create_default_config, ensure_directories
from models import Config, GeneralConfig, LbrynetConfig
from utils import expand_path


def main():
    print("Odysee/LBRY Downloader - Initialization")
    print("=" * 40)

    # Default paths
    base_dir = expand_path("~/Documents/lbry-downloads")
    config_file = base_dir / "config.yaml"

    # Check if already exists
    if config_file.exists():
        print(f"\nConfiguration already exists at: {config_file}")
        response = input("Overwrite? (y/N): ").strip().lower()
        if response != "y":
            print("Aborted.")
            sys.exit(0)

    # Create default config
    config_content = create_default_config()

    # Create directories
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "state").mkdir(exist_ok=True)
    (base_dir / "channels").mkdir(exist_ok=True)

    # Write config
    with open(config_file, "w") as f:
        f.write(config_content)

    print(f"\n✓ Created configuration: {config_file}")
    print(f"✓ Created directories:")
    print(f"  - {base_dir}")
    print(f"  - {base_dir / 'state'}")
    print(f"  - {base_dir / 'channels'}")

    print("\n" + "=" * 40)
    print("Next steps:")
    print("1. Edit the configuration file to add your channels")
    print(f"   nano {config_file}")
    print("\n2. Test first with dry-run:")
    print("   python main.py --dry-run")
    print("\n3. Recommended first real run:")
    print("   python main.py --non-video-only")
    print("\n4. Optional P2P mode if you want the local node path:")
    print("   lbrynet start")
    print("   python main.py --p2p")
    print("=" * 40)


if __name__ == "__main__":
    main()
