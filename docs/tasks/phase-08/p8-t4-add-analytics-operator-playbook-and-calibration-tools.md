# P8-T4: Add Analytics, Operator Playbook, and Calibration Tools

## Summary

Add telemetry views, operator documentation, and basic calibration tools for V1 rollout of the Radar feature.

## Details

### What to implement

1. **Radar telemetry store** in `radar/telemetry.py`
   - `RadarTelemetryStore` class that aggregates feedback and conversion metrics
   - Methods: `get_feedback_stats()`, `get_conversion_rates()`, `get_opportunity_funnel()`
   - Stores analytics in `~/.config/cc-deep-research/radar/analytics/` directory

2. **Analytics data structures** in `radar/models.py`
   ```python
   class RadarAnalytics(BaseModel):
       total_opportunities: int
       opportunities_by_status: dict[str, int]
       opportunities_by_type: dict[str, int]
       feedback_counts: dict[str, int]
       conversion_rates: dict[str, float]
       avg_time_to_action: float | None
       top_opportunity_types: list[tuple[str, int]]
   ```

3. **API endpoints for radar analytics** in `radar/router.py`
   - `GET /api/radar/analytics` - Returns RadarAnalytics summary
   - `GET /api/radar/analytics/funnel` - Returns conversion funnel data
   - `GET /api/radar/analytics/feedback-trends` - Returns feedback trends over time

4. **Frontend analytics page** in `dashboard/src/app/radar/analytics/page.tsx`
   - Summary cards: total opportunities, conversion rate, avg score
   - Funnel visualization: new → saved → acted_on conversion
   - Feedback breakdown chart
   - Top opportunity types

5. **Operator playbook documentation** in `docs/radar/operator-playbook.md`
   - How to interpret opportunity scores
   - Calibration guide for tuning scoring weights
   - How to use feedback data to improve ranking
   - Troubleshooting common issues

6. **Calibration helpers** in `radar/engine.py`
   - `ScoreCalculator.set_weight(dimension, weight)` for runtime weight adjustment
   - Default weights are documented and can be overridden via config

### Exit criteria

- Analytics endpoint returns structured RadarAnalytics data
- Frontend analytics page displays summary metrics and funnel
- Operator playbook documentation exists and covers key scenarios
- Calibration weights are exposed for operator tuning
