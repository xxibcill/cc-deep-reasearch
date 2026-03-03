# CC Deep Research - Report Quality Improvement Plan

## Executive Summary

After running `cc-deep-research research "health benefit of white tea"` and analyzing the output against quality criteria, several critical issues were identified. This plan addresses those issues with prioritized improvements.

## Issues Found in Current Report

### Critical Issues

1. **Garbled/Noisy Content in Key Points**
   - Example: `"- Benefits, Taste, Uses Have you ever sipped a loose leaf tea so delicate..."`
   - Root Cause: `ai_executor.py:_extract_key_points()` extracts sentences without proper content cleaning
   - Impact: Reports contain marketing fluff and navigation text

2. **Semantic Incoherence (Wrong Topic Association)**
   - Example: Oral hygiene findings appear under "Weight Management Support"
   - Root Cause: `_semantic_theme_extraction()` uses simple word matching instead of semantic relevance
   - Impact: Findings don't match their themes, confusing readers

3. **Poor Description Quality**
   - Example: Theme descriptions start with unrelated key points
   - Root Cause: `_generate_description()` blindly appends first key point without relevance check
   - Impact: Descriptions are incoherent and unprofessional

### Medium Issues

4. **No Source Quality Differentiation**
   - Blog posts (nelsonstea.com) treated equally with peer-reviewed sources (PubMed)
   - No credibility scoring visible in output
   - Impact: Readers can't distinguish reliable from unreliable sources

5. **Missing Analytical Depth**
   - No discussion of mechanisms, doses, clinical evidence
   - No comparison of human vs. animal studies
   - No safety/contraindication discussion
   - Impact: Reports are superficial summaries, not deep analysis

6. **No Methodology Section**
   - Report doesn't explain how research was conducted
   - Impact: Not reproducible, lacks transparency

---

## Improvement Plan

### Phase 1: Fix Critical Content Quality Issues (HIGH PRIORITY)

#### Task 1.1: Enhance Content Cleaning in `_extract_key_points()`
**File**: `src/cc_deep_research/agents/ai_executor.py`

Changes needed:
- [ ] Improve `_clean_sentence()` to remove more artifacts:
  - Remove sentences starting with `-` or other markdown list markers
  - Remove sentences with marketing language ("Have you ever", "Discover", "Learn more")
  - Remove sentences with incomplete phrases
  - Remove sentences that are questions
  - Remove sentences with URL fragments or navigation text
- [ ] Add semantic relevance check in `_extract_key_points()`:
  - Only include sentences where topic-specific keywords appear together
  - Use topic-specific word sets, not just topic name words

#### Task 1.2: Fix Theme-Key Point Alignment
**File**: `src/cc_deep_research/agents/ai_executor.py`

Changes needed:
- [ ] Create topic-specific keyword sets for each theme pattern
- [ ] Only assign key points to themes where they are semantically relevant
- [ ] Add validation that key points actually relate to the topic

#### Task 1.3: Improve Description Generation
**File**: `src/cc_deep_research/agents/ai_executor.py`

Changes needed:
- [ ] `_generate_description()` should:
  - Select key points that are most relevant to the topic
  - Summarize findings rather than just appending first key point
  - Validate description coherence

### Phase 2: Add Source Quality Scoring (MEDIUM PRIORITY)

#### Task 2.1: Implement Source Credibility Scoring
**File**: `src/cc_deep_research/aggregation.py` (new module or extension)

Changes needed:
- [ ] Add domain credibility database (pubmed.gov, nih.gov = high; blogs = low)
- [ ] Score sources on credibility, relevance, freshness
- [ ] Display credibility scores in report
- [ ] Prioritize high-credibility sources in analysis

#### Task 2.2: Differentiate Source Types in Report
**File**: `src/cc_deep_research/agents/reporter.py`

Changes needed:
- [ ] Mark sources as [Peer-Reviewed], [Blog], [News], etc.
- [ ] Group sources by type in Sources section
- [ ] Highlight high-credibility sources in findings

### Phase 3: Add Analytical Depth (MEDIUM PRIORITY)

#### Task 3.1: Add Methodology Section
**File**: `src/cc_deep_research/agents/reporter.py`

Changes needed:
- [ ] Add Methodology section to report structure
- [ ] Document search strategy, query expansion, source selection criteria
- [ ] Include limitations and scope

#### Task 3.2: Enhance Cross-Reference Analysis
**File**: `src/cc_deep_research/agents/ai_analysis_service.py`

Changes needed:
- [ ] Distinguish between human studies, animal studies, in vitro studies
- [ ] Identify conflicting evidence and explain contradictions
- [ ] Add confidence levels based on evidence quality

#### Task 3.3: Add Safety and Contraindications Section
**File**: `src/cc_deep_research/agents/reporter.py`

Changes needed:
- [ ] Add dedicated section for safety, side effects, contraindications
- [ ] Extract this information from sources during analysis

---

## Implementation Priority

### Immediate (Next Loop)
1. [x] Fix `_clean_sentence()` to remove garbled content
2. [x] Fix `_extract_key_points()` to ensure semantic relevance
3. [x] Fix `_generate_description()` to create coherent descriptions

### Short-term (After Immediate)
4. [ ] Add source credibility scoring
5. [ ] Add methodology section to reports

### Medium-term
6. [ ] Add analytical depth improvements
7. [ ] Add safety/contraindication extraction

---

## Success Criteria

After implementing improvements, running the same query should produce:

1. **Clean key points** - No marketing text, no navigation artifacts
2. **Coherent themes** - Key points actually relate to their themes
3. **Professional descriptions** - Each theme has a clear, relevant summary
4. **Source differentiation** - Readers can identify credible sources
5. **Methodology transparency** - Research process is documented
6. **Analytical depth** - Beyond surface summarization

---

## Verification

After each phase, run:
```bash
uv run cc-deep-research research "health benefit of white tea" --monitor --output test_output.md --depth quick
```

Compare output against quality criteria:
- Clear structure and defined scope
- Claims supported by citations
- Facts distinguished from interpretations
- Analytical depth, not surface summarization
- No marketing language or fluff
- Reproducible methodology
