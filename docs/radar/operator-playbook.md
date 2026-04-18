# Radar Operator Playbook

This playbook provides guidance for operators deploying and tuning the Opportunity Radar feature.

## Understanding Opportunity Scores

Opportunities are scored across six dimensions, weighted as follows:

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Strategic Relevance | 30% | How well the topic matches your stated strategy and industry focus |
| Business Value | 20% | Expected impact of acting on this opportunity |
| Urgency | 15% | Time-sensitivity of the topic |
| Evidence | 15% | Number of corroborating signals |
| Novelty | 10% | How recently this topic emerged |
| Workflow Fit | 10% | How actionable this opportunity is right now |

### Priority Labels

Priority labels are derived from the total score:

- **Act Now** (80+): Immediate attention required. High strategic relevance and recent activity.
- **High Potential** (60-79): Strong opportunity worth pursuing soon.
- **Monitor** (40-59): Valid opportunity but not urgent.
- **Low Priority** (<40): May be worth revisiting later.

## Calibration Guide

### Tuning Scoring Weights

The default scoring weights are designed for general use. To calibrate for your specific context:

1. **Higher Strategic Relevance weight**: If you need fewer but more strategically aligned opportunities
2. **Higher Business Value weight**: If you want to prioritize high-impact topics
3. **Higher Urgency weight**: If you operate in fast-moving industries

The weights are defined in `ScoreCalculator.WEIGHTS` in `radar/engine.py`.

### Adjusting Freshness Thresholds

Freshness determines how "new" an opportunity appears:

- **NEW**: Created within 6 hours
- **FRESH**: Newest signal within 24 hours
- **STALE**: Newest signal between 24-72 hours
- **EXPIRED**: Newest signal older than 72 hours

Thresholds are defined in `FreshnessManager` in `radar/engine.py`.

### Tuning Clustering

The `SignalClusterer` uses keyword overlap to group signals. Key parameters:

- `MIN_SHARED_KEYWORDS = 2`: Minimum shared keywords to cluster signals
- `CLUSTER_WINDOW_DAYS = 7`: Time window for clustering
- Similarity threshold `0.15`: Cosine similarity minimum to cluster

## Using Feedback Data

Feedback signals help the system learn from your behavior:

### Feedback Types

- **acted_on**: You took action on this opportunity
- **saved**: You saved it for later
- **dismissed**: You explicitly dismissed it
- **ignored**: You viewed it but took no action
- **converted_to_research**: Launched a research run
- **converted_to_content**: Launched a brief, backlog item, or content pipeline

### Interpreting Conversion Rates

The analytics dashboard shows conversion rates for each workflow type. A low conversion rate from "Acted On" to actual workflows may indicate:
- Opportunities are scoring well but aren't actionable enough
- The workflow launch friction is too high
- The scoring priorities don't match your actual workflow preferences

## Troubleshooting

### No Opportunities Detected

1. Check that sources are configured and active (`/radar/sources`)
2. Verify the scanner is running: look for `last_scanned_at` updates
3. Check logs for scanning errors

### Opportunities Not Updating

1. Verify the ingest cycle is running
2. Check freshness thresholds - opportunities may have moved to EXPIRED
3. Look at signal linking - ensure signals are being clustered

### Low Quality Opportunities

1. Review keyword lists in `engine.py` for your industry
2. Adjust strategic relevance keywords to match your focus
3. Increase evidence weight if you want more corroborated topics

### Score Accuracy Issues

1. Check that `why_it_matters` and `recommended_action` are being populated
2. Review the score explanation in the opportunity detail page
3. Use feedback to identify which dimensions need adjustment

## Rollout Checklist

Before going live with Radar:

- [ ] Configure at least 3-5 relevant RSS/Atom sources
- [ ] Review and adjust strategic relevance keywords for your industry
- [ ] Set up monitoring for the analytics dashboard
- [ ] Establish a feedback loop: review analytics weekly
- [ ] Document your workflow conversion preferences
- [ ] Train users on the "Act Now" workflow

## Data Retention

- Signals are stored in `~/.config/cc-deep-research/radar/radar_signals.yaml`
- Opportunities are stored in `~/.config/cc-deep-research/radar/radar_opportunities.yaml`
- Feedback history is persisted for ranking improvements
- Analytics data is computed on-demand from raw records
