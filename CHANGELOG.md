# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Fixed
- **Streaming Endpoint Fallback**: When P2P peers are unavailable, the tool now automatically falls back to the daemon's streaming endpoint (`http://localhost:5280/stream/{sd_hash}`), enabling reliable downloads even with no P2P peers
- Reduced P2P wait timeout from 300s to 60s for faster fallback detection
- Added progress bar display during streaming downloads

### Added
- Initial implementation of LBRY Downloader
- Support for incremental sync of LBRY/Odysee channels
- Version tracking using sd_hash
- Atomic state database writes
- Configurable YAML configuration
- Dry-run mode for testing
- Run history logging in JSONL format
- Comprehensive test suite
- Support for Odysee URLs, LBRY URIs, and claim IDs
- Automatic path sanitization
- Checksum generation for downloaded files
- **Per-channel download paths** - Each channel can have its own download location
- **Download limit** - Limit downloads to most recent N items per channel (default: 10)
- **Interactive setup script** - Automated installation with user prompts
- **Uninstall script** - Easy removal of the application

### Technical Details
- JSON-RPC client for lbrynet daemon
- Modular architecture with clear separation of concerns
- State management with claim and version tracking
- Download planning and execution pipeline
- Comprehensive error handling

## Future Ideas

### Planned
- SQLite state database option for large archives
- Tag-based filtering
- Date range filtering
- Parallel download support with rate limiting
- Resume interrupted downloads
- Export reports (CSV, JSON)
- Webhook notifications

### Under Consideration
- GUI interface
- Docker containerization
- Automatic thumbnail/metadata download
- Video format selection
- Bandwidth limiting
