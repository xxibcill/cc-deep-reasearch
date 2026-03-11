# Releasing

This project now tracks user-visible history with Semantic Versioning and [`CHANGELOG.md`](../CHANGELOG.md).

## Workflow

1. Add pending user-visible changes to the `Unreleased` section in [`CHANGELOG.md`](../CHANGELOG.md).
2. Run the release helper with a semantic bump or explicit version:

   ```bash
   uv run python scripts/bump_version.py patch
   uv run python scripts/bump_version.py minor
   uv run python scripts/bump_version.py 0.2.0
   ```

3. Review the updated files:

   - [`src/cc_deep_research/__about__.py`](../src/cc_deep_research/__about__.py)
   - [`README.md`](../README.md)
   - [`CHANGELOG.md`](../CHANGELOG.md)

4. Commit the release and create a matching Git tag such as `v0.2.0`.

## Notes

- `patch`, `minor`, and `major` follow standard semantic version increments.
- An explicit `X.Y.Z` version is accepted when you need a specific target.
- If `Unreleased` is empty, the helper records a fallback note so the release still has an entry.
