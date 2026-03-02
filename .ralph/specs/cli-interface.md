# CLI Interface - Requirements & Acceptance Criteria

## Overview
Command-line interface requirements for the CC Deep Research CLI tool.

## Requirements

### 1. Main Command Structure

**Requirement**: CLI framework with main command and subcommands.

**Acceptance Criteria**:
- [ ] Uses click framework
- [ ] Main command `cc-deep-research` works
- [ ] `--version` flag shows version
- [ ] `--help` flag shows help text
- [ ] Help text is clear and comprehensive
- [ ] Can be installed via `pip install -e .`

**Backpressure Gates**:
- Tests: pass (command invocation, help output)
- Lint: pass
- Typecheck: pass
- Committed: yes

### 2. Research Command

**Requirement**: Main research command that executes deep research.

**Acceptance Criteria**:
- [ ] `cc-deep-research research "query"` works
- [ ] Accepts `-d, --depth` option (quick/standard/deep)
- [ ] Accepts `-s, --sources INT` option (minimum sources)
- [ ] Accepts `-o, --output PATH` option (output file path)
- [ ] Accepts `--format` option (markdown/json)
- [ ] Accepts `--providers TEXT...` option (specific providers)
- [ ] Accepts `--no-cross-ref` flag (disable cross-reference)
- [ ] Accepts `--tavily-only` flag (use only Tavily)
- [ ] Accepts `--claude-only` flag (use only Claude)
- [ ] Accepts `--color` option (always/auto/never)
- [ ] Accepts `--progress` flag (show progress)
- [ ] Accepts `--quiet` flag (suppress output)
- [ ] Accepts `--verbose` flag (detailed output)
- [ ] Executes research and generates report
- [ ] Saves report to specified file or default (report_<timestamp>.md)
- [ ] Shows progress during long operations

**Backpressure Gates**:
- Tests: pass (all options work, command executes correctly)
- Lint: pass
- Typecheck: pass
- Committed: yes

### 3. Interactive Mode

**Requirement**: Interactive research session with prompts.

**Acceptance Criteria**:
- [ ] `cc-deep-research interactive` works
- [ ] Prompts user for research query
- [ ] Shows progress updates during research
- [ ] Displays summary and options after research
- [ ] Allows saving report
- [ ] Accepts `-d, --depth` option
- [ ] Accepts `--save-dir PATH` option
- [ ] Accepts `--no-auto-save` flag

**Backpressure Gates**:
- Tests: pass (interactive flow, prompts, save options)
- Lint: pass
- Typecheck: pass
- Committed: yes

### 4. Config Command

**Requirement**: Configuration management commands.

**Acceptance Criteria**:
- [ ] `cc-deep-research config show` displays current config
- [ ] `cc-deep-research config set KEY VALUE` sets config value
- [ ] `cc-deep-research config unset KEY` removes config value
- [ ] `cc-deep-research config edit` opens config file in editor
- [ ] `cc-deep-research config reset` creates default config
- [ ] Config file location: `~/.config/cc-deep-research/config.yaml`
- [ ] Config file is YAML format
- [ ] Config values persist across sessions
- [ ] Changes to config are reflected immediately

**Backpressure Gates**:
- Tests: pass (all subcommands work, config persists)
- Lint: pass
- Typecheck: pass
- Committed: yes

### 5. Session Command

**Requirement**: Session management commands.

**Acceptance Criteria**:
- [ ] `cc-deep-research session list` shows all saved sessions
- [ ] `cc-deep-research session show SESSION_ID` shows session details
- [ ] `cc-deep-research session export SESSION_ID` exports session
- [ ] `cc-deep-research session delete SESSION_ID` deletes session
- [ ] `cc-deep-research session compare ID1 ID2` compares sessions
- [ ] Export accepts `-f, --format` option (markdown/json/html)
- [ ] Export accepts `-o, --output PATH` option
- [ ] Sessions have unique IDs
- [ ] Session list shows summary (query, date, source count)
- [ ] Session show shows full details

**Backpressure Gates**:
- Tests: pass (all subcommands work, session persistence)
- Lint: pass
- Typecheck: pass
- Committed: yes

### 6. Progress Indicators

**Requirement**: Visual feedback during long-running operations.

**Acceptance Criteria**:
- [ ] Progress bar shown for deep mode (5+ sources)
- [ ] Spinner shown for quick/standard mode
- [ ] Progress bar shows: percentage, sources found, searches remaining, ETA
- [ ] Progress can be disabled with `--no-progress`
- [ ] Progress indicators work in quiet mode (minimal)
- [ ] Rich library used for terminal formatting
- [ ] Colors work correctly (respects `--color` setting)

**Backpressure Gates**:
- Tests: pass (progress displays correctly, options work)
- Lint: pass
- Typecheck: pass
- Committed: yes

### 7. Error Messages

**Requirement**: Helpful error messages for common failure scenarios.

**Acceptance Criteria**:
- [ ] No Tavily API keys: shows error, suggests config command or env var
- [ ] All keys exhausted: shows error, indicates reset time
- [ ] No results found: suggests rephrasing, broader terms
- [ ] Cannot write file: shows permission error, suggests alternative path
- [ ] Invalid config value: shows which key is invalid, suggests valid values
- [ ] Network error: shows error, retries automatically
- [ ] All errors include context (what failed, why, how to fix)
- [ ] Error messages are clear and actionable

**Backpressure Gates**:
- Tests: pass (all error scenarios produce helpful messages)
- Lint: pass
- Typecheck: pass
- Committed: yes

### 8. Configuration File

**Requirement**: YAML configuration file with all settings.

**Acceptance Criteria**:
- [ ] Config file location: `~/.config/cc-deep-research/config.yaml`
- [ ] Default config created on first run
- [ ] Config structure:
  ```yaml
  search:
    depth: deep
    providers: [tavily, claude]
    mode: hybrid_parallel
  tavily:
    api_keys: [key1, key2]
    rate_limit: 1000
    max_results: 100
  research:
    min_sources:
      quick: 3
      standard: 10
      deep: 20
    enable_iterative_search: true
    enable_cross_ref: true
    enable_quality_scoring: true
  output:
    format: markdown
    auto_save: true
    save_dir: ./reports
    include_metadata: true
    include_cross_ref_analysis: true
  display:
    color: auto
    progress: auto
    verbose: false
  ```
- [ ] Config can be loaded and validated
- [ ] Invalid config shows helpful error

**Backpressure Gates**:
- Tests: pass (config loading, validation, defaults)
- Lint: pass
- Typecheck: pass
- Committed: yes

### 9. Environment Variables

**Requirement**: Environment variables override config file.

**Acceptance Criteria**:
- [ ] `TAVILY_API_KEYS` overrides tavily.api_keys
- [ ] `CC_DEEP_RESEARCH_CONFIG` sets custom config path
- [ ] `CC_DEEP_RESEARCH_DEPTH` sets default depth
- [ ] `CC_DEEP_RESEARCH_FORMAT` sets default output format
- [ ] `NO_COLOR` disables colors (standard convention)
- [ ] Environment variables take precedence over config file
- [ ] CLI options take precedence over both

**Backpressure Gates**:
- Tests: pass (env vars override correctly)
- Lint: pass
- Typecheck: pass
- Committed: yes

### 10. Shell Completion

**Requirement**: Tab completion for commands and options.

**Acceptance Criteria**:
- [ ] Bash completion works
- [ ] Zsh completion works
- [ ] Fish completion works
- [ ] Completions for subcommands
- [ ] Completions for options
- [ ] Completions for config keys
- [ ] Installation instructions provided in README

**Backpressure Gates**:
- Tests: pass (completion scripts work)
- Lint: pass
- Typecheck: pass
- Committed: yes

### 11. Output Formats

**Requirement**: Multiple output formats for different use cases.

**Acceptance Criteria**:
- [ ] Markdown format works (default)
- [ ] JSON format works (machine-readable)
- [ ] JSON includes all session data
- [ ] Format can be specified via `--format` option
- [ ] Format respects `-o` output file extension
- [ ] Invalid format shows error with valid options

**Backpressure Gates**:
- Tests: pass (markdown and JSON formats work)
- Lint: pass
- Typecheck: pass
- Committed: yes

### 12. CLI Examples

**Requirement**: CLI works with real-world usage patterns.

**Acceptance Criteria**:
- [ ] Basic research: `cc-deep-research research "test query"`
- [ ] Quick research: `cc-deep-research research -d quick "test"`
- [ ] Deep research: `cc-deep-research research -d deep "complex topic"`
- [ ] Save to file: `cc-deep-research research -o report.md "query"`
- [ ] JSON output: `cc-deep-research research --format json "query"`
- [ ] Tavily only: `cc-deep-research research --tavily-only "query"`
- [ ] Config show: `cc-deep-research config show`
- [ ] Session list: `cc-deep-research session list`

**Backpressure Gates**:
- Tests: pass (all examples work as documented)
- Lint: pass
- Typecheck: pass
- Committed: yes

## Backpressure Gates Summary

All CLI features must meet:
- Tests: pass (unit tests for each command)
- Lint: pass (`ruff check`)
- Typecheck: pass (`mypy`)
- Coverage: 85%+ for new code
- Committed: yes (with conventional commit message)

## Additional Notes

- CLI should be responsive and user-friendly
- Help text should be clear and include examples
- Progress indicators should be informative without being overwhelming
- Error messages should be actionable
- CLI should work on Linux, macOS, and Windows
- Consider internationalization for future (not required now)
