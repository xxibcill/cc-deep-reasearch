# Releasing

This project now tracks user-visible history with Semantic Versioning and [`CHANGELOG.md`](../CHANGELOG.md).

## Pre-Release Verification

Before cutting a release, run these checks to ensure the codebase is in a releasable state:

### Canonical Preflight

```bash
./scripts/preflight
```

This checks the Python lock, lint, types, and full test suite, then validates the
dashboard with lint, unit tests, a production build, smoke tests, and the
accessibility baseline. A release is blocked if either application fails.

## Release Workflow

### 1. Update Changelog

Add your user-visible changes to the `Unreleased` section in [`CHANGELOG.md`](../CHANGELOG.md):

```markdown
## [Unreleased]

### Added
- New feature description

### Changed
- Existing behavior change

### Fixed
- Bug fix description
```

### 2. Bump Version

Run the release helper with a semantic bump or explicit version:

```bash
uv run python scripts/bump_version.py patch
uv run python scripts/bump_version.py minor
uv run python scripts/bump_version.py 0.2.0
```

The script updates:
- [`src/cc_deep_research/__about__.py`](../src/cc_deep_research/__about__.py)
- [`README.md`](../README.md)
- [`CHANGELOG.md`](../CHANGELOG.md)

### 3. Review Changes

Verify the updated files are correct:
- Check the new version in `__about__.py`
- Verify README version matches
- Confirm changelog has your changes under the new version header

### 4. Commit and Tag

Commit the changes and create a matching Git tag:

```bash
git add -A
git commit -m "Release v0.2.0"
git tag -a v0.2.0 -m "Release v0.2.0"
git push && git push --tags
```

## Notes

- `patch`, `minor`, and `major` follow standard semantic version increments.
- An explicit `X.Y.Z` version is accepted when you need a specific target.
- If `Unreleased` is empty, the helper records a fallback note so the release still has an entry.
- Use `--dry-run` with `bump_version.py` to preview the version without modifying files.
