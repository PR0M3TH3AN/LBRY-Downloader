#!/usr/bin/env python3
"""
LBRY Downloader - Interactive Setup Script

This script handles:
- Dependency checking and installation
- Virtual environment setup
- Configuration with user prompts
- Download location selection
- Channel configuration
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path
from typing import Optional, List, Tuple


# Colors for terminal output
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


def run_command(
    cmd: List[str], check: bool = True, capture: bool = False
) -> Tuple[int, str, str]:
    """Run a shell command and return result."""
    try:
        if capture:
            result = subprocess.run(cmd, check=check, capture_output=True, text=True)
            return result.returncode, result.stdout, result.stderr
        else:
            result = subprocess.run(cmd, check=check)
            return result.returncode, "", ""
    except subprocess.CalledProcessError as e:
        if check:
            raise
        return e.returncode, "", str(e)
    except FileNotFoundError:
        if check:
            raise
        return 1, "", f"Command not found: {cmd[0]}"


def check_python_version() -> bool:
    """Check if Python version is 3.8 or higher."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print_error(f"Python 3.8+ required, found {version.major}.{version.minor}")
        return False
    print_success(f"Python {version.major}.{version.minor}.{version.micro} found")
    return True


def check_system_dependencies() -> bool:
    """Check if required system packages are available."""
    print_header("Checking System Dependencies")

    missing = []

    # Check for apt (Debian-based)
    if shutil.which("apt-get"):
        print_success("Package manager (apt-get) found")
    elif shutil.which("dnf"):
        print_success("Package manager (dnf) found")
    elif shutil.which("pacman"):
        print_success("Package manager (pacman) found")
    else:
        print_warning("No recognized package manager found")

    # Check for git
    if shutil.which("git"):
        print_success("Git found")
    else:
        print_warning("Git not found (optional)")

    # Check for curl
    if shutil.which("curl"):
        print_success("curl found")
    else:
        missing.append("curl")

    return len(missing) == 0


def install_system_dependencies() -> bool:
    """Install required system packages."""
    print_header("Installing System Dependencies")

    packages = ["python3-pip", "python3-venv"]

    if shutil.which("apt-get"):
        # Debian/Ubuntu/Mint
        cmd = ["sudo", "apt-get", "update"]
        print_info("Updating package lists...")
        try:
            run_command(cmd)
        except:
            print_warning("Failed to update package lists, continuing anyway...")

        cmd = ["sudo", "apt-get", "install", "-y"] + packages
        print_info("Installing packages: " + ", ".join(packages))
        try:
            run_command(cmd)
            print_success("System dependencies installed")
            return True
        except Exception as e:
            print_error(f"Failed to install packages: {e}")
            return False
    else:
        print_warning("Automatic installation only supported on apt-based systems")
        print_info("Please manually install: " + ", ".join(packages))
        return True  # Continue anyway


def setup_virtual_environment(install_dir: Path) -> Path:
    """Create and setup virtual environment."""
    print_header("Setting up Virtual Environment")

    venv_path = install_dir / "venv"

    if venv_path.exists():
        print_warning("Virtual environment already exists")
        response = input("Recreate it? (y/N): ").strip().lower()
        if response == "y":
            shutil.rmtree(venv_path)
        else:
            print_info("Using existing virtual environment")
            return venv_path

    print_info("Creating virtual environment...")
    try:
        run_command([sys.executable, "-m", "venv", str(venv_path)])
        print_success("Virtual environment created")
    except Exception as e:
        print_error(f"Failed to create virtual environment: {e}")
        sys.exit(1)

    return venv_path


def install_python_dependencies(venv_path: Path, install_dir: Path) -> bool:
    """Install Python packages in virtual environment."""
    print_header("Installing Python Dependencies")

    pip_path = venv_path / "bin" / "pip"
    if not pip_path.exists():
        pip_path = venv_path / "Scripts" / "pip.exe"  # Windows

    requirements_file = install_dir / "requirements.txt"

    print_info("Upgrading pip...")
    try:
        run_command([str(pip_path), "install", "--upgrade", "pip"])
    except:
        print_warning("Failed to upgrade pip, continuing...")

    print_info("Installing required packages...")
    try:
        run_command([str(pip_path), "install", "-r", str(requirements_file)])
        print_success("Python dependencies installed")
        return True
    except Exception as e:
        print_error(f"Failed to install Python dependencies: {e}")
        return False


def get_installation_directory() -> Path:
    """Ask user for installation directory."""
    print_header("Installation Directory")

    default_dir = Path.home() / "Documents" / "LBRY-Downloader"

    print_info(f"Default: {default_dir}")
    response = input(f"Enter installation directory [{default_dir}]: ").strip()

    if response:
        install_dir = Path(response).expanduser().resolve()
    else:
        install_dir = default_dir

    # Create directory if it doesn't exist
    install_dir.mkdir(parents=True, exist_ok=True)

    print_success(f"Installation directory: {install_dir}")
    return install_dir


def get_download_location() -> str:
    """Ask user for download location."""
    print_header("Download Location")

    print_info("Where would you like to store downloaded content?")
    print_info(
        "(This is the base directory - each channel will have its own subfolder)"
    )
    print()

    default_location = "~/Documents/lbry-downloads"
    print_info(f"Default: {default_location}")

    while True:
        response = input(f"Enter download location [{default_location}]: ").strip()

        if not response:
            location = default_location
        else:
            location = response

        # Expand and check
        expanded_path = Path(location).expanduser().resolve()

        try:
            # Try to create it
            expanded_path.mkdir(parents=True, exist_ok=True)

            # Check if writable
            test_file = expanded_path / ".write_test"
            try:
                test_file.touch()
                test_file.unlink()
                print_success(f"Download location: {expanded_path}")
                return str(location)
            except PermissionError:
                print_error(f"Cannot write to {expanded_path}")
                print_info("Please choose a different location or fix permissions")
        except Exception as e:
            print_error(f"Invalid path: {e}")


def get_channels() -> List[dict]:
    """Ask user for channels to download."""
    print_header("Channel Configuration")

    print_info("Enter the channels you want to download from.")
    print_info("You can add more later by editing the config file.")
    print()
    print_info("Supported formats:")
    print_info("  - Odysee URL: https://odysee.com/@ChannelName:1")
    print_info("  - LBRY URI: lbry://@ChannelName#1")
    print_info("  - Just press Enter when done")
    print()

    channels = []

    while True:
        channel_num = len(channels) + 1
        url = input(f"Channel {channel_num} URL (or Enter to finish): ").strip()

        if not url:
            if len(channels) == 0:
                print_warning(
                    "No channels added. You can add them later in the config file."
                )
            break

        # Basic validation
        if not ("odysee.com" in url or "lbry://" in url or url.startswith("@")):
            print_warning("URL format looks unusual. Make sure it's correct.")
            confirm = input("Use this URL anyway? (Y/n): ").strip().lower()
            if confirm == "n":
                continue

        channels.append({"input": url, "enabled": True})
        print_success(f"Added: {url}")

    return channels


def get_download_limit() -> int:
    """Ask user for download limit."""
    print_header("Download Limit")

    print_info("How many items should be downloaded per channel per run?")
    print_info("  - Lower numbers = safer for testing")
    print_info("  - Higher numbers = faster initial sync")
    print_info("  - Downloads most recent items first")
    print()

    print_info("Recommended values:")
    print_info("  - 5-10: Good for testing or large channels")
    print_info("  - 20-50: Moderate syncing")
    print_info("  - 0: Download everything (use with caution!)")
    print()

    while True:
        response = input("Download limit per channel [10]: ").strip()

        if not response:
            return 10

        try:
            limit = int(response)
            if limit < 0:
                print_error("Please enter 0 or a positive number")
                continue

            if limit == 0:
                confirm = (
                    input("Are you sure you want to download ALL items? (y/N): ")
                    .strip()
                    .lower()
                )
                if confirm != "y":
                    continue
                print_warning("Download limit set to ALL items")
            else:
                print_success(f"Download limit set to {limit} items per channel")

            return limit
        except ValueError:
            print_error("Please enter a number")


def create_config(
    download_location: str, channels: List[dict], download_limit: int
) -> str:
    """Generate configuration file content."""
    config = f"""# LBRY Downloader Configuration
# Generated by setup script on {platform.platform()}

lbrynet:
  # URL of the local LBRY daemon (lbrynet)
  api_url: "http://127.0.0.1:5279"
  # Timeout for daemon requests in seconds
  timeout_seconds: 60

general:
  # Base directory for all downloads and state
  base_dir: "{download_location}"
  # Path to the state database
  state_file: "{download_location}/state/database.json"
  # Number of concurrent downloads (keep low to avoid daemon issues)
  max_workers: 2
  # Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
  log_level: "INFO"
  # If true, show what would be downloaded without actually downloading
  dry_run: false
  # Verify that previously downloaded files still exist
  verify_existing_files: true
  # Write SHA256 checksums for downloaded files
  write_checksums: true
  # Filename handling: 'original' or 'safe' (aggressively sanitized)
  filename_mode: "original"
  # Include reposts in downloads (default: false)
  include_reposts: false
  # Number of claims to fetch per page from the daemon
  channel_page_size: 50
  # Keep records of claims even if they disappear from the channel
  keep_missing_claim_records: true
  # Download limit: Number of most recent downloads per channel (0 = all)
  download_limit: {download_limit}

channels:
"""

    for channel in channels:
        config += f'''  - input: "{channel["input"]}"
    enabled: true
'''

    if not channels:
        config += """  # Add your channels here:
  # - input: "https://odysee.com/@ChannelName:1"
  #   enabled: true
"""

    return config


def create_launcher_script(install_dir: Path, venv_path: Path) -> None:
    """Create launcher scripts for easy execution."""
    print_header("Creating Launcher Scripts")

    # Create bin directory
    bin_dir = install_dir / "bin"
    bin_dir.mkdir(exist_ok=True)

    # Create main launcher with daemon auto-check
    launcher = bin_dir / "lbry-downloader"
    launcher_content = f"""#!/bin/bash
# LBRY Downloader Launcher
# Auto-checks and starts lbrynet daemon if needed

INSTALL_DIR="{install_dir}"
VENV_DIR="{venv_path}"
DAEMON_URL="http://127.0.0.1:5279"

# Check if daemon is running
if ! curl -s "$DAEMON_URL" > /dev/null 2>&1; then
    echo "LBRY daemon not running. Starting..."
    
    # Try to start daemon
    if command -v lbrynet &> /dev/null; then
        lbrynet start &
        echo "Waiting for daemon to start..."
        
        # Wait up to 30 seconds for daemon
        for i in $(seq 1 30); do
            if curl -s "$DAEMON_URL" > /dev/null 2>&1; then
                echo "✓ Daemon started successfully"
                break
            fi
            sleep 1
        done
        
        # Check if daemon started
        if ! curl -s "$DAEMON_URL" > /dev/null 2>&1; then
            echo "✗ Failed to start daemon automatically"
            echo ""
            echo "Please start it manually:"
            echo "  lbrynet start"
            echo ""
            echo "Or see LINUX_SETUP.md for installation instructions"
            exit 1
        fi
    else
        echo "✗ lbrynet not found in PATH"
        echo ""
        echo "Please install LBRY SDK:"
        echo "  https://github.com/lbryio/lbry-sdk/releases"
        echo ""
        echo "Or see LINUX_SETUP.md for detailed instructions"
        exit 1
    fi
fi

cd "$INSTALL_DIR"
source "$VENV_DIR/bin/activate"

python main.py "$@"
"""

    launcher.write_text(launcher_content)
    launcher.chmod(0o755)
    print_success(f"Created launcher: {launcher}")

    # Create quick test script with daemon auto-check
    test_script = bin_dir / "lbry-test"
    test_content = f"""#!/bin/bash
# Quick test script

INSTALL_DIR="{install_dir}"
VENV_DIR="{venv_path}"
DAEMON_URL="http://127.0.0.1:5279"

# Check if daemon is running
if ! curl -s "$DAEMON_URL" > /dev/null 2>&1; then
    echo "LBRY daemon not running. Starting..."
    
    if command -v lbrynet &> /dev/null; then
        lbrynet start &
        echo "Waiting for daemon to start..."
        sleep 5
        
        if curl -s "$DAEMON_URL" > /dev/null 2>&1; then
            echo "✓ Daemon started"
        else
            echo "✗ Failed to start daemon"
            echo "Run manually: lbrynet start"
            exit 1
        fi
    else
        echo "✗ lbrynet not found. Install from:"
        echo "  https://github.com/lbryio/lbry-sdk/releases"
        exit 1
    fi
fi

cd "$INSTALL_DIR"
source "$VENV_DIR/bin/activate"

echo "Testing LBRY Downloader..."
python main.py --dry-run "$@"
"""

    test_script.write_text(test_content)
    test_script.chmod(0o755)
    print_success(f"Created test script: {test_script}")

    # Automatically add to PATH and reload shell
    shell_rc = Path.home() / ".bashrc"
    if not shell_rc.exists():
        shell_rc = Path.home() / ".zshrc"

    if shell_rc.exists():
        # Check if already in PATH
        path_line = f'export PATH="{bin_dir}:$PATH"'
        try:
            rc_content = shell_rc.read_text()
            if str(bin_dir) not in rc_content:
                with open(shell_rc, "a") as f:
                    f.write(f"\n# LBRY Downloader\n{path_line}\n")
                print_success(f"Added to PATH in {shell_rc.name}")
            else:
                print_info(f"Already in PATH ({shell_rc.name})")
        except Exception as e:
            print_warning(f"Could not update {shell_rc.name}: {e}")
            print_info(f"Add this line manually to {shell_rc.name}:")
            print(f"  {path_line}")


def run_setup() -> None:
    """Main setup function."""
    print(f"""
{Colors.BOLD}╔══════════════════════════════════════════════════════════════╗
║           LBRY Downloader - Interactive Setup               ║
║                                                              ║
║  This script will help you install and configure the        ║
║  LBRY Downloader tool.                                       ║
╚══════════════════════════════════════════════════════════════╝{Colors.END}
""")

    # Check Python version
    if not check_python_version():
        print_error("Python 3.8+ is required. Please upgrade Python.")
        sys.exit(1)

    # Check system dependencies
    if not check_system_dependencies():
        print_info("Some system dependencies are missing.")
        response = input("Install system dependencies? (Y/n): ").strip().lower()
        if response != "n":
            if not install_system_dependencies():
                print_warning("Failed to install some dependencies")
                response = input("Continue anyway? (y/N): ").strip().lower()
                if response != "y":
                    sys.exit(1)

    # Get installation directory
    install_dir = get_installation_directory()

    # Copy files if not running from install directory
    current_dir = Path(__file__).parent.resolve()
    if current_dir != install_dir:
        print_header("Copying Files")
        print_info(f"Copying from {current_dir} to {install_dir}")

        # Copy Python files
        for pattern in ["*.py", "*.md", "*.txt", "*.toml", "*.example", "Makefile"]:
            for file in current_dir.glob(pattern):
                if file.name != "setup.py":  # Don't copy setup script itself
                    shutil.copy2(file, install_dir)
                    print_success(f"Copied {file.name}")

        # Copy tests directory
        tests_src = current_dir / "tests"
        tests_dst = install_dir / "tests"
        if tests_src.exists():
            if tests_dst.exists():
                shutil.rmtree(tests_dst)
            shutil.copytree(tests_src, tests_dst)
            print_success("Copied tests/")

    # Setup virtual environment
    venv_path = setup_virtual_environment(install_dir)

    # Install Python dependencies
    if not install_python_dependencies(venv_path, install_dir):
        print_error("Failed to install Python dependencies")
        sys.exit(1)

    # Check for existing configuration
    default_download_location = "~/Documents/lbry-downloads"
    config_path = Path(default_download_location).expanduser() / "config.yaml"

    if config_path.exists():
        print_header("Existing Configuration Found")
        print_info(f"Found existing config: {config_path}")
        print_info("This will preserve your channels and settings")

        response = input("Use existing configuration? (Y/n): ").strip().lower()
        if response != "n":
            print_success("Using existing configuration")
            download_location = default_download_location
            # Ensure necessary directories exist
            Path(download_location).expanduser().mkdir(parents=True, exist_ok=True)
            (Path(download_location).expanduser() / "state").mkdir(exist_ok=True)
            (Path(download_location).expanduser() / "channels").mkdir(exist_ok=True)
            # Store config_path for final message
            config_path = Path(download_location).expanduser() / "config.yaml"
        else:
            # User wants to reconfigure
            download_location = get_download_location()
            channels = get_channels()
            download_limit = get_download_limit()

            # Create config file
            print_header("Creating Configuration")
            config_content = create_config(download_location, channels, download_limit)

            config_path = Path(download_location).expanduser() / "config.yaml"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(config_content)
            print_success(f"Created configuration: {config_path}")

            # Create necessary directories
            (config_path.parent / "state").mkdir(exist_ok=True)
            (config_path.parent / "channels").mkdir(exist_ok=True)
            print_success("Created directory structure")
    else:
        # No existing config, proceed with normal setup
        # Get configuration from user
        download_location = get_download_location()
        channels = get_channels()
        download_limit = get_download_limit()

        # Create config file
        print_header("Creating Configuration")
        config_content = create_config(download_location, channels, download_limit)

        config_path = Path(download_location).expanduser() / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(config_content)
        print_success(f"Created configuration: {config_path}")

        # Create necessary directories
        (config_path.parent / "state").mkdir(exist_ok=True)
        (config_path.parent / "channels").mkdir(exist_ok=True)
        print_success("Created directory structure")

    # Create necessary directories
    (config_path.parent / "state").mkdir(exist_ok=True)
    (config_path.parent / "channels").mkdir(exist_ok=True)
    print_success("Created directory structure")

    # Create launcher scripts
    create_launcher_script(install_dir, venv_path)

    # Final instructions
    print(f"""
{Colors.BOLD}{Colors.GREEN}╔══════════════════════════════════════════════════════════════╗
║                    Setup Complete!                           ║
╚══════════════════════════════════════════════════════════════╝{Colors.END}

🎉 LBRY Downloader is ready to use!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 QUICK START (Run these commands):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣  Start the LBRY daemon:
    lbrynet start

2️⃣  Test your configuration:
    lbry-downloader --dry-run

3️⃣  Download content:
    lbry-downloader

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ️  IMPORTANT NOTES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• Command to run: {Colors.BOLD}lbry-downloader{Colors.END}
• Config file: {config_path}
• Download location: {download_location}

If {Colors.BOLD}lbry-downloader{Colors.END} command not found, run:
    source ~/.bashrc

If lbrynet is not installed, see LINUX_SETUP.md for installation.

To add more channels later:
    nano {config_path}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 Documentation:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• README.md - Project overview
• LINUX_SETUP.md - Detailed Linux setup  
• QUICKSTART.md - Quick reference
• config.yaml.example - More examples

Happy downloading! 🚀
""")


if __name__ == "__main__":
    try:
        run_setup()
    except KeyboardInterrupt:
        print("\n\nSetup interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print_error(f"Setup failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
