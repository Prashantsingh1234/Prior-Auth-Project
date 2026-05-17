import { useState, useCallback } from 'react'

// ─── Types ────────────────────────────────────────────────────────────────────

export type StepType =
  | 'retrieve'
  | 'parse'
  | 'evidence_gather'
  | 'evaluate'
  | 'aggregate'
  | 'conclude'

export type StepStatus = 'pending' | 'running' | 'done' | 'failed'

export type CriterionStatus = 'MET' | 'NOT_MET' | 'INSUFFICIENT' | 'NOT_APPLICABLE'

export interface ReasoningStep {
  id:         string
  type:       StepType
  label:      string
  detail:     string
  status:     StepStatus
  latencyMs:  number
  tokenCount: number
  model:      string
  criterionId?: string
  inputChunks?: string[]
  outputSummary: string
  confidence?: number
}

export interface RetrievedChunk {
  id:         string
  sourceDoc:  string
  page:       number
  text:       string
  similarity: number
  usedIn:     string[]  // criterionIds
}

export interface EvidenceNode {
  id:       string
  label:    string
  type:     'lab_value' | 'clinical_note' | 'imaging' | 'medication' | 'diagnosis' | 'functional'
  value:    string
  page:     number
  excerpt:  string
  confidence: number
}

export interface PolicyNode {
  id:         string
  criterionId: string
  label:      string
  requirement: string
  status:     CriterionStatus
  confidence: number
  weight:     number
}

export interface EvidenceMapping {
  evidenceId: string
  policyId:   string
  strength:   number  // 0-1
  type:       'supports' | 'conflicts' | 'partial'
}

export interface CriterionDependency {
  fromId: string
  toId:   string
  type:   'requires' | 'enhances' | 'blocks'
}

export interface HeatmapCell {
  criterionId:  string
  evidenceType: string
  confidence:   number
  count:        number
}

export interface ModelExecution {
  model:      string
  provider:   string
  role:       string
  isFallback: boolean
  latencyMs:  number
  inputTokens:  number
  outputTokens: number
  totalCost:    number
  steps:        string[]
}

export interface RAGChain {
  query:       string
  retrieved:   number
  filtered:    number
  latencyMs:   number
  topK:        number
  threshold:   number
  embedModel:  string
}

export interface ReasoningData {
  caseId:         string
  patientName:    string
  procedure:      string
  decision:       'APPROVED' | 'DENIED' | 'PENDING'
  overallConfidence: number
  totalLatencyMs: number
  totalTokens:    number
  steps:          ReasoningStep[]
  chunks:         RetrievedChunk[]
  evidenceNodes:  EvidenceNode[]
  policyNodes:    PolicyNode[]
  mappings:       EvidenceMapping[]
  dependencies:   CriterionDependency[]
  heatmap:        HeatmapCell[]
  modelChain:     ModelExecution[]
  ragChain:       RAGChain
}

// ─── Mock data ────────────────────────────────────────────────────────────────

const STEPS: ReasoningStep[] = [
  {
    id: 's1', type: 'retrieve', label: 'Policy Retrieval', status: 'done',
    detail: 'Vector search across 2,847 UHC policy documents',
    latencyMs: 312, tokenCount: 0, model: 'text-embedding-3-large',
    inputChunks: [],
    outputSummary: 'Retrieved 14 relevant policy chunks; top-k=8 after threshold filter (sim ≥ 0.72)',
    confidence: 0.96,
  },
  {
    id: 's2', type: 'parse', label: 'Document Parse', status: 'done',
    detail: 'Extract structured fields from OCR output',
    latencyMs: 184, tokenCount: 2840, model: 'claude-haiku-4-5-20251001',
    outputSummary: 'Extracted 47 structured fields; 12 entities flagged for cross-reference',
    confidence: 0.974,
  },
  {
    id: 's3', type: 'evidence_gather', label: 'Evidence Collection', status: 'done',
    detail: 'Map extracted fields to policy requirements',
    latencyMs: 228, tokenCount: 3610, model: 'claude-haiku-4-5-20251001',
    outputSummary: 'Collected 18 evidence items across 6 criteria; 2 requiring inference',
    confidence: 0.941,
  },
  {
    id: 's4', type: 'evaluate', label: 'Criterion C1: Conservative Tx', status: 'done',
    detail: 'Evaluate ≥3 months conservative treatment documented', criterionId: 'c1',
    latencyMs: 891, tokenCount: 4220, model: 'claude-sonnet-4-6',
    inputChunks: ['chunk-1', 'chunk-3', 'chunk-7'],
    outputSummary: 'PT records document 6 months conservative treatment — MEETS threshold. High confidence.',
    confidence: 0.97,
  },
  {
    id: 's5', type: 'evaluate', label: 'Criterion C2: Radiographic', status: 'done',
    detail: 'Evaluate radiographic evidence of severe joint degeneration', criterionId: 'c2',
    latencyMs: 743, tokenCount: 3890, model: 'claude-sonnet-4-6',
    inputChunks: ['chunk-2', 'chunk-5'],
    outputSummary: 'X-ray report confirms Kellgren-Lawrence Grade IV bilateral OA — MEETS criterion.',
    confidence: 0.93,
  },
  {
    id: 's6', type: 'evaluate', label: 'Criterion C3: Functional Impairment', status: 'done',
    detail: 'Validate documented functional limitation score', criterionId: 'c3',
    latencyMs: 618, tokenCount: 3140, model: 'claude-sonnet-4-6',
    inputChunks: ['chunk-4', 'chunk-6'],
    outputSummary: 'WOMAC score 68/100 documented; walking distance <50m — MEETS functional impairment criterion.',
    confidence: 0.89,
  },
  {
    id: 's7', type: 'evaluate', label: 'Criterion C4: BMI', status: 'done',
    detail: 'Verify BMI within acceptable surgical range', criterionId: 'c4',
    latencyMs: 204, tokenCount: 1820, model: 'claude-haiku-4-5-20251001',
    inputChunks: ['chunk-8'],
    outputSummary: 'BMI 27.4 — within policy range <40. MEETS criterion with high confidence.',
    confidence: 0.99,
  },
  {
    id: 's8', type: 'evaluate', label: 'Criterion C5: Bone Density', status: 'done',
    detail: 'Assess bone density suitability for implant anchoring', criterionId: 'c5',
    latencyMs: 312, tokenCount: 2100, model: 'claude-haiku-4-5-20251001',
    inputChunks: [],
    outputSummary: 'No DEXA scan ordered for standard TKA — NOT APPLICABLE per policy section 4.2.1.',
    confidence: 0.88,
  },
  {
    id: 's9', type: 'evaluate', label: 'Criterion C6: Cardiac Clearance', status: 'done',
    detail: 'Confirm pre-operative cardiac evaluation', criterionId: 'c6',
    latencyMs: 441, tokenCount: 2760, model: 'claude-sonnet-4-6',
    inputChunks: ['chunk-9', 'chunk-11'],
    outputSummary: 'Cardiology clearance note dated 2025-10-28 present — MEETS criterion.',
    confidence: 0.96,
  },
  {
    id: 's10', type: 'aggregate', label: 'Score Aggregation', status: 'done',
    detail: 'Weighted scoring across all evaluated criteria',
    latencyMs: 167, tokenCount: 1940, model: 'claude-sonnet-4-6',
    outputSummary: '5/5 applicable criteria met. Weighted confidence 0.941. No guardrail flags triggered.',
    confidence: 0.941,
  },
  {
    id: 's11', type: 'conclude', label: 'Final Decision', status: 'done',
    detail: 'Generate recommendation with rationale summary',
    latencyMs: 823, tokenCount: 5120, model: 'claude-sonnet-4-6',
    outputSummary: 'RECOMMENDATION: APPROVE. All applicable PA criteria satisfied. Clinical necessity well-documented.',
    confidence: 0.941,
  },
]

const CHUNKS: RetrievedChunk[] = [
  {
    id: 'chunk-1', sourceDoc: 'Physical Therapy Notes', page: 2, similarity: 0.934,
    text: 'Patient has completed 24 weeks of supervised physical therapy including quadriceps strengthening, gait training, and aquatic therapy. No significant improvement in pain or function noted.',
    usedIn: ['c1'],
  },
  {
    id: 'chunk-2', sourceDoc: 'Radiology Report', page: 1, similarity: 0.911,
    text: 'AP and lateral weight-bearing radiographs demonstrate severe tricompartmental osteoarthritis with complete medial joint space obliteration. Kellgren-Lawrence Grade IV bilaterally.',
    usedIn: ['c2'],
  },
  {
    id: 'chunk-3', sourceDoc: 'Clinical Notes', page: 1, similarity: 0.887,
    text: 'Patient initially treated with NSAIDs (meloxicam 15mg) and corticosteroid injections (3 total over 18 months) with declining response. Trial of hyaluronic acid injections completed.',
    usedIn: ['c1'],
  },
  {
    id: 'chunk-4', sourceDoc: 'Functional Assessment', page: 1, similarity: 0.873,
    text: 'WOMAC Osteoarthritis Index score: 68/100 (severe). Patient ambulates <50 meters before pain cessation. Unable to perform ADLs without assistive device.',
    usedIn: ['c3'],
  },
  {
    id: 'chunk-5', sourceDoc: 'Radiology Report', page: 2, similarity: 0.861,
    text: 'MRI confirms full-thickness cartilage loss in medial compartment. Bone marrow edema and subchondral sclerosis consistent with end-stage degenerative joint disease.',
    usedIn: ['c2'],
  },
  {
    id: 'chunk-6', sourceDoc: 'Clinical Notes', page: 3, similarity: 0.849,
    text: 'VAS pain score 8/10 at rest, 10/10 with ambulation. Significant impact on quality of life including inability to work and sleep disturbance.',
    usedIn: ['c3'],
  },
  {
    id: 'chunk-7', sourceDoc: 'PT Discharge Summary', page: 1, similarity: 0.836,
    text: 'Discharge from PT program after 6 months. All conservative modalities exhausted. Orthopedic surgical consultation recommended.',
    usedIn: ['c1'],
  },
  {
    id: 'chunk-8', sourceDoc: 'Pre-op Workup', page: 1, similarity: 0.821,
    text: 'Height 175cm, Weight 84kg. BMI 27.4. No morbid obesity. Patient deemed appropriate surgical candidate from weight perspective.',
    usedIn: ['c4'],
  },
  {
    id: 'chunk-9', sourceDoc: 'Cardiology Consult', page: 1, similarity: 0.809,
    text: 'EKG normal sinus rhythm. Echo EF 62%. No significant valvular disease. Cleared for elective surgical procedure under general or spinal anesthesia.',
    usedIn: ['c6'],
  },
  {
    id: 'chunk-10', sourceDoc: 'UHC Policy LCD-2024', page: 4, similarity: 0.798,
    text: 'CPT 27447 (Total Knee Arthroplasty) requires: documented failure of ≥3 months conservative care, radiographic evidence of severe OA, functional impairment score ≥50/100.',
    usedIn: ['c1', 'c2', 'c3'],
  },
  {
    id: 'chunk-11', sourceDoc: 'Cardiology Consult', page: 2, similarity: 0.786,
    text: 'Surgical clearance granted 2025-10-28. Recommend continuation of aspirin 81mg perioperatively. No cardiac contraindications identified.',
    usedIn: ['c6'],
  },
]

const EVIDENCE_NODES: EvidenceNode[] = [
  { id: 'e1', label: 'PT Duration', type: 'clinical_note', value: '6 months', page: 2, confidence: 0.97, excerpt: '24 weeks of supervised physical therapy...' },
  { id: 'e2', label: 'KL Grade', type: 'imaging', value: 'Grade IV', page: 1, confidence: 0.93, excerpt: 'Kellgren-Lawrence Grade IV bilaterally' },
  { id: 'e3', label: 'WOMAC Score', type: 'functional', value: '68/100', page: 1, confidence: 0.91, excerpt: 'WOMAC Osteoarthritis Index score: 68/100' },
  { id: 'e4', label: 'BMI', type: 'lab_value', value: '27.4', page: 1, confidence: 0.99, excerpt: 'BMI 27.4. No morbid obesity.' },
  { id: 'e5', label: 'Cardiac Clearance', type: 'clinical_note', value: 'Cleared', page: 1, confidence: 0.96, excerpt: 'Cleared for elective surgical procedure' },
  { id: 'e6', label: 'Cartilage Loss', type: 'imaging', value: 'Full-thickness', page: 2, confidence: 0.93, excerpt: 'Full-thickness cartilage loss in medial compartment' },
  { id: 'e7', label: 'VAS Pain', type: 'functional', value: '8-10/10', page: 3, confidence: 0.89, excerpt: 'VAS pain score 8/10 at rest, 10/10 with ambulation' },
  { id: 'e8', label: 'Injection Trials', type: 'medication', value: '3 injections', page: 1, confidence: 0.94, excerpt: 'corticosteroid injections (3 total over 18 months)' },
]

const POLICY_NODES: PolicyNode[] = [
  { id: 'p1', criterionId: 'c1', label: 'Conservative Tx', requirement: '≥3 months conservative treatment', status: 'MET', confidence: 0.97, weight: 0.25 },
  { id: 'p2', criterionId: 'c2', label: 'Radiographic', requirement: 'Radiographic evidence of severe OA', status: 'MET', confidence: 0.93, weight: 0.25 },
  { id: 'p3', criterionId: 'c3', label: 'Functional', requirement: 'Functional impairment ≥50/100', status: 'MET', confidence: 0.89, weight: 0.20 },
  { id: 'p4', criterionId: 'c4', label: 'BMI Range', requirement: 'BMI <40', status: 'MET', confidence: 0.99, weight: 0.15 },
  { id: 'p5', criterionId: 'c5', label: 'Bone Density', requirement: 'Adequate bone density for implant', status: 'NOT_APPLICABLE', confidence: 0.88, weight: 0.05 },
  { id: 'p6', criterionId: 'c6', label: 'Cardiac Clearance', requirement: 'Pre-op cardiac evaluation', status: 'MET', confidence: 0.96, weight: 0.10 },
]

const MAPPINGS: EvidenceMapping[] = [
  { evidenceId: 'e1', policyId: 'p1', strength: 0.97, type: 'supports' },
  { evidenceId: 'e8', policyId: 'p1', strength: 0.88, type: 'supports' },
  { evidenceId: 'e2', policyId: 'p2', strength: 0.93, type: 'supports' },
  { evidenceId: 'e6', policyId: 'p2', strength: 0.91, type: 'supports' },
  { evidenceId: 'e3', policyId: 'p3', strength: 0.91, type: 'supports' },
  { evidenceId: 'e7', policyId: 'p3', strength: 0.87, type: 'supports' },
  { evidenceId: 'e4', policyId: 'p4', strength: 0.99, type: 'supports' },
  { evidenceId: 'e5', policyId: 'p6', strength: 0.96, type: 'supports' },
]

const DEPENDENCIES: CriterionDependency[] = [
  { fromId: 'p1', toId: 'p2', type: 'enhances' },
  { fromId: 'p1', toId: 'p3', type: 'enhances' },
  { fromId: 'p4', toId: 'p2', type: 'requires' },
  { fromId: 'p6', toId: 'p2', type: 'requires' },
]

const HEATMAP: HeatmapCell[] = [
  // c1
  { criterionId: 'c1', evidenceType: 'clinical_note', confidence: 0.97, count: 3 },
  { criterionId: 'c1', evidenceType: 'medication', confidence: 0.88, count: 2 },
  { criterionId: 'c1', evidenceType: 'functional', confidence: 0.72, count: 1 },
  { criterionId: 'c1', evidenceType: 'imaging', confidence: 0.45, count: 1 },
  { criterionId: 'c1', evidenceType: 'lab_value', confidence: 0.12, count: 0 },
  // c2
  { criterionId: 'c2', evidenceType: 'imaging', confidence: 0.93, count: 4 },
  { criterionId: 'c2', evidenceType: 'clinical_note', confidence: 0.71, count: 1 },
  { criterionId: 'c2', evidenceType: 'functional', confidence: 0.38, count: 1 },
  { criterionId: 'c2', evidenceType: 'lab_value', confidence: 0.14, count: 0 },
  { criterionId: 'c2', evidenceType: 'medication', confidence: 0.09, count: 0 },
  // c3
  { criterionId: 'c3', evidenceType: 'functional', confidence: 0.91, count: 3 },
  { criterionId: 'c3', evidenceType: 'clinical_note', confidence: 0.74, count: 2 },
  { criterionId: 'c3', evidenceType: 'imaging', confidence: 0.52, count: 1 },
  { criterionId: 'c3', evidenceType: 'medication', confidence: 0.22, count: 0 },
  { criterionId: 'c3', evidenceType: 'lab_value', confidence: 0.11, count: 0 },
  // c4
  { criterionId: 'c4', evidenceType: 'lab_value', confidence: 0.99, count: 2 },
  { criterionId: 'c4', evidenceType: 'clinical_note', confidence: 0.41, count: 1 },
  { criterionId: 'c4', evidenceType: 'imaging', confidence: 0.08, count: 0 },
  { criterionId: 'c4', evidenceType: 'functional', confidence: 0.07, count: 0 },
  { criterionId: 'c4', evidenceType: 'medication', confidence: 0.06, count: 0 },
  // c5
  { criterionId: 'c5', evidenceType: 'lab_value', confidence: 0.15, count: 0 },
  { criterionId: 'c5', evidenceType: 'imaging', confidence: 0.12, count: 0 },
  { criterionId: 'c5', evidenceType: 'clinical_note', confidence: 0.09, count: 0 },
  { criterionId: 'c5', evidenceType: 'functional', confidence: 0.06, count: 0 },
  { criterionId: 'c5', evidenceType: 'medication', confidence: 0.05, count: 0 },
  // c6
  { criterionId: 'c6', evidenceType: 'clinical_note', confidence: 0.96, count: 3 },
  { criterionId: 'c6', evidenceType: 'lab_value', confidence: 0.67, count: 2 },
  { criterionId: 'c6', evidenceType: 'imaging', confidence: 0.31, count: 1 },
  { criterionId: 'c6', evidenceType: 'functional', confidence: 0.09, count: 0 },
  { criterionId: 'c6', evidenceType: 'medication', confidence: 0.08, count: 0 },
]

const MODEL_CHAIN: ModelExecution[] = [
  {
    model: 'text-embedding-3-large', provider: 'OpenAI', role: 'RAG Embedding',
    isFallback: false, latencyMs: 312, inputTokens: 0, outputTokens: 0, totalCost: 0.0004,
    steps: ['s1'],
  },
  {
    model: 'claude-haiku-4-5-20251001', provider: 'Anthropic', role: 'Extraction & Parsing',
    isFallback: false, latencyMs: 616, inputTokens: 9770, outputTokens: 2340, totalCost: 0.0018,
    steps: ['s2', 's3', 's7', 's8'],
  },
  {
    model: 'claude-sonnet-4-6', provider: 'Anthropic', role: 'Criterion Evaluation',
    isFallback: false, latencyMs: 3516, inputTokens: 24110, outputTokens: 6880, totalCost: 0.0341,
    steps: ['s4', 's5', 's6', 's9', 's10', 's11'],
  },
]

const RAG_CHAIN: RAGChain = {
  query: 'CPT 27447 total knee arthroplasty prior authorization criteria UHC PPO',
  retrieved: 24, filtered: 11, latencyMs: 312, topK: 11, threshold: 0.72,
  embedModel: 'text-embedding-3-large',
}

const MOCK_DATA: ReasoningData = {
  caseId: 'PA-2024-18847',
  patientName: 'James R. Mitchell',
  procedure: 'Total Knee Arthroplasty (CPT 27447)',
  decision: 'APPROVED',
  overallConfidence: 0.941,
  totalLatencyMs: 4863,
  totalTokens: 42440,
  steps: STEPS,
  chunks: CHUNKS,
  evidenceNodes: EVIDENCE_NODES,
  policyNodes: POLICY_NODES,
  mappings: MAPPINGS,
  dependencies: DEPENDENCIES,
  heatmap: HEATMAP,
  modelChain: MODEL_CHAIN,
  ragChain: RAG_CHAIN,
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export interface ReasoningState {
  data:               ReasoningData
  activeStepId:       string | null
  activeEvidenceId:   string | null
  activePolicyId:     string | null
  expandedStepIds:    Set<string>
  setActiveStep:      (id: string | null) => void
  setActiveEvidence:  (id: string | null) => void
  setActivePolicy:    (id: string | null) => void
  toggleStep:         (id: string) => void
  highlightedMapping: EvidenceMapping | null
}

export function useReasoningData(): ReasoningState {
  const [activeStepId, setActiveStepId]       = useState<string | null>(null)
  const [activeEvidenceId, setActiveEvidenceId] = useState<string | null>(null)
  const [activePolicyId, setActivePolicyId]   = useState<string | null>(null)
  const [expandedStepIds, setExpandedStepIds] = useState<Set<string>>(new Set(['s11']))

  const setActiveStep     = useCallback((id: string | null) => setActiveStepId(id), [])
  const setActiveEvidence = useCallback((id: string | null) => setActiveEvidenceId(id), [])
  const setActivePolicy   = useCallback((id: string | null) => setActivePolicyId(id), [])

  const toggleStep = useCallback((id: string) => {
    setExpandedStepIds((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }, [])

  const highlightedMapping = activeEvidenceId && activePolicyId
    ? MOCK_DATA.mappings.find(
        (m) => m.evidenceId === activeEvidenceId && m.policyId === activePolicyId
      ) ?? null
    : null

  return {
    data: MOCK_DATA,
    activeStepId,
    activeEvidenceId,
    activePolicyId,
    expandedStepIds,
    setActiveStep,
    setActiveEvidence,
    setActivePolicy,
    toggleStep,
    highlightedMapping,
  }
}
