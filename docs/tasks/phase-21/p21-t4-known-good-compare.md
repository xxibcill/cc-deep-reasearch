# P21-T4: Known-Good Compare Flow

## Summary

Improve compare workflows so failed or degraded runs can be reviewed against known-good baselines quickly.

## Details

1. Add a compare entry point from failed, interrupted, or degraded sessions.
2. Suggest candidate baseline sessions using query similarity, depth, status, report availability, and recency.
3. Make the compare page distinguish baseline and target roles clearly.
4. Highlight differences in phases, tool failures, LLM route behavior, source counts, duration, and generated outputs.
5. Preserve existing manual compare selection behavior.
6. Add tests for candidate suggestions and baseline/target comparison rendering.

## Acceptance Criteria

- Failed or degraded sessions offer a direct compare-against-baseline action.
- Candidate baselines exclude active or failed sessions unless explicitly requested.
- Compare UI clearly labels baseline and target sessions.
- Key differences are visible without manually scanning raw event tables.
- Existing compare links and manual selections continue to work.
