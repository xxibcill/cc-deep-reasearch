# P18-T7: Performance Regression Gates

## Summary

Add repeatable checks that protect the optimized dashboard against future build, workflow, and performance regressions.

## Details

1. Add or update Playwright smoke coverage for:
   - home/session list
   - session overview
   - session monitor
   - report view
   - settings
   - benchmark page
   - a representative content-gen route
2. Add a repeatable large-session fixture or generator for dashboard performance tests.
3. Add a script or documented command that records:
   - production build bundle summary
   - home route load timing
   - monitor first useful paint
   - filter interaction latency
   - websocket burst handling timing
4. Define acceptable thresholds relative to the P18-T1 baseline.
5. Document how to run the performance checks locally and in CI.
6. Add a final before/after verification note under `docs/tasks/`.

## Acceptance Criteria

- Dashboard smoke tests cover the critical workflows that optimization could break.
- A large-session performance check can be run repeatably from a clean checkout.
- Final performance numbers are documented and compared against the P18-T1 baseline.
- `npm run build`, `npm run lint`, `npm run test`, and the selected Playwright smoke suite pass.
- The phase has clear thresholds for future regression review.
