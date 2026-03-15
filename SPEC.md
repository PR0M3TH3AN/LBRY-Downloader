# LBRY / Odysee Channel Downloader — Detailed Implementation Spec

## Goal

Build a local Python tool that:

1. Accepts a list of Odysee/LBRY channels in a config file.
2. Resolves each channel to stable LBRY identifiers.
3. Enumerates all downloadable file claims published by those channels.
4. Downloads each claim into a structured folder layout.
5. Skips anything already downloaded.
6. Detects new versions of previously seen content and downloads only the new version.
7. Maintains persistent state so repeated runs behave like an incremental sync.

This should be designed for **robustness**, not page scraping.

---

## Recommended Architecture

### Use the LBRY SDK daemon, not Odysee HTML scraping

The tool should talk to a locally running `lbrynet` daemon through its JSON-RPC API, typically at:

```text
http://127.0.0.1:5279
```

Why this is the right design:

* Odysee web pages are presentation-layer HTML and can change.
* The daemon exposes blockchain-backed claim metadata.
* The daemon handles resolution and downloading.
* You get stable IDs like `claim_id`, `channel_claim_id`, `txid`, `nout`, `sd_hash`, and file info.
* You avoid reverse-engineering Odysee’s frontend behavior.

### Input format recommendation

Let users enter channels in either of these forms:

* Odysee URL, for convenience
* LBRY URI, for correctness
* Channel claim ID, for maximum stability

Accepted examples:

```text
https://odysee.com/@SomeChannel:1
lbry://@SomeChannel#1
@SomeChannel#1
f3b9b2b7c1c3d8e9a1234567890abcdef123456
```

### Normalization strategy

On the first successful resolve of a channel, store these canonical values in state:

* original input
* normalized LBRY URI
* `channel_claim_id`
* current channel name

From then on, use `channel_claim_id` internally whenever possible.

This protects the sync process from:

* display name changes
* URL changes
* case differences
* Odysee frontend URL changes

---

## What counts as a “downloadable file”

The tool should only process claims that actually resolve to downloadable content.

In practice, that usually means stream/file claims that the daemon can download with `get`.

### Include

* stream claims with downloadable content
* claims with valid source blobs / `sd_hash`
* files returned by channel claim search that are downloadable through the daemon

### Exclude

* repost-only entries unless explicitly enabled
* channels
* collections/playlists
* unsupported claim types
* claims that resolve but are not downloadable files

Config should allow optional inclusion of reposts:

```yaml
include_reposts: false
```

Default should be `false`.

---

## Folder Layout

Base folder:

```text
~/Documents/lbry-downloads/
```

Within that:

```text
lbry-downloads/
  config.yaml
  state/
    database.json
    run-history.jsonl
    locks/
  channels/
    <channel_slug>__<channel_claim_id>/
      channel.json
      claims/
        <claim_slug>__<claim_id>/
          claim.json
          versions/
            <version_token>/
              file.ext
              metadata.json
              download.json
              checksums.txt
```

### Directory naming rules

#### Channel folder name

Use:

```text
<sanitized_channel_name>__<channel_claim_id>
```

Example:

```text
TheModernInvestor__f3b9b2b7c1c3d8e9a1234567890abcdef123456
```

#### Claim folder name

Use:

```text
<sanitized_claim_name>__<claim_id>
```

Example:

```text
bitcoin-market-update__8ab12cd34ef56aa90bb11223344556677889900
```

#### Version folder name

Use a deterministic version token based on the best available content identity:

Priority order:

1. `sd_hash`
2. `stream_hash`
3. `txid:nout`
4. fallback hash of resolved metadata JSON

Example:

```text
sd_4f8c5d7e9a...
```

This gives a clean per-version subfolder and makes version detection robust.

---

## State Model

Use a persistent JSON database initially.

File:

```text
state/database.json
```

Later this can be upgraded to SQLite, but JSON is fine for v1.

### Top-level shape

```json
{
  "schema_version": 1,
  "channels": {},
  "claims": {},
  "downloads": {},
  "last_run": null
}
```

### Channel record

```json
{
  "input": "https://odysee.com/@SomeChannel:1",
  "normalized_uri": "lbry://@SomeChannel#1",
  "channel_claim_id": "f3b9...",
  "channel_name": "@SomeChannel",
  "folder": "channels/SomeChannel__f3b9...",
  "last_scan": "2026-03-15T12:34:56Z"
}
```

### Claim record

Key by claim ID.

```json
{
  "claim_id": "8ab12...",
  "channel_claim_id": "f3b9...",
  "name": "bitcoin-market-update",
  "permanent_url": "lbry://@SomeChannel#1/bitcoin-market-update#8",
  "claim_folder": "channels/SomeChannel__f3b9.../claims/bitcoin-market-update__8ab12...",
  "first_seen": "2026-03-15T12:34:56Z",
  "last_seen": "2026-03-15T12:34:56Z",
  "latest_version_token": "sd_4f8c5d7e...",
  "versions": {
    "sd_4f8c5d7e...": {
      "txid": "...",
      "nout": 0,
      "sd_hash": "4f8c5d7e...",
      "stream_hash": "...",
      "published_at": "...",
      "downloaded": true,
      "file_relpath": "versions/sd_4f8c5d7e.../video.mp4"
    }
  }
}
```

### Why key by claim ID

Because filenames and titles can change.

Claim ID is the stable identity for the published item.

### How versioning should work

A claim may be updated over time. The same `claim_id` can point to newer content.

The script should treat a claim as “new version available” when the current version token differs from the latest stored version token.

That means:

* same claim ID + same version token → skip
* same claim ID + different version token → download into a new version subfolder
* unseen claim ID → new download

---

## Config File Spec

Use YAML for readability.

Path:

```text
~/Documents/lbry-downloads/config.yaml
```

Example:

```yaml
lbrynet:
  api_url: "http://127.0.0.1:5279"
  timeout_seconds: 60

general:
  base_dir: "~/Documents/lbry-downloads"
  state_file: "~/Documents/lbry-downloads/state/database.json"
  max_workers: 2
  log_level: "INFO"
  dry_run: false
  verify_existing_files: true
  write_checksums: true
  filename_mode: "original"
  include_reposts: false
  channel_page_size: 50
  keep_missing_claim_records: true

channels:
  - input: "https://odysee.com/@SomeChannel:1"
    enabled: true
    tags_include: []
    tags_exclude: []
  - input: "lbry://@AnotherChannel#5"
    enabled: true
    tags_include: []
    tags_exclude: []
```

### Field behavior

#### `api_url`

Location of the local daemon.

#### `base_dir`

Root output directory.

#### `max_workers`

Number of concurrent downloads. Keep low by default because daemon/resource behavior may vary.

#### `dry_run`

If true, the script resolves and plans actions but does not download.

#### `verify_existing_files`

If true, check that previously downloaded files still exist where expected.

#### `write_checksums`

If true, compute SHA256 for downloaded files and write `checksums.txt`.

#### `filename_mode`

Allowed values:

* `original` → preserve daemon/original filename when possible
* `safe` → sanitize aggressively

#### `channel_page_size`

Batch size for paginated claim searches.

#### `keep_missing_claim_records`

If a previously seen claim no longer appears in a later channel scan, keep it in state instead of deleting it.

---

## Functional Requirements

## 1. Startup and validation

On launch, the script must:

1. Load config.
2. Expand `~` paths.
3. Create base directories if missing.
4. Load or initialize state DB.
5. Verify that `lbrynet` API is reachable.
6. Fail with a helpful message if the daemon is unavailable.

Validation checks:

* config file exists
* YAML parses
* channels list is not empty
* at least one channel is enabled
* daemon health check succeeds

---

## 2. Channel resolution

For each enabled channel:

1. Parse the input string.
2. If input is an Odysee URL, extract the channel slug/claim suffix if possible.
3. Convert to a resolvable LBRY-style reference.
4. Call resolve through the daemon.
5. Confirm the resolved claim is a channel claim.
6. Store normalized channel metadata in state.

Expected stored channel metadata:

* display name
* normalized URI
* claim ID
* permanent URL if available
* short URL if available

If resolution fails:

* log error
* continue to next channel
* do not abort whole run unless `fail_fast` is enabled later

---

## 3. Enumerating claims in a channel

For each resolved channel, the script must enumerate all claims published by that channel.

The enumeration should:

* paginate until exhausted
* collect claim metadata records
* ignore duplicates
* filter non-downloadable items
* optionally exclude reposts

Each candidate claim should be evaluated for:

* `claim_id`
* `name`
* `title`
* `value_type`
* `sd_hash`
* file/source metadata
* release/publish timestamp
* claim sequence or tx info

The exact daemon methods can vary slightly by SDK version, so implementation should isolate API calls in a client wrapper.

### Client wrapper design

Create a module like:

```text
lbry_client.py
```

With functions such as:

```python
def resolve(url_or_uri) -> dict: ...
def list_channel_claims(channel_claim_id: str, page: int, page_size: int) -> dict: ...
def get_claim(claim_id: str) -> dict: ...
def download(uri: str, download_directory: str) -> dict: ...
def file_list(claim_id: str | None = None) -> dict: ...
```

This keeps the rest of the app independent from API quirks.

---

## 4. Deciding whether a claim should be downloaded

For every claim found in the channel listing:

### Step A — determine if downloadable

A claim is eligible if:

* it resolves to a stream/file
* daemon can provide download metadata
* it is not channel/collection-only content

### Step B — compute version token

Build a deterministic version token using:

1. `sd_hash`
2. else `stream_hash`
3. else `txid:nout`
4. else hash of normalized metadata JSON

### Step C — compare to state

Cases:

#### New claim

`claim_id` not in state:

* create claim record
* mark action = `download_new`

#### Existing claim, same version

`claim_id` exists and version token already recorded:

* action = `skip_existing`

#### Existing claim, new version

`claim_id` exists but version token not recorded:

* action = `download_new_version`

---

## 5. Download behavior

For any claim that needs downloading:

1. Create channel folder if missing.
2. Create claim folder if missing.
3. Create version folder.
4. Ask daemon to download into that version folder.
5. Capture returned metadata.
6. Find resulting file path.
7. Write metadata files.
8. Update state only after download succeeds.

### Files written per version

Inside each version folder:

```text
file.ext
metadata.json
download.json
checksums.txt
```

#### `metadata.json`

Normalized metadata assembled by our tool:

* claim ID
* channel claim ID
* title
* name
* version token
* permanent URL
* timestamps
* hashes
* original filename if known
* local file path

#### `download.json`

Raw or near-raw daemon response from the download call.

#### `checksums.txt`

SHA256 checksum of the downloaded file.

---

## 6. Skip logic

The skip logic should be conservative and deterministic.

A file should be skipped only if:

* claim ID exists in state
* version token exists in that claim’s `versions`
* expected local file exists
* optionally checksum still matches if verification is enabled later

If state says a version is downloaded but the file is missing:

* mark as `redownload_missing`
* download again into the same version folder if empty, or recreate safely

### Avoid duplicate downloads caused by title changes

Never rely on title or filename as identity.

Identity must be:

* claim ID for item identity
* version token for content version identity

---

## 7. Updating state safely

State writes must be atomic.

Recommended pattern:

1. Write updated JSON to `database.json.tmp`
2. fsync if possible
3. replace `database.json`

Also append one line per action to:

```text
state/run-history.jsonl
```

Each line example:

```json
{"ts":"2026-03-15T12:45:00Z","channel_claim_id":"f3...","claim_id":"8ab...","action":"download_new_version","version_token":"sd_4f8...","status":"success"}
```

This gives easy auditing without parsing the whole DB.

---

## 8. Logging

The script should log:

* daemon connectivity
* channel resolution results
* pagination progress
* skipped claims
* new claims
* new versions
* failures
* summary counts

Recommended outputs:

* console logging
* optional file logging later

Example summary:

```text
Run complete.
Channels scanned: 3
Claims examined: 842
New downloads: 7
New versions: 2
Skipped existing: 833
Failures: 0
```

---

## 9. Error handling

The script should continue past individual failures where possible.

Handle these separately:

### Daemon unavailable

Abort run with clear message.

### Channel resolve failure

Log and continue.

### Claim metadata incomplete

Log warning and skip.

### Download failure

Log failure and continue.
Do not mark as downloaded in state.

### Partial/incomplete local file

Either:

* remove partial file and retry once, or
* mark failed and continue

For v1, keep it simple:

* no automatic retry beyond one retry per claim

---

## 10. Suggested Python package structure

```text
lbry-downloads/
  config.yaml
  main.py
  lbry_client.py
  config_loader.py
  state_db.py
  planner.py
  downloader.py
  models.py
  utils.py
  requirements.txt
```

### Module responsibilities

#### `main.py`

Program entry point.
Coordinates the run.

#### `lbry_client.py`

JSON-RPC wrapper for the daemon.

#### `config_loader.py`

Loads and validates YAML config.

#### `state_db.py`

Loads, updates, and atomically saves state.

#### `planner.py`

Compares channel claims with state and decides actions.

#### `downloader.py`

Performs downloads and writes metadata.

#### `models.py`

Typed dataclasses / pydantic models if desired.

#### `utils.py`

Slugify, hashing, time helpers, path helpers.

---

## 11. Suggested core algorithm

```text
load config
ensure directories exist
load state
check daemon

for each enabled channel:
    resolve channel
    save/update channel record
    page through channel claims
    for each claim:
        if not downloadable:
            continue
        compute version token
        compare against state
        if new or new version or missing local file:
            queue download action
        else:
            queue skip action

execute queued downloads
write metadata
update state after each successful download
write run summary
```

---

## 12. Recommended metadata normalization

Build a normalized metadata object for each claim version with fields like:

```json
{
  "claim_id": "...",
  "channel_claim_id": "...",
  "name": "...",
  "title": "...",
  "claim_type": "stream",
  "value_type": "stream",
  "version_token": "sd_...",
  "sd_hash": "...",
  "stream_hash": "...",
  "txid": "...",
  "nout": 0,
  "permanent_url": "...",
  "short_url": "...",
  "canonical_url": "...",
  "timestamp": 0,
  "release_time": 0,
  "fee": null,
  "tags": [],
  "languages": [],
  "source_name": "...",
  "source_media_type": "...",
  "file_name": "...",
  "download_path": "..."
}
```

This makes future migration much easier.

---

## 13. Filename and path sanitization

All filesystem names should be sanitized.

Rules:

* replace `/`, `\\`, `:`, `*`, `?`, `"`, `<`, `>`, `|`
* collapse repeated whitespace
* trim trailing periods/spaces
* limit path component length, e.g. 120 chars
* preserve extension where possible

Recommended slug helper behavior:

```text
"Bitcoin Market Update!!!" -> "Bitcoin Market Update"
```

For stricter mode:

```text
"Bitcoin Market Update!!!" -> "bitcoin-market-update"
```

---

## 14. Concurrency

For v1, keep concurrency low.

Recommendation:

* enumerate sequentially
* download with `max_workers` of 1 or 2

Reason:

* easier logging
* fewer daemon surprises
* less chance of file/path contention

---

## 15. CLI behavior

The script should support:

```bash
python main.py
```

Optional future flags:

```bash
python main.py --config ~/Documents/lbry-downloads/config.yaml
python main.py --dry-run
python main.py --channel @SomeChannel#1
python main.py --repair-missing
```

For v1, minimum supported:

* optional `--config`
* optional `--dry-run`

---

## 16. Minimum external dependencies

Recommended `requirements.txt`:

```text
PyYAML>=6.0
requests>=2.31.0
```

Optional:

```text
python-slugify>=8.0.0
```

But a custom sanitizer is fine, so this can stay minimal.

---

## 17. Daemon assumptions

The spec assumes the user has installed and started the LBRY SDK daemon locally.

The script should not try to install or manage the daemon itself.

It should simply detect and report whether the daemon is reachable.

Helpful startup error example:

```text
Could not connect to LBRY daemon at http://127.0.0.1:5279.
Make sure lbrynet is installed and running before starting the downloader.
```

---

## 18. Why Odysee links in config are okay but not ideal as primary identity

They are fine for user convenience.

But the script should convert them internally to stable identifiers because:

* Odysee is a frontend
* URLs can change format
* channel names can change
* claim IDs are more stable than presentation-layer URLs

Best practice:

* accept Odysee links
* resolve once
* store `channel_claim_id`
* use `channel_claim_id` and canonical LBRY URI from then on

---

## 19. Practical recommendations for v1

### Use this identity model

* Channel identity: `channel_claim_id`
* Claim identity: `claim_id`
* Version identity: `sd_hash` or fallback version token

### Use this storage model

* JSON state DB
* per-channel folders
* per-claim folders
* per-version subfolders

### Use this behavior model

* skip identical versions
* download only new claims or changed versions
* keep prior versions on disk

That gives you:

* reproducible organization
* incremental sync
* protection against duplicate downloads
* visible version history

---

## 20. Nice-to-have future features

Not required for v1, but useful later:

* SQLite state DB
* daemon method compatibility layer for multiple SDK versions
* retry queue
* checksum verification of existing files on every run
* tag filters
* date filters
* delete/archival policy for removed claims
* export report CSV
* webhook or email notifications
* parallel downloads with backoff
* channel alias cache

---

## 21. Explicit implementation decisions

These are the recommended final choices for the first working version.

### Decision 1

Use local `lbrynet` JSON-RPC API.

### Decision 2

Accept Odysee URLs in config, but normalize to LBRY URI and `channel_claim_id`.

### Decision 3

Organize downloads as:

```text
channel -> claim -> version -> file
```

### Decision 4

Use `claim_id` as stable item identity.

### Decision 5

Use `sd_hash` as primary version identity.

### Decision 6

Store persistent state in JSON.

### Decision 7

Skip only when both state and local file presence confirm the version already exists.

### Decision 8

Write metadata files beside every downloaded file.

---

## 22. Example sample config

```yaml
lbrynet:
  api_url: "http://127.0.0.1:5279"
  timeout_seconds: 60

general:
  base_dir: "~/Documents/lbry-downloads"
  state_file: "~/Documents/lbry-downloads/state/database.json"
  max_workers: 2
  log_level: "INFO"
  dry_run: false
  verify_existing_files: true
  write_checksums: true
  filename_mode: "original"
  include_reposts: false
  channel_page_size: 50
  keep_missing_claim_records: true

channels:
  - input: "https://odysee.com/@SomeChannel:1"
    enabled: true
    tags_include: []
    tags_exclude: []

  - input: "lbry://@AnotherChannel#5"
    enabled: true
    tags_include: []
    tags_exclude: []
```

---

## 23. Example first-run behavior

Given a config with 2 channels:

1. Script starts.
2. Connects to local daemon.
3. Resolves both channels.
4. Enumerates all downloadable claims.
5. Downloads every eligible file.
6. Writes state and metadata.

Example resulting structure:

```text
~/Documents/lbry-downloads/
  config.yaml
  state/
    database.json
    run-history.jsonl
  channels/
    SomeChannel__f3b9.../
      channel.json
      claims/
        bitcoin-market-update__8ab12.../
          claim.json
          versions/
            sd_4f8c5d7e.../
              update.mp4
              metadata.json
              download.json
              checksums.txt
```

---

## 24. Example repeat-run behavior

Second run:

* same channels resolve successfully
* 500 existing claims unchanged
* 2 new claims published
* 1 old claim updated with new `sd_hash`

Result:

* 500 skipped
* 2 new downloads
* 1 new version folder added under an existing claim folder

---

## 25. Bottom-line recommendation

The most robust solution is:

* **Use LBRY SDK locally**
* **Treat Odysee links as user input only**
* **Normalize channels to claim IDs**
* **Track claims by claim ID**
* **Track versions by `sd_hash`**
* **Download into channel/claim/version folders**
* **Store persistent state and metadata**

That is the best balance of:

* robustness
* maintainability
* incremental sync
* resistance to frontend/API changes

---

## 26. Copy-paste starter config block

```yaml
lbrynet:
  api_url: "http://127.0.0.1:5279"
  timeout_seconds: 60

general:
  base_dir: "~/Documents/lbry-downloads"
  state_file: "~/Documents/lbry-downloads/state/database.json"
  max_workers: 2
  log_level: "INFO"
  dry_run: false
  verify_existing_files: true
  write_checksums: true
  filename_mode: "original"
  include_reposts: false
  channel_page_size: 50
  keep_missing_claim_records: true

channels:
  - input: "https://odysee.com/@SomeChannel:1"
    enabled: true
    tags_include: []
    tags_exclude: []
```

---

## 27. Implementation note for the next step

When turning this into code, the most important design choice is to isolate all daemon API interactions in one client module. That way, if the LBRY SDK method signatures differ slightly across versions, only one part of the code has to change.
