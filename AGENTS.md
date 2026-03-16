# AGENTS.md

## Purpose

This repository contains a Python tool that incrementally syncs downloadable file claims from configured LBRY/Odysee channels into a structured local archive.

Primary goals:

1. Resolve configured channels to stable LBRY identities.
2. Enumerate downloadable claims published by those channels.
3. Download only new claims or new versions.
4. Preserve old versions instead of overwriting them.
5. Maintain deterministic local structure and persistent state.

This project prioritizes correctness, repeatability, and safe incremental behavior over cleverness.

---

## Non-negotiable rules

- Prefer stable identifiers over presentation-layer names:
  - channel identity = `channel_claim_id`
  - claim identity = `claim_id`
  - version identity = `sd_hash` if available, otherwise a deterministic fallback
- Never use title or filename alone as identity.
- Never overwrite an existing downloaded version in place.
- Never mark a download as complete in state unless the file exists and metadata is written.
- Keep changes small and targeted. Do not do unrelated refactors.
- Do not add new dependencies unless they clearly reduce complexity or improve reliability.
- Do not add cloud services, databases, or background workers unless explicitly requested.

### Download Modes

The tool supports two download modes:

1. **P2P Mode (default)** - Uses local lbrynet daemon
   - Downloads from LBRY's decentralized peer network
   - Respects the original LBRY protocol
   - May have availability issues if no peers are online

2. **Direct Mode** - Downloads from Odysee CDN
   - Uses Odysee's centralized CDN for better reliability
   - Falls back when P2P is unavailable or fails
   - User can select via `--direct` flag or config
   - Acceptable because:
     - User explicitly requested this feature
     - Odysee is the primary frontend for LBRY content
     - CDN downloads are more reliable than P2P
     - Still preserves all metadata and state tracking

---

## Expected architecture

Agents should preserve this separation of concerns:

- `main.py`
  - entry point
  - orchestration
  - summary logging
- `config_loader.py`
  - load and validate YAML config
- `lbry_client.py`
  - all JSON-RPC communication with local `lbrynet` daemon
  - isolate daemon/API compatibility here
- `planner.py`
  - compare discovered claims against local state
  - decide: skip / new / new_version / redownload_missing
- `downloader.py`
  - execute downloads via P2P (lbrynet daemon)
  - write metadata files
  - finalize state updates
- `direct_downloader.py`
  - execute downloads from Odysee CDN
  - used when `--direct` flag is set or P2P fails
  - same metadata structure as P2P downloads
- `state_db.py`
  - load/save state
  - atomic writes only
- `models.py`
  - dataclasses / typed structures
- `utils.py`
  - slugifying, hashing, time helpers, filesystem helpers

If the implementation diverges from this shape, preserve the same boundaries.

---

## Filesystem contract

Default base directory is expected to be:

`~/Documents/lbry-downloads`

Expected structure:

```text
lbry-downloads/
  config.yaml
  state/
    database.json
    run-history.jsonl
  channels/
    <channel_slug>__<channel_claim_id>/
      channel.json
      claims/
        <claim_slug>__<claim_id>/
          claim.json
          versions/
            <version_token>/
              <downloaded_file>
              metadata.json
              download.json
              checksums.txt
````

Rules:

* Sanitize filesystem names.
* Preserve extensions when possible.
* Keep folder names deterministic.
* Store metadata beside each downloaded file version.
* Do not flatten version folders.

---

## State management rules

State is a core feature, not a convenience.

Requirements:

* Persistent state must exist across runs.
* State writes must be atomic.
* A claim may have multiple versions.
* A rerun must skip already-downloaded versions.
* If state says a version exists but the local file is missing, treat it as `redownload_missing`.
* Keep prior versions on disk unless the user explicitly asks for pruning.

Preferred initial format:

* JSON state database for v1
* append-only `run-history.jsonl` for auditability

Do not silently delete historical records.

---

## Channel handling rules

Accepted user inputs may include:

* Odysee channel URLs
* LBRY URIs
* channel claim IDs

Normalization rules:

* Accept convenient input forms.
* Resolve to canonical LBRY metadata as early as possible.
* Store and operate on `channel_claim_id` internally.
* If a channel display name changes, keep continuity through the claim ID.

Do not build logic around URL string shape beyond initial parsing.

---

## Download rules

A claim should be downloaded only if it is actually downloadable through the daemon.

Include by default:

* downloadable stream/file claims

Exclude by default:

* reposts
* channels
* collections
* unsupported claim types

If repost support is added, make it config-driven and default-off.

For every successful download:

1. create channel / claim / version folders
2. download into the version folder
3. write normalized metadata
4. write raw or near-raw daemon response
5. optionally write checksum file
6. update state only after success

Do not reorder that sequence.

---

## Version detection rules

Use this priority order for version identity:

1. `sd_hash`
2. `stream_hash`
3. `txid:nout`
4. deterministic hash of normalized metadata JSON

Interpretation:

* same `claim_id` + same version token => skip
* same `claim_id` + different version token => new version
* unseen `claim_id` => new claim

Do not use title changes, filename changes, or folder names as version signals.

---

## Logging and reporting

Logging should be useful during long sync runs.

Always log:

* daemon connectivity result
* channel resolution result
* scan progress
* per-claim action decision
* download success/failure
* final summary counts

Preferred summary fields:

* channels scanned
* claims examined
* new downloads
* new versions
* skipped existing
* redownloaded missing
* failures

Make logs concise and grep-friendly.

---

## Error handling

Prefer graceful degradation over hard failure.

Rules:

* If daemon is unavailable, fail fast with a clear message.
* If one channel fails to resolve, log it and continue with the rest.
* If one claim fails, log it and continue.
* Do not write partial success to state.
* Do not swallow exceptions silently.
* If adding retries, keep them bounded and explicit.

Avoid “best guess” behavior when metadata is incomplete. Prefer a logged skip.

---

## Configuration rules

Expected config file is YAML.

Config should cover:

* daemon API URL
* timeout
* base output directory
* state file path
* max workers
* dry-run
* checksum writing
* verification of existing files
* repost inclusion
* channel list

Agents may extend config, but must follow these rules:

* add defaults conservatively
* preserve backwards compatibility where practical
* validate new fields explicitly
* do not remove existing config keys without migration notes

---

## Development workflow

Before finishing changes:

1. run formatting
2. run linting if configured
3. run tests if present
4. run a dry-run against sample config if practical
5. verify no obvious regression in path/state/version logic

If the repo has a `Makefile`, `pyproject.toml`, `justfile`, or documented task runner, use that instead of inventing commands.

Preferred commands when available:

```bash
python -m pytest
python -m ruff check .
python -m ruff format .
python main.py --dry-run
```

If these tools are not configured in the repo, do not add them casually.

---

## Code style

* Target readable Python over clever Python.
* Prefer small pure functions for planning and normalization logic.
* Keep daemon I/O isolated from business logic.
* Add types where they materially improve clarity.
* Use dataclasses or clearly documented dict schemas.
* Avoid deeply nested control flow.
* Keep path logic deterministic and testable.

When changing behavior, update:

* config comments/examples
* state schema notes if relevant
* any sample output or CLI docs

---

## Testing priorities

If tests exist or are added, prioritize these cases:

1. channel input normalization
2. slug/path sanitization
3. version token generation
4. skip vs new vs new-version decisions
5. missing-file redownload behavior
6. atomic state write behavior
7. metadata normalization stability

The most valuable tests are the ones that prevent duplicate downloads or broken state.

---

## Safe change policy

Safe changes:

* bug fixes in normalization, planning, downloading, or state handling
* clearer logging
* improved config validation
* additional tests
* daemon compatibility fixes isolated to client wrapper

Changes that need extra caution:

* state schema changes
* path layout changes
* version token logic changes
* concurrency changes
* anything that could duplicate downloads or orphan files

For high-impact changes, preserve backwards compatibility or document a migration path.

---

## Things agents should not do

* Do not switch persistence to SQLite unless explicitly requested.
* Do not add async/concurrency complexity unless needed.
* Do not rename major folders or config keys casually.
* Do not remove version history.
* Do not "clean up" files automatically without an explicit retention policy.
* Do not assume Odysee URL formats are permanent.
* Do not assume filenames are unique.
* Do not commit secrets, auth tokens, or machine-specific absolute paths.

Note: Direct Odysee CDN downloads are permitted as a user-requested alternative to P2P.

---

## When uncertain

When faced with an ambiguous implementation choice, prefer:

1. stable identifiers over names
2. deterministic behavior over convenience
3. append-only/history-preserving behavior over destructive updates
4. explicit logging over silent magic
5. compatibility in `lbry_client.py` over leaking API quirks through the codebase

This project is an incremental archive/sync tool. Protect the archive first.