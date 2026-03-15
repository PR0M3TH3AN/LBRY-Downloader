#!/usr/bin/env python3
"""
LBRY Downloader - Uninstall Script

This script removes the LBRY Downloader installation.
It will ask for confirmation before deleting any files.
"""

import os
import sys
import shutil
from pathlib import Path


class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_success(msg: str):
    print(f"{Colors.GREEN}✓{Colors.END} {msg}")


def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠{Colors.END} {msg}")


def print_error(msg: str):
    print(f"{Colors.RED}✗{Colors.END} {msg}")


def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ{Colors.END} {msg}")


def print_header(msg: str):
    print(f"\n{Colors.BOLD}{msg}{Colors.END}")
    print("=" * 60)


def find_installation() -> Path:
    """Try to find the installation directory."""
    # Check common locations
    possible_locations = [
        Path.home() / "Documents" / "LBRY-Downloader",
        Path.home() / "LBRY-Downloader",
        Path("/opt/LBRY-Downloader"),
        Path("/usr/local/LBRY-Downloader"),
    ]

    # Check current directory
    current = Path.cwd()
    if (current / "main.py").exists() and (current / "requirements.txt").exists():
        possible_locations.insert(0, current)

    # Check if any of these exist
    for location in possible_locations:
        if location.exists() and (location / "main.py").exists():
            return location

    return None


def get_download_location() -> Path:
    """Try to find the download location from config."""
    config_paths = [
        Path.home() / "Documents" / "lbry-downloads" / "config.yaml",
        Path.home() / "lbry-downloads" / "config.yaml",
    ]

    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path) as f:
                    content = f.read()

                # Simple parsing to find base_dir
                for line in content.split("\n"):
                    if "base_dir:" in line:
                        path = line.split(":", 1)[1].strip().strip('"').strip("'")
                        if path.startswith("~"):
                            path = path.replace("~", str(Path.home()))
                        return Path(path).resolve()
            except:
                pass

    return None


def remove_directory(path: Path, description: str) -> bool:
    """Remove a directory with confirmation."""
    if not path.exists():
        print_info(f"{description} not found at {path}")
        return False

    print_warning(f"Found {description}: {path}")

    # Show size if it's a directory
    if path.is_dir():
        try:
            total_size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            size_mb = total_size / (1024 * 1024)
            print_info(f"Size: {size_mb:.1f} MB")
        except:
            pass

    response = input(f"Remove {description}? (y/N): ").strip().lower()

    if response == "y":
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            print_success(f"Removed {description}")
            return True
        except Exception as e:
            print_error(f"Failed to remove {description}: {e}")
            return False
    else:
        print_info(f"Skipped {description}")
        return False


def remove_from_path(install_dir: Path) -> None:
    """Remove launcher from PATH if it was added."""
    print_header("Checking PATH Configuration")

    bin_dir = install_dir / "bin"
    if not bin_dir.exists():
        return

    shell_rc_files = [
        Path.home() / ".bashrc",
        Path.home() / ".zshrc",
        Path.home() / ".bash_profile",
    ]

    for rc_file in shell_rc_files:
        if not rc_file.exists():
            continue

        try:
            content = rc_file.read_text()
            bin_str = str(bin_dir)

            if bin_str in content:
                print_warning(f"Found PATH modification in {rc_file}")
                print_info("You should manually remove this line from the file:")
                for i, line in enumerate(content.split("\n"), 1):
                    if bin_str in line and "PATH" in line:
                        print(f"  Line {i}: {line}")
        except:
            pass


def main():
    print(f"""
{Colors.BOLD}╔══════════════════════════════════════════════════════════════╗
║         LBRY Downloader - Uninstall Script                   ║
╚══════════════════════════════════════════════════════════════╝{Colors.END}

This script will help you uninstall LBRY Downloader.
""")

    # Find installation
    install_dir = find_installation()

    if install_dir:
        print_info(f"Found installation at: {install_dir}")
    else:
        print_warning("Could not automatically find installation")
        response = input(
            "Enter installation directory (or press Enter to skip): "
        ).strip()
        if response:
            install_dir = Path(response).expanduser().resolve()

    # Find download location
    download_dir = get_download_location()

    if download_dir:
        print_info(f"Found download location at: {download_dir}")
    else:
        default_dl = Path.home() / "Documents" / "lbry-downloads"
        if default_dl.exists():
            download_dir = default_dl
            print_info(f"Found download location at: {download_dir}")

    # Show summary and ask for confirmation
    print_header("Uninstall Summary")

    items_to_remove = []

    if install_dir and install_dir.exists():
        items_to_remove.append(("Installation", install_dir))

    if download_dir and download_dir.exists():
        items_to_remove.append(("Downloads", download_dir))

    if not items_to_remove:
        print_info("Nothing found to uninstall")
        return

    print("The following items will be removed:")
    for name, path in items_to_remove:
        print(f"  - {name}: {path}")

    print()
    print_warning("This action cannot be undone!")
    response = input("\nProceed with uninstallation? (yes/no): ").strip().lower()

    if response != "yes":
        print_info("Uninstallation cancelled")
        return

    # Remove items
    print_header("Removing Files")

    for name, path in items_to_remove:
        remove_directory(path, name)

    # Check PATH
    if install_dir:
        remove_from_path(install_dir)

    # Summary
    print_header("Uninstallation Complete")
    print_success("LBRY Downloader has been removed from your system")

    print("\nOptional cleanup:")
    print("  - Remove lbrynet if you no longer need it")
    print("  - Remove any cron jobs you may have set up")
    print("  - Remove PATH modifications from your shell config")

    print("\nThank you for trying LBRY Downloader!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nUninstallation cancelled")
        sys.exit(1)
    except Exception as e:
        print_error(f"Uninstallation failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
