# CC Deep Research CLI - Build and Run Instructions

## Project Setup

### Prerequisites
- Python 3.11 or higher
- pip (Python package manager)
- git (for version control)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd cc-deep-research

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies (after pyproject.toml is created)
pip install -e .
# Or if using requirements.txt
pip install -r requirements.txt
```

### Configuration

```bash
# Set Tavily API keys (comma-separated for rotation)
export TAVILY_API_KEYS=key1,key2,key3

# Or use config file (created automatically on first run)
cc-deep-research config edit
```

---

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/cc_deep_research --cov-report=term-missing

# Run specific test file
pytest tests/test_search_provider.py

# Run with verbose output
pytest -v

# Run async tests
pytest --asyncio-mode=auto
```

### Test Requirements

Minimum 85% code coverage required for all new code.

---

## Development Workflow

### Running the CLI

```bash
# Basic research (deep mode by default)
cc-deep-research research "What are the latest developments in quantum computing?"

# Quick research
cc-deep-research research -d quick "What is the capital of Australia?"

# Save to specific file
cc-deep-research research -o report.md "Climate change statistics 2024"

# Use only Tavily
cc-deep-research research --tavily-only "AI safety research"

# Show current configuration
cc-deep-research config show

# Set configuration value
cc-deep-research config set research.min_sources_deep 25

# List saved sessions
cc-deep-research session list
```

### Development Server

```bash
# Run in development mode with verbose logging
cc-deep-research research --verbose "test query"

# Enable debug mode
export CC_DEEP_RESEARCH_DEBUG=1
cc-deep-research research "test query"
```

---

## Build Commands

```bash
# Build distribution packages
python -m build

# Check package structure
python -m twine check dist/*

# Install in editable mode (for development)
pip install -e .
```

---

## Code Quality

```bash
# Format code with black
black src/ tests/

# Check code style with ruff
ruff check src/ tests/

# Type check with mypy
mypy src/

# Run pre-commit hooks (if configured)
pre-commit run --all-files
```

---

## Key Learnings

### Project Structure
```
src/cc_deep_research/
├── __init__.py           # Package initialization
├── cli/                  # CLI interface (click commands)
├── search/               # Search provider implementations
├── orchestrator/         # Research orchestration logic
├── reporting/            # Report generation
└── config/               # Configuration management
```

### Async Patterns
- All network operations use `async/await`
- Use `httpx.AsyncClient` for HTTP requests
- Use `asyncio.gather()` for parallel operations
- Use `pytest-asyncio` for async tests

### Data Validation
- All data structures use `pydantic.BaseModel`
- Type hints are required for all functions
- Use `pydantic` for runtime validation

### Configuration
- Config files in YAML format (`~/.config/cc-deep-research/config.yaml`)
- Environment variables override config file settings
- Use `python-dotenv` for `.env` file support

### Error Handling
- Use custom exception classes for specific errors
- Provide helpful error messages with suggestions
- Log errors with context (provider, query, timestamp)
- Implement circuit breaker for repeated failures

---

## Troubleshooting

### Common Issues

**Tavily API key errors**
```bash
# Verify API keys are set
cc-deep-research config show

# Reset config and add keys again
cc-deep-research config reset
cc-deep-research config set tavily.api_keys key1,key2,key3
```

**Import errors**
```bash
# Reinstall package in editable mode
pip install -e .
```

**Test failures**
```bash
# Clear pytest cache
pytest --cache-clear

# Run tests with debug output
pytest -v -s
```

---

## Feature Development Quality Standards

**CRITICAL**: All new features MUST meet the following mandatory requirements before being considered complete.

### Testing Requirements

- **Minimum Coverage**: 85% code coverage ratio required for all new code
- **Test Pass Rate**: 100% - all tests must pass, no exceptions
- **Test Types Required**:
  - Unit tests for all business logic and services
  - Integration tests for API endpoints or main functionality
  - End-to-end tests for critical user workflows
- **Coverage Validation**: Run coverage reports before marking features complete:
  ```bash
  pytest --cov=src/cc_deep_research --cov-report=term-missing
  ```
- **Test Quality**: Tests must validate behavior, not just achieve coverage metrics
- **Test Documentation**: Complex test scenarios must include comments explaining the test strategy

### Git Workflow Requirements

Before moving to the next feature, ALL changes must be:

1. **Committed with Clear Messages**:
   ```bash
   git add .
   git commit -m "feat(module): descriptive message following conventional commits"
   ```
   - Use conventional commit format: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, etc.
   - Include scope when applicable: `feat(search):`, `fix(cli):`, `test(orchestrator):`
   - Write descriptive messages that explain WHAT changed and WHY

2. **Pushed to Remote Repository**:
   ```bash
   git push origin <branch-name>
   ```
   - Never leave completed features uncommitted
   - Push regularly to maintain backup and enable collaboration

3. **Branch Hygiene**:
   - Work on feature branches, never directly on `main`
   - Branch naming convention: `feature/<feature-name>`, `fix/<issue-name>`, `docs/<doc-update>`
   - Create pull requests for all significant changes

4. **Ralph Integration**:
   - Update .ralph/fix_plan.md with new tasks before starting work
   - Mark items complete in .ralph/fix_plan.md upon completion
   - Update .ralph/PROMPT.md if development patterns change
   - Test features work within Ralph's autonomous loop

### Documentation Requirements

**ALL implementation documentation MUST remain synchronized with the codebase**:

1. **Code Documentation**:
   - Python docstrings for all classes and public functions
   - Type hints for all parameters and return values
   - Update inline comments when implementation changes
   - Remove outdated comments immediately

2. **Implementation Documentation**:
   - Update relevant sections in this AGENT.md file
   - Keep build and test commands current
   - Update configuration examples when defaults change
   - Document breaking changes prominently

3. **README Updates**:
   - Keep feature lists current
   - Update setup instructions when dependencies change
   - Maintain accurate command examples
   - Update version compatibility information

4. **AGENT.md Maintenance**:
   - Add new build patterns to relevant sections
   - Update "Key Learnings" with new insights
   - Keep command examples accurate and tested
   - Document new testing patterns or quality gates

### Feature Completion Checklist

Before marking ANY feature as complete, verify:

- [ ] All tests pass with `pytest`
- [ ] Code coverage meets 85% minimum threshold
- [ ] Coverage report reviewed for meaningful test quality
- [ ] Code formatted with `black`
- [ ] Linting passes with `ruff`
- [ ] Type checking passes with `mypy`
- [ ] All changes committed with conventional commit messages
- [ ] All commits pushed to remote repository
- [ ] .ralph/fix_plan.md task marked as complete
- [ ] Implementation documentation updated
- [ ] Inline code comments updated or added
- [ ] .ralph/AGENT.md updated (if new patterns introduced)
- [ ] Breaking changes documented
- [ ] Features tested within Ralph loop (if applicable)

### Rationale

These standards ensure:
- **Quality**: High test coverage and pass rates prevent regressions
- **Traceability**: Git commits and .ralph/fix_plan.md provide clear history of changes
- **Maintainability**: Current documentation reduces onboarding time and prevents knowledge loss
- **Collaboration**: Pushed changes enable team visibility and code review
- **Reliability**: Consistent quality gates maintain production stability
- **Automation**: Ralph integration ensures continuous development practices

**Enforcement**: AI agents should automatically apply these standards to all feature development tasks without requiring explicit instruction for each task.

---

## Performance Considerations

### Async Optimization
- Use connection pooling with httpx
- Limit concurrent requests to avoid overwhelming APIs
- Implement timeouts for all network operations
- Cache results when appropriate

### Memory Management
- Stream large responses instead of loading entirely into memory
- Use generators for result processing when possible
- Clean up resources in finally blocks

### Rate Limiting
- Respect Tavily API rate limits
- Implement exponential backoff for retries
- Track usage per API key for rotation
- Alert users when approaching limits

---

## Security Considerations

- Never log or print API keys
- Use environment variables or config files for sensitive data
- Sanitize user input before using in queries
- Validate URLs before making requests
- Use HTTPS for all network requests
- Implement proper error handling to avoid leaking information
