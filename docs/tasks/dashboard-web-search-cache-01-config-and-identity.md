# Dashboard Web Search Cache Tasks 01: Config and Identity

Status: Done

## Goal

Define the configuration and cache-key rules that control when cache is used and what counts as the same search.

## Task Breakdown

### 1. Add cache configuration to the shared config model

**Why**
Operators need a first-class way to enable, disable, and tune cache behavior without editing separate files or hard-coded constants.

**Work**
- Add a dedicated cache config section under the main config schema
- Include at least:
  - `enabled`
  - `ttl_seconds`
  - `max_entries`
  - `db_path` or a derived default path
- Ensure config defaults are safe for existing installs

**Acceptance criteria**
- The config model validates cache settings cleanly
- Existing config files still load without changes
- The new settings appear in the same persisted/effective config response used by the dashboard

**Likely files**
- `src/cc_deep_research/config/schema.py`
- `src/cc_deep_research/config/service.py`

### 2. Define stable cache identity rules

**Why**
The cache only saves credits if equivalent searches map to the same key and materially different searches do not collide.

**Work**
- Add a shared helper that normalizes:
  - provider name
  - query text
  - search depth or strategy
  - `max_results`
  - `include_raw_content`
- Create a deterministic serialized signature for cache lookup
- Decide how whitespace, case, and empty values are normalized

**Acceptance criteria**
- Equivalent requests produce the same key
- Different provider strategies produce different keys
- Key generation logic is shared instead of duplicated across code paths

**Likely files**
- new: `src/cc_deep_research/search_cache.py` or `src/cc_deep_research/cache/search.py`
- `src/cc_deep_research/models/search.py`
