# Dependency Maintenance

The project uses locked Python and dashboard dependency graphs:

- `uv.lock` is the source of truth for Python installs.
- `dashboard/package-lock.json` is the only npm lockfile.
- Node.js 24 is the CI and recommended local runtime.

Dependabot checks Python, npm, and GitHub Actions dependencies weekly.

## Routine Checks

```bash
uv lock --check
uv tree --outdated --depth 1
uvx pip-audit
cd dashboard
npm outdated
npm run audit
```

Use `npm run audit:strict` when reviewing all high-severity findings.

The Python lock was fully refreshed on 2026-07-29 and had no known
vulnerabilities in `pip-audit`.

## Known Dashboard Audit Exceptions

As of 2026-07-29, the remaining dashboard findings collapse to two transitive
roots:

- `next@16.2.12` pins `postcss@8.4.31`. This is the production dependency
  finding. `npm audit fix --force` proposes an invalid downgrade to Next.js
  9.3.3.
- The supported ESLint 9 and Next.js lint-plugin graph pins old `minimatch`
  versions that depend on vulnerable `brace-expansion` releases. The patched
  major is API-incompatible with those consumers, and ESLint 10 is not yet
  accepted by the Next.js lint plugins.

Dependabot should replace these exceptions as soon as compatible upstream
releases are available. CI still blocks critical advisories.
