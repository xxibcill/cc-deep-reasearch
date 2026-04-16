'use client'

import type { ArgumentBeatClaim, ArgumentClaim, ArgumentCounterargument, ArgumentProofAnchor, PipelineContext } from '@/types/content-gen'
import { SectionList, SummaryField } from './ui'

function renderProofAnchor(anchor: ArgumentProofAnchor): string {
  const sourceIds = anchor.source_ids.length ? `Sources: ${anchor.source_ids.join(', ')}` : ''
  const usageNote = anchor.usage_note ? `Usage: ${anchor.usage_note}` : ''
  return [anchor.summary, sourceIds, usageNote].filter(Boolean).join(' | ')
}

function renderClaim(claim: ArgumentClaim): string {
  const proofIds = claim.supporting_proof_ids.length
    ? `Proof: ${claim.supporting_proof_ids.join(', ')}`
    : ''
  return [claim.claim, proofIds, claim.note].filter(Boolean).join(' | ')
}

function renderCounterargument(counterargument: ArgumentCounterargument): string {
  const proofIds = counterargument.response_proof_ids.length
    ? `Response proof: ${counterargument.response_proof_ids.join(', ')}`
    : ''
  return [counterargument.counterargument, counterargument.response, proofIds]
    .filter(Boolean)
    .join(' | ')
}

function renderBeatPlan(beat: ArgumentBeatClaim): string {
  const claims = beat.claim_ids.length ? `Claims: ${beat.claim_ids.join(', ')}` : ''
  const proof = beat.proof_anchor_ids.length ? `Proof: ${beat.proof_anchor_ids.join(', ')}` : ''
  const counters = beat.counterargument_ids.length
    ? `Counters: ${beat.counterargument_ids.join(', ')}`
    : ''
  return [beat.beat_name, beat.goal, claims, proof, counters, beat.transition_note]
    .filter(Boolean)
    .join(' | ')
}

export function BuildArgumentMapPanel({ ctx }: { ctx: PipelineContext }) {
  if (!ctx.argument_map) {
    return null
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <SummaryField
          label="Thesis"
          value={ctx.argument_map.thesis || 'No thesis recorded'}
        />
        <SummaryField
          label="Core mechanism"
          value={ctx.argument_map.core_mechanism || 'No mechanism recorded'}
        />
        <SummaryField
          label="Fact-risk decision"
          value={ctx.fact_risk_gate?.decision || 'No early fact-risk gate recorded'}
        />
        <SummaryField
          label="Fact-risk rationale"
          value={ctx.fact_risk_gate?.decision_reason || 'No early fact-risk rationale recorded'}
        />
      </div>

      <SummaryField
        label="Audience belief to challenge"
        value={
          ctx.argument_map.audience_belief_to_challenge || 'No audience belief recorded'
        }
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionList
          label="Proof anchors"
          items={ctx.argument_map.proof_anchors.map(renderProofAnchor)}
          emptyLabel="No proof anchors"
        />
        <SectionList
          label="Beat claim plan"
          items={ctx.argument_map.beat_claim_plan.map(renderBeatPlan)}
          emptyLabel="No beat plan"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionList
          label="Safe claims"
          items={ctx.argument_map.safe_claims.map(renderClaim)}
          emptyLabel="No safe claims"
        />
        <SectionList
          label="Unsafe claims"
          items={ctx.argument_map.unsafe_claims.map(renderClaim)}
          emptyLabel="No unsafe claims"
        />
      </div>

      <SectionList
        label="Counterarguments"
        items={ctx.argument_map.counterarguments.map(renderCounterargument)}
        emptyLabel="No counterarguments"
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <SummaryField
          label="Contribution"
          value={ctx.argument_map.what_this_contributes || null}
        />
        <SummaryField
          label="Differentiation strategy"
          value={ctx.argument_map.differentiation_stategy || null}
        />
      </div>

      <SectionList
        label="Genericity flags"
        items={ctx.argument_map.genericity_flags ?? []}
        emptyLabel="No genericity flags"
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionList
          label="Hold resolution requirements"
          items={ctx.fact_risk_gate?.hold_resolution_requirements ?? []}
          emptyLabel="No hold requirements recorded"
        />
        <SectionList
          label="Proof checks"
          items={ctx.fact_risk_gate?.proof_check_results ?? []}
          emptyLabel="No proof checks recorded"
        />
      </div>
    </div>
  )
}
