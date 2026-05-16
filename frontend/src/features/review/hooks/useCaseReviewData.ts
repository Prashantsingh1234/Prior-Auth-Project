import { useState, useCallback } from 'react'

// ─── Entity types ─────────────────────────────────────────────────────────────

export type EntityType = 'CPT' | 'ICD' | 'MEDICATION' | 'LAB_VALUE' | 'DATE' | 'PROVIDER' | 'PATIENT'

export interface DocEntity {
  id:         string
  type:       EntityType
  value:      string
  normalized: string
  context:    string
  pageIndex:  number
  confidence: number
  criterionIds: string[]
}

// ─── Document pages ───────────────────────────────────────────────────────────

export interface DocPage {
  index:    number
  label:    string
  docType:  string
  content:  PageContent[]
}

export interface PageContent {
  type:   'heading' | 'subheading' | 'paragraph' | 'divider' | 'table' | 'field-row'
  text?:  string
  label?: string
  value?: string
  rows?:  { label: string; value: string; entityId?: string }[]
  entityIds?: string[]
}

// ─── Policy criteria ──────────────────────────────────────────────────────────

export type CriterionStatus = 'MET' | 'NOT_MET' | 'INSUFFICIENT' | 'NOT_APPLICABLE'

export interface Evidence {
  id:         string
  text:       string
  source:     string
  pageIndex:  number
  entityId?:  string
  confidence: number
}

export interface ReasoningStep {
  step:   number
  type:   'retrieve' | 'compare' | 'evaluate' | 'conclude'
  text:   string
}

export interface PolicyCriterion {
  id:            string
  policyRef:     string
  requirement:   string
  status:        CriterionStatus
  rationale:     string
  confidence:    number
  evidence:      Evidence[]
  reasoningSteps: ReasoningStep[]
  groundingScore: number
  hallucinationRisk: 'LOW' | 'MEDIUM' | 'HIGH'
}

// ─── Review case ──────────────────────────────────────────────────────────────

export interface ReviewCase {
  id:          string
  caseNumber:  string
  status:      string
  priority:    'ROUTINE' | 'URGENT' | 'EMERGENT'
  patient: {
    name:      string
    dob:       string
    memberId:  string
    plan:      string
    gender:    string
    age:       number
  }
  provider: {
    name:      string
    npi:       string
    org:       string
    specialty: string
    phone:     string
  }
  procedure: {
    cptCode:   string
    description: string
    icdCodes:  string[]
    requestedAt: string
    urgency:   string
  }
  ai: {
    recommendation:  'APPROVE' | 'DENY' | 'REQUEST_INFO' | 'ESCALATE'
    confidence:      number
    metCriteria:     number
    totalCriteria:   number
    processedAt:     string
    modelVersion:    string
  }
}

export interface AuditEntry {
  id:        string
  type:      string
  actor:     string
  role:      string
  note?:     string
  ts:        Date
}

// ─── Mock data ────────────────────────────────────────────────────────────────

const CASE: ReviewCase = {
  id: 'PA-2024-1247',
  caseNumber: 'PA-2024-1247',
  status: 'UNDER_REVIEW',
  priority: 'URGENT',
  patient: {
    name: 'James Mitchell',
    dob:  '1958-04-12',
    memberId: 'UHC-4821937',
    plan: 'UnitedHealth PPO Gold',
    gender: 'Male',
    age: 66,
  },
  provider: {
    name:      'Dr. Sarah Chen, MD',
    npi:       '1497836254',
    org:       'Westside Orthopedic Associates',
    specialty: 'Orthopedic Surgery',
    phone:     '(310) 555-0142',
  },
  procedure: {
    cptCode:     '27447',
    description: 'Total Knee Arthroplasty, Right Knee',
    icdCodes:    ['M17.11', 'Z96.651', 'M25.361'],
    requestedAt: new Date(Date.now() - 4 * 3600000).toISOString(),
    urgency:     'Elective',
  },
  ai: {
    recommendation: 'APPROVE',
    confidence:      0.924,
    metCriteria:     5,
    totalCriteria:   6,
    processedAt:     new Date(Date.now() - 2 * 3600000).toISOString(),
    modelVersion:    'claude-sonnet-4-6 + RAG v3.1',
  },
}

export const ENTITIES: DocEntity[] = [
  { id: 'e1', type: 'CPT',        value: '27447',    normalized: 'Total Knee Arthroplasty',        context: 'Procedure: 27447',            pageIndex: 0, confidence: 0.99, criterionIds: ['c1','c2','c3'] },
  { id: 'e2', type: 'ICD',        value: 'M17.11',   normalized: 'Primary osteoarthritis, right knee', context: 'Dx: M17.11',              pageIndex: 0, confidence: 0.98, criterionIds: ['c2','c3'] },
  { id: 'e3', type: 'ICD',        value: 'Z96.651',  normalized: 'Presence of right artificial knee joint', context: 'Hx: Z96.651',       pageIndex: 0, confidence: 0.97, criterionIds: [] },
  { id: 'e4', type: 'ICD',        value: 'M25.361',  normalized: 'Stiffness of right knee, NEC',   context: 'Dx: M25.361',               pageIndex: 1, confidence: 0.95, criterionIds: ['c3'] },
  { id: 'e5', type: 'MEDICATION', value: 'Naproxen', normalized: 'Naproxen 500mg BID',             context: 'NSAIDs × 18 months',         pageIndex: 1, confidence: 0.96, criterionIds: ['c1'] },
  { id: 'e6', type: 'MEDICATION', value: 'Celecoxib',normalized: 'Celecoxib 200mg QD',             context: 'COX-2 inhibitor × 6 months', pageIndex: 1, confidence: 0.94, criterionIds: ['c1'] },
  { id: 'e7', type: 'MEDICATION', value: 'Cortisone',normalized: 'Corticosteroid injection × 3',  context: 'IA injections, quarterly',   pageIndex: 1, confidence: 0.93, criterionIds: ['c1'] },
  { id: 'e8', type: 'LAB_VALUE',  value: 'BMI 28.4', normalized: 'Body mass index 28.4 kg/m²',    context: 'Vitals: Wt 185 lb',          pageIndex: 2, confidence: 0.99, criterionIds: ['c4'] },
  { id: 'e9', type: 'LAB_VALUE',  value: 'HbA1c 5.9%', normalized: 'Glycosylated hemoglobin 5.9%', context: 'Labs 2024-01-15',          pageIndex: 3, confidence: 0.99, criterionIds: ['c4'] },
  { id:'e10', type: 'LAB_VALUE',  value: 'KL Grade IV', normalized: 'Kellgren-Lawrence Grade IV', context: 'X-ray right knee',           pageIndex: 2, confidence: 0.97, criterionIds: ['c2'] },
  { id:'e11', type: 'DATE',       value: '2022-03-14', normalized: 'March 14, 2022',               context: 'PT initiated',               pageIndex: 1, confidence: 0.99, criterionIds: ['c1'] },
  { id:'e12', type: 'DATE',       value: '2024-01-08', normalized: 'January 8, 2024',              context: 'Cardiac clearance issued',   pageIndex: 3, confidence: 0.99, criterionIds: ['c6'] },
]

export const PAGES: DocPage[] = [
  {
    index: 0, label: 'Referral Letter', docType: 'REFERRAL_LETTER',
    content: [
      { type: 'heading',    text: 'PRIOR AUTHORIZATION REQUEST' },
      { type: 'subheading', text: 'Westside Orthopedic Associates · NPI 1497836254' },
      { type: 'divider' },
      { type: 'field-row',  rows: [
        { label: 'Patient',        value: 'James Mitchell',       entityId: undefined },
        { label: 'Date of Birth',  value: '04/12/1958 (Age 66)',  entityId: undefined },
        { label: 'Member ID',      value: 'UHC-4821937',          entityId: undefined },
        { label: 'Insurance Plan', value: 'UnitedHealth PPO Gold',entityId: undefined },
      ]},
      { type: 'field-row',  rows: [
        { label: 'Requesting Provider', value: 'Dr. Sarah Chen, MD (Ortho)', entityId: undefined },
        { label: 'Procedure Requested', value: 'Total Knee Arthroplasty',    entityId: 'e1' },
        { label: 'CPT Code',            value: '27447',                      entityId: 'e1' },
        { label: 'Primary Diagnosis',   value: 'M17.11 — Primary OA, Right Knee', entityId: 'e2' },
        { label: 'Secondary Dx',        value: 'M25.361 — Stiffness, Right Knee', entityId: 'e4' },
      ]},
      { type: 'paragraph', text: 'Mr. Mitchell is a 66-year-old male presenting with advanced primary osteoarthritis of the right knee (M17.11), with KL Grade IV changes confirmed on recent radiographic imaging. He has experienced progressive functional decline over 24+ months despite exhaustive conservative management. This request is submitted for approval of Total Knee Arthroplasty (CPT 27447) as medically necessary.', entityIds: ['e1','e2','e10'] },
    ],
  },
  {
    index: 1, label: 'Clinical Notes', docType: 'CLINICAL_NOTES',
    content: [
      { type: 'heading',    text: 'CLINICAL NOTES — ORTHOPEDIC CONSULTATION' },
      { type: 'subheading', text: 'Date of Service: 2024-02-20 · Provider: Dr. Sarah Chen' },
      { type: 'divider' },
      { type: 'subheading', text: 'Chief Complaint' },
      { type: 'paragraph',  text: 'Patient presents with worsening right knee pain (8/10), severe stiffness, and inability to perform activities of daily living including walking > 1 block and ascending stairs. Pain is constant, worse with weight-bearing.', entityIds: ['e4'] },
      { type: 'subheading', text: 'Conservative Treatment History' },
      { type: 'paragraph',  text: 'Initiated physical therapy March 2022 (24 sessions completed). NSAIDs trialed: Naproxen 500mg BID × 18 months, transitioned to Celecoxib 200mg QD × 6 months due to GI intolerance. Intraarticular corticosteroid injections administered quarterly × 3 (last injection Sept 2023). Patient reports < 15% symptom relief from all conservative measures combined.', entityIds: ['e5','e6','e7','e11'] },
      { type: 'subheading', text: 'Assessment & Plan' },
      { type: 'paragraph',  text: 'Given exhaustive conservative management over 24 months without meaningful improvement, clinical presentation consistent with end-stage OA, and patient\'s severely reduced quality of life, Total Knee Arthroplasty is indicated as the next appropriate intervention. Surgical clearance has been obtained. BMI 28.4 kg/m² is within acceptable range for elective TKA.', entityIds: ['e8','e1'] },
    ],
  },
  {
    index: 2, label: 'Radiology Report', docType: 'IMAGING_REPORT',
    content: [
      { type: 'heading',    text: 'RADIOLOGY REPORT — PLAIN FILM X-RAY' },
      { type: 'subheading', text: 'Study: Right Knee AP/Lateral/Merchant · Date: 2024-01-30' },
      { type: 'divider' },
      { type: 'field-row', rows: [
        { label: 'Patient',    value: 'James Mitchell (DOB: 04/12/1958)',   entityId: undefined },
        { label: 'Study Type', value: 'Plain Film X-Ray, 3 views',          entityId: undefined },
        { label: 'Body Part',  value: 'Right Knee',                          entityId: undefined },
        { label: 'Radiologist',value: 'Dr. Michael Torres, MD, Radiology',  entityId: undefined },
      ]},
      { type: 'subheading', text: 'Findings' },
      { type: 'paragraph',  text: 'RIGHT KNEE: Severe tri-compartmental osteoarthritis. Kellgren-Lawrence Grade IV changes with complete loss of medial joint space, marked varus deformity, large periarticular osteophytes (femoral and tibial), and subchondral sclerosis. Mild lateral compartment narrowing. Patellofemoral compartment with moderate osteophyte formation. No fracture, dislocation, or malignancy identified.', entityIds: ['e2','e10'] },
      { type: 'subheading', text: 'Impression' },
      { type: 'paragraph',  text: 'Kellgren-Lawrence Grade IV osteoarthritis, right knee. Findings consistent with end-stage degenerative joint disease and support surgical intervention.', entityIds: ['e10','e2'] },
      { type: 'field-row', rows: [
        { label: 'KL Grade',      value: 'Grade IV (Severe)',          entityId: 'e10' },
        { label: 'Joint Space',   value: 'Complete medial obliteration',entityId: undefined },
        { label: 'Osteophytes',   value: 'Large, periarticular',        entityId: undefined },
        { label: 'Deformity',     value: 'Varus 8°',                    entityId: undefined },
      ]},
    ],
  },
  {
    index: 3, label: 'Lab Results', docType: 'LAB_RESULTS',
    content: [
      { type: 'heading',    text: 'LABORATORY RESULTS & CARDIAC CLEARANCE' },
      { type: 'subheading', text: 'Collection Date: 2024-01-15 · Lab: Quest Diagnostics' },
      { type: 'divider' },
      { type: 'subheading', text: 'Pre-Surgical Labs' },
      { type: 'table', rows: [
        { label: 'HbA1c',          value: '5.9%   (Ref: <5.7% normal, <6.5% pre-diabetic)',  entityId: 'e9' },
        { label: 'Hemoglobin',     value: '14.2 g/dL  (Ref: 13.5–17.5)',                     entityId: undefined },
        { label: 'Creatinine',     value: '0.98 mg/dL  (Ref: 0.74–1.35)',                    entityId: undefined },
        { label: 'INR',            value: '1.0  (Ref: 0.9–1.1)',                             entityId: undefined },
        { label: 'Platelet Count', value: '224 × 10³/μL  (Ref: 150–400)',                   entityId: undefined },
      ]},
      { type: 'subheading', text: 'Cardiac Clearance' },
      { type: 'paragraph',  text: 'Cardiac evaluation completed January 8, 2024 by Dr. Lisa Park (Cardiology). EKG: Normal sinus rhythm. Echo: EF 60%, no valvular disease. Stress test: Negative for ischemia. Patient cleared for elective surgery — low cardiac risk per ACC/AHA guidelines (RCRI score 1).', entityIds: ['e12'] },
      { type: 'field-row', rows: [
        { label: 'Clearance Date', value: '01/08/2024',          entityId: 'e12' },
        { label: 'Cleared By',     value: 'Dr. Lisa Park, Cardiology', entityId: undefined },
        { label: 'Risk Level',     value: 'LOW (RCRI 1)',          entityId: undefined },
        { label: 'Validity',       value: '90 days from issue',    entityId: undefined },
      ]},
    ],
  },
]

export const CRITERIA: PolicyCriterion[] = [
  {
    id: 'c1',
    policyRef: 'UHC MP.028.A §3.1',
    requirement: 'Conservative treatment attempted for ≥6 months including at least two of: physical therapy, NSAIDs, intra-articular injections, or bracing',
    status: 'MET',
    confidence: 0.97,
    rationale: 'Documentation confirms physical therapy initiated March 2022 (24 sessions), dual NSAID trials (Naproxen 18 months, Celecoxib 6 months), and three quarterly intra-articular corticosteroid injections — all spanning 24 months. This substantially exceeds the 6-month threshold with three qualifying modalities.',
    groundingScore: 0.96,
    hallucinationRisk: 'LOW',
    evidence: [
      { id: 'ev1', text: 'Initiated physical therapy March 2022 (24 sessions completed).', source: 'Clinical Notes, p.2', pageIndex: 1, entityId: 'e11', confidence: 0.98 },
      { id: 'ev2', text: 'Naproxen 500mg BID × 18 months, transitioned to Celecoxib 200mg QD × 6 months', source: 'Clinical Notes, p.2', pageIndex: 1, entityId: 'e5', confidence: 0.97 },
      { id: 'ev3', text: 'Intraarticular corticosteroid injections administered quarterly × 3 (last Sept 2023)', source: 'Clinical Notes, p.2', pageIndex: 1, entityId: 'e7', confidence: 0.95 },
    ],
    reasoningSteps: [
      { step: 1, type: 'retrieve',  text: 'Retrieved UHC policy MP.028.A §3.1 — Conservative Treatment Requirements for TKA' },
      { step: 2, type: 'compare',   text: 'Policy requires ≥6 months + ≥2 modalities. Evidence shows 24-month duration with 3 modalities (PT, NSAIDs × 2, injections)' },
      { step: 3, type: 'evaluate',  text: 'Duration far exceeds minimum. All three modalities documented with dates, dosages, and visit counts' },
      { step: 4, type: 'conclude',  text: 'CRITERION MET with high confidence (0.97)' },
    ],
  },
  {
    id: 'c2',
    policyRef: 'UHC MP.028.A §3.2',
    requirement: 'Radiographic evidence of severe osteoarthritis (Kellgren-Lawrence Grade III or IV) documented within 12 months of request',
    status: 'MET',
    confidence: 0.93,
    rationale: 'Radiology report dated January 30, 2024 (21 days before request) explicitly states Kellgren-Lawrence Grade IV changes with complete loss of medial joint space. This exceeds the minimum Grade III threshold and is within the required 12-month window.',
    groundingScore: 0.95,
    hallucinationRisk: 'LOW',
    evidence: [
      { id: 'ev4', text: 'Kellgren-Lawrence Grade IV changes with complete loss of medial joint space', source: 'Radiology Report, p.3', pageIndex: 2, entityId: 'e10', confidence: 0.97 },
      { id: 'ev5', text: 'Study date: 2024-01-30 — within 12-month window of request (2024-02-20)', source: 'Radiology Report, p.3', pageIndex: 2, entityId: undefined, confidence: 0.99 },
    ],
    reasoningSteps: [
      { step: 1, type: 'retrieve',  text: 'Retrieved radiology report dated 2024-01-30 for right knee plain film' },
      { step: 2, type: 'compare',   text: 'Policy requires KL Grade III or IV within 12 months. Report shows Grade IV, dated 21 days before request date' },
      { step: 3, type: 'evaluate',  text: 'KL Grade IV > required Grade III. 21 days << 12 months. Both conditions met' },
      { step: 4, type: 'conclude',  text: 'CRITERION MET (0.93) — slight reduction from KL Grade interpretation ambiguity' },
    ],
  },
  {
    id: 'c3',
    policyRef: 'UHC MP.028.A §3.3',
    requirement: 'Documented functional impairment limiting activities of daily living (ADLs) with WOMAC or equivalent scale score or physician attestation',
    status: 'MET',
    confidence: 0.89,
    rationale: 'Physician attestation in clinical notes documents inability to walk >1 block, ascend stairs, and constant 8/10 pain with weight-bearing. While a formal WOMAC score is not documented, the physician\'s detailed functional assessment constitutes equivalent documentation per policy language.',
    groundingScore: 0.88,
    hallucinationRisk: 'LOW',
    evidence: [
      { id: 'ev6', text: 'Worsening right knee pain (8/10), severe stiffness, inability to perform ADLs including walking > 1 block and ascending stairs', source: 'Clinical Notes, p.2', pageIndex: 1, entityId: 'e4', confidence: 0.91 },
    ],
    reasoningSteps: [
      { step: 1, type: 'retrieve',  text: 'Searched for WOMAC score or standardized functional assessment — not found' },
      { step: 2, type: 'compare',   text: 'Policy allows "WOMAC or equivalent scale score OR physician attestation." Clinical notes contain detailed ADL limitations by physician.' },
      { step: 3, type: 'evaluate',  text: 'Physician attestation provides equivalent functional documentation: pain 8/10, <1 block ambulation, stair limitation' },
      { step: 4, type: 'conclude',  text: 'CRITERION MET (0.89) — confidence reduced slightly due to absence of formal WOMAC instrument' },
    ],
  },
  {
    id: 'c4',
    policyRef: 'UHC MP.028.A §3.4',
    requirement: 'BMI ≤40 kg/m², or BMI >40 with documented risk-benefit discussion and multidisciplinary team review',
    status: 'MET',
    confidence: 0.99,
    rationale: 'BMI documented as 28.4 kg/m² — well within the acceptable surgical range. No special risk-benefit documentation required.',
    groundingScore: 0.99,
    hallucinationRisk: 'LOW',
    evidence: [
      { id: 'ev7', text: 'BMI 28.4 kg/m² is within acceptable range for elective TKA', source: 'Clinical Notes, p.2', pageIndex: 1, entityId: 'e8', confidence: 0.99 },
    ],
    reasoningSteps: [
      { step: 1, type: 'retrieve',  text: 'Retrieved BMI from clinical notes: 28.4 kg/m²' },
      { step: 2, type: 'compare',   text: 'Policy threshold: BMI ≤40. Documented BMI: 28.4. Delta: -11.6 units below threshold' },
      { step: 3, type: 'conclude',  text: 'CRITERION MET (0.99) — high confidence, clear numerical compliance' },
    ],
  },
  {
    id: 'c5',
    policyRef: 'UHC MP.028.A §3.5',
    requirement: 'Bone mineral density (BMD) assessment or DEXA scan result documented if patient is female >65 or male >70, OR at-risk population per criteria',
    status: 'NOT_APPLICABLE',
    confidence: 0.85,
    rationale: 'Patient is male, age 66. The policy BMD requirement applies to females >65 OR males >70. Patient does not meet either gender/age threshold. This criterion is not applicable to this case.',
    groundingScore: 0.87,
    hallucinationRisk: 'LOW',
    evidence: [
      { id: 'ev8', text: 'Patient: James Mitchell, Male, DOB 04/12/1958 (age 66)', source: 'Referral Letter, p.1', pageIndex: 0, entityId: undefined, confidence: 0.99 },
    ],
    reasoningSteps: [
      { step: 1, type: 'retrieve',  text: 'Checked patient demographics: Male, age 66' },
      { step: 2, type: 'compare',   text: 'Policy requires BMD for: females >65 OR males >70. Patient is male age 66 — does not reach male threshold of 70' },
      { step: 3, type: 'conclude',  text: 'CRITERION NOT APPLICABLE — patient demographic does not trigger BMD requirement' },
    ],
  },
  {
    id: 'c6',
    policyRef: 'UHC MP.028.A §3.6',
    requirement: 'Cardiac clearance from cardiologist or PCP within 90 days of proposed surgery date for patients ≥65 years of age',
    status: 'MET',
    confidence: 0.96,
    rationale: 'Cardiac clearance documented January 8, 2024 by Dr. Lisa Park (Cardiology). Patient is 66 years old (≥65 threshold met). Clearance issued 43 days before request date (within 90-day window). EKG normal, echo EF 60%, stress test negative — low RCRI risk.',
    groundingScore: 0.97,
    hallucinationRisk: 'LOW',
    evidence: [
      { id: 'ev9', text: 'Cardiac evaluation completed January 8, 2024 by Dr. Lisa Park (Cardiology). Patient cleared for elective surgery — low cardiac risk (RCRI score 1)', source: 'Lab Results/Cardiac Clearance, p.4', pageIndex: 3, entityId: 'e12', confidence: 0.98 },
    ],
    reasoningSteps: [
      { step: 1, type: 'retrieve',  text: 'Found cardiac clearance letter in documents, dated 2024-01-08' },
      { step: 2, type: 'compare',   text: 'Patient age 66 ≥65 — trigger applies. Clearance date: 2024-01-08, request date 2024-02-20 → 43 days elapsed, within 90-day window' },
      { step: 3, type: 'evaluate',  text: 'Clearance issued by cardiologist (Dr. Lisa Park). EKG, echo, stress test all documented' },
      { step: 4, type: 'conclude',  text: 'CRITERION MET (0.96)' },
    ],
  },
]

export const AUDIT_LOG: AuditEntry[] = [
  { id: 'a1', type: 'AI_PROCESSED',    actor: 'AI Engine', role: 'system',   note: 'Case processed — APPROVE recommended (92.4%)', ts: new Date(Date.now() - 2 * 3600000) },
  { id: 'a2', type: 'ASSIGNED',        actor: 'Dr. M. Torres', role: 'supervisor', note: 'Assigned to Dr. J. Park for review', ts: new Date(Date.now() - 90 * 60000) },
  { id: 'a3', type: 'OPENED',          actor: 'Dr. J. Park', role: 'reviewer', note: 'Case opened for review', ts: new Date(Date.now() - 30 * 60000) },
  { id: 'a4', type: 'DOCUMENT_VIEWED', actor: 'Dr. J. Park', role: 'reviewer', note: 'Viewed: Clinical Notes (p.2)', ts: new Date(Date.now() - 25 * 60000) },
  { id: 'a5', type: 'DOCUMENT_VIEWED', actor: 'Dr. J. Park', role: 'reviewer', note: 'Viewed: Radiology Report (p.3)', ts: new Date(Date.now() - 18 * 60000) },
]

// ─── Hook ─────────────────────────────────────────────────────────────────────

export interface ReviewState {
  caseData:           ReviewCase
  pages:              DocPage[]
  entities:           DocEntity[]
  criteria:           PolicyCriterion[]
  auditLog:           AuditEntry[]
  // UI state
  activePage:         number
  zoom:               number
  highlightedEntityIds: string[]
  activeCriterionId:  string | null
  expandedCriterionIds: Set<string>
  // Actions
  setPage:            (n: number) => void
  setZoom:            (z: number) => void
  highlightEntity:    (ids: string[]) => void
  clearHighlight:     () => void
  setActiveCriterion: (id: string | null) => void
  toggleCriterion:    (id: string) => void
}

export function useCaseReviewData(): ReviewState {
  const [activePage,  setPage]  = useState(0)
  const [zoom,        setZoom]  = useState(1)
  const [highlightedEntityIds, setHighlight] = useState<string[]>([])
  const [activeCriterionId, setActiveCriterion] = useState<string | null>(null)
  const [expandedCriterionIds, setExpanded] = useState<Set<string>>(new Set(['c1']))

  const highlightEntity = useCallback((ids: string[]) => setHighlight(ids), [])
  const clearHighlight  = useCallback(() => setHighlight([]), [])

  const toggleCriterion = useCallback((id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  return {
    caseData: CASE, pages: PAGES, entities: ENTITIES,
    criteria: CRITERIA, auditLog: AUDIT_LOG,
    activePage, zoom, highlightedEntityIds, activeCriterionId, expandedCriterionIds,
    setPage, setZoom, highlightEntity, clearHighlight,
    setActiveCriterion, toggleCriterion,
  }
}
