# P2-T3: Build Structured Editors for Nested Strategy Objects

## Summary
Add structured editors for audience, proof, CTA, platform, and evidence-related strategy data.

## Details
The following nested strategy objects need dedicated editors replacing comma-separated text inputs:

### Audience Segments (`audience_segments`)
- `AudienceSegment` has: name, description, pain_points[]
- Render as expandable cards with inline edit for name/description
- pain_points as a tag-input list (add/remove tags, not comma-separated)

### Platforms (`platforms`, `platform_rules`)
- `platforms` is a string[] - replace comma-separated with tag-input
- `platform_rules` is `PlatformRule[]` - structured editor with: platform, format_preferences[], length_constraints, style_constraints[], cta_norms[]

### Proof Standards & Forbidden Claims
- `proof_standards` string[] - tag-input list
- `forbidden_claims` string[] - tag-input list
- `forbidden_topics` string[] - tag-input list

### CTA Policy (`offer_cta_rules`, `cta_strategy`)
- `offer_cta_rules` string[] - tag-input list
- `cta_strategy` (`CTAStrategy`) has: allowed_cta_types[], default_by_content_goal{}
- Structured editor for the CTAStrategy object

### Past Winners/Losers (`past_winners`, `past_losers`)
- `ContentExample` has: title, why_it_worked_or_failed, metrics_snapshot{}
- Render as cards with expand/edit, not raw JSON

## Exit Criteria
- All nested list fields use tag-input or structured editors, not comma-separated text
- `AudienceSegment`, `PlatformRule`, `CTAStrategy`, `ContentExample` all have dedicated card-based editors
- Tag-input pattern is used consistently for simple string[] fields across all sections

## Dependencies
- P2-T1 (workspace) provides the tab/section framework
- P2-T2 (pillar management) may share drag-and-drop infrastructure
