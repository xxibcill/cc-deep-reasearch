# P18-T1: Restore Build Health and Capture Baseline

## Summary

Fix the dashboard production build blocker, remove root inference ambiguity, and capture baseline performance numbers before changing runtime behavior.

## Details

1. Fix `dashboard/src/app/benchmark/page.tsx` so it imports only exports that exist in `dashboard/src/components/ui/select.tsx`, or extend the select component intentionally if the benchmark page needs the compound API.
2. Add the appropriate `turbopack.root` setting in `dashboard/next.config.js` so Next.js does not infer the workspace root from the parent lockfile.
3. Run the current verification commands from `dashboard/`:
   - `npm run build`
   - `npm run lint`
   - `npm run test`
   - `npm run test:e2e:smoke`
4. Capture baseline measurements for:
   - production build route bundle sizes
   - home route load time
   - session monitor first useful paint
   - event filter latency on a large session
   - websocket history and burst handling behavior
5. Record the baseline in a short dated verification note under `docs/tasks/`.

## Acceptance Criteria

- `npm run build` passes from `dashboard/`.
- The Next.js root inference warning is resolved or explicitly documented if it cannot be resolved safely.
- Baseline numbers exist for home load, monitor first useful paint, filter latency, websocket burst handling, and bundle size.
- No dashboard routes are removed or hidden to make the build pass.
- Any known failing verification command is documented with the exact failure and owner task.
