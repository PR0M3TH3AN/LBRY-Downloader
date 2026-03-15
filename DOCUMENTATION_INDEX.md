# Documentation Index

Not sure where to start? This guide helps you find the right documentation.

## 🚀 Getting Started

**New user? Start here:**

1. **[LINUX_SETUP.md](LINUX_SETUP.md)** - Complete Linux installation guide
   - System requirements
   - Step-by-step installation
   - Configuration examples
   - Troubleshooting common issues
   - Setting up automation

2. **[QUICKSTART.md](QUICKSTART.md)** - Get running in 5 minutes
   - Minimal setup instructions
   - Basic usage
   - Common commands

3. **[README.md](README.md)** - Project overview
   - Features
   - Basic usage
   - Architecture

## 📖 Detailed Documentation

### For Users

- **[README.md](README.md)** - Main project documentation
- **[LINUX_SETUP.md](LINUX_SETUP.md)** - Linux-specific setup (Debian/Ubuntu/Mint)
- **[QUICKSTART.md](QUICKSTART.md)** - Quick start guide
- **[config.yaml.example](config.yaml.example)** - Example configuration
- **[PER_CHANNEL_PATHS.md](docs/PER_CHANNEL_PATHS.md)** - Per-channel download paths guide

### Setup Scripts

- **[setup.py](setup.py)** - Interactive installation script (recommended)
  - Checks dependencies
  - Sets up virtual environment
  - Configures download location
  - Sets up channels
  - Creates launcher scripts

- **[uninstall.py](uninstall.py)** - Uninstallation script
  - Finds installation automatically
  - Shows what will be removed
  - Asks for confirmation
  - Cleans up PATH entries

### For Developers

- **[SPEC.md](SPEC.md)** - Detailed implementation specification
  - Architecture decisions
  - Data models
  - API design
  - File structure
  - State management

- **[AGENTS.md](AGENTS.md)** - Development guidelines
  - Coding standards
  - Architecture rules
  - Testing requirements
  - Change policies

- **[CHANGELOG.md](CHANGELOG.md)** - Version history and changes

## 🔧 Setup Guides by Platform

### Linux (Debian/Ubuntu/Mint)

**Quick Install:**
```bash
./install.sh
```

**Manual Install:**
See [LINUX_SETUP.md](LINUX_SETUP.md) for:
- Installing Python and dependencies
- Installing lbrynet daemon
- Configuration setup
- Systemd service setup
- Cron job automation

### Other Platforms

The tool should work on any platform with Python 3.8+, but you'll need to:
1. Install Python 3 and pip
2. Install the LBRY SDK (`lbrynet`)
3. Install Python dependencies from `requirements.txt`
4. Run `python init.py`

## 📋 Configuration

- **Example:** [config.yaml.example](config.yaml.example)
- **Location:** `~/Documents/lbry-downloads/config.yaml`
- **Format:** YAML

## 🧪 Development

### Running Tests

```bash
make test
# OR
python -m pytest tests/ -v
```

### Code Structure

```
main.py           - Entry point
models.py         - Data structures
utils.py          - Helper functions
config_loader.py  - Configuration parsing
lbry_client.py    - Daemon communication
state_db.py       - State management
planner.py        - Download decisions
downloader.py     - Download execution
```

See [SPEC.md](SPEC.md) for detailed architecture.

## 🐛 Troubleshooting

**Common issues are covered in:**
- [LINUX_SETUP.md](LINUX_SETUP.md) - Platform-specific issues
- [README.md](README.md) - General troubleshooting
- [AGENTS.md](AGENTS.md) - Development/debugging

## 📦 Additional Files

- **[install.sh](install.sh)** - Automated Linux installer
- **[init.py](init.py)** - Configuration initialization
- **[Makefile](Makefile)** - Common development tasks
- **[pyproject.toml](pyproject.toml)** - Python package configuration
- **[requirements.txt](requirements.txt)** - Python dependencies

## 📝 Contributing

1. Read [AGENTS.md](AGENTS.md) for development guidelines
2. Review [SPEC.md](SPEC.md) for architecture details
3. Follow existing code style
4. Add tests for new features
5. Update documentation

## 🔗 External Resources

- **LBRY SDK:** https://github.com/lbryio/lbry-sdk
- **LBRY Website:** https://lbry.com
- **Odysee:** https://odysee.com

## 🆘 Getting Help

1. Check the logs: `~/Documents/lbry-downloads/state/run-history.jsonl`
2. Run with debug mode: Set `log_level: "DEBUG"` in config
3. Test daemon: `curl http://127.0.0.1:5279`
4. Review [LINUX_SETUP.md](LINUX_SETUP.md) troubleshooting section

## 📚 Documentation Roadmap

- [x] README - Project overview
- [x] QUICKSTART - Quick start guide
- [x] LINUX_SETUP - Linux installation
- [x] SPEC - Implementation details
- [x] AGENTS - Development guidelines
- [x] CHANGELOG - Version history
- [ ] API documentation (generated)
- [ ] Video tutorial (future)
- [ ] FAQ (future)

## 🎯 Quick Reference

**Most users need:**
1. [LINUX_SETUP.md](LINUX_SETUP.md) - To install
2. [config.yaml.example](config.yaml.example) - To configure
3. [README.md](README.md) - To understand features

**Developers need:**
1. [AGENTS.md](AGENTS.md) - To understand code standards
2. [SPEC.md](SPEC.md) - To understand architecture
3. Source code - Well-commented Python files

---

**Can't find what you need?**
- Check the source code - it's well-documented
- Look at the tests in `tests/` for usage examples
- Review [SPEC.md](SPEC.md) for design decisions
