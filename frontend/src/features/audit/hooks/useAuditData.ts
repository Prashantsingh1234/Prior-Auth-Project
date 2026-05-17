import { useState, useCallback, useMemo } from 'react'

// ─── Extended event types ─────────────────────────────────────────────────────

export type AuditEventType =
  | 'SUBMITTED' | 'ASSIGNED' | 'REVIEWED' | 'APPROVED' | 'DENIED'
  | 'ESCALATED' | 'PENDED' | 'STATUS_CHANGED'
  | 'AI_PROCESSED' | 'AI_OUTPUT' | 'AI_OVERRIDE' | 'AI_FALLBACK'
  | 'PROMPT_TRACE' | 'RETRIEVAL_TRACE'
  | 'CLARIFICATION_REQUESTED' | 'CLARIFICATION_ANSWERED' | 'CLARIFICATION_ESCALATED'
  | 'DOCUMENT_UPLOADED' | 'DOCUMENT_VIEWED' | 'DOCUMENT_OCR'
  | 'POLICY_MATCHED' | 'POLICY_UPDATED'
  | 'COMPLIANCE_EXPORT' | 'ACCESS_GRANTED' | 'ACCESS_REVOKED'
  | 'SLA_BREACHED' | 'SLA_WARNING'

export type EventCategory = 'decision' | 'ai' | 'clarification' | 'document' | 'policy' | 'system' | 'compliance'
export type ActorRole     = 'reviewer' | 'admin' | 'ai_system' | 'provider' | 'system'

export interface PromptTrace {
  model:        string
  inputTokens:  number
  outputTokens: number
  latencyMs:    number
  temperature:  number
  systemPrompt: string
  userPrompt:   string
  completion:   string
  groundingScore: number
  hallucinationFlag: boolean
  cost:         number
}

export interface RetrievalTrace {
  query:      string
  totalChunks: number
  threshold:  number
  chunks: Array<{
    id:         string
    policyName: string
    sectionRef: string
    text:       string
    score:      number
    used:       boolean
  }>
}

export interface AIDecisionOutput {
  recommendation: 'APPROVE' | 'DENY' | 'PEND' | 'ESCALATE'
  confidence:     number
  rationale:      string
  criteriaResults: Array<{ criterion: string; status: 'MET' | 'NOT_MET' | 'INSUFFICIENT'; confidence: number }>
  modelChain:     string[]
}

export interface OverrideRecord {
  aiDecision:       string
  reviewerDecision: string
  reason:           string
  flaggedForReview: boolean
}

export interface AuditEntry {
  id:          string
  caseId:      string
  caseRef:     string
  eventType:   AuditEventType
  category:    EventCategory
  description: string
  actorId:     string
  actorName:   string
  actorRole:   ActorRole
  occurredAt:  string
  ipAddress:   string
  userAgent:   string
  immutable:   boolean
  integrityHash: string
  metadata?:   Record<string, string | number | boolean>
  promptTrace?:    PromptTrace
  retrievalTrace?: RetrievalTrace
  aiOutput?:       AIDecisionOutput
  override?:       OverrideRecord
}

export interface AuditFilters {
  search:      string
  dateFrom:    string
  dateTo:      string
  categories:  EventCategory[]
  eventTypes:  AuditEventType[]
  actorRoles:  ActorRole[]
  caseRef:     string
  outcomes:    string[]
}

// ─── Seeded PRNG ──────────────────────────────────────────────────────────────

function s(n: number) { return Math.abs(Math.sin(n * 9301 + 49297) % 1) }

function makeHash(seed: number) {
  const chars = '0123456789abcdef'
  return Array.from({ length: 64 }, (_, i) => chars[Math.floor(s(seed + i) * 16)]).join('')
}

// ─── Actors ───────────────────────────────────────────────────────────────────

const ACTORS = [
  { id: 'r1', name: 'Dr. A. Torres',   role: 'reviewer' as ActorRole, ip: '10.0.1.42' },
  { id: 'r2', name: 'Dr. J. Park',     role: 'reviewer' as ActorRole, ip: '10.0.1.67' },
  { id: 'r3', name: 'Dr. S. Kim',      role: 'reviewer' as ActorRole, ip: '10.0.1.91' },
  { id: 'a1', name: 'Admin Console',   role: 'admin' as ActorRole,    ip: '10.0.0.5'  },
  { id: 'ai', name: 'AI System',       role: 'ai_system' as ActorRole, ip: '10.0.2.1' },
  { id: 'p1', name: 'Dr. M. Chen',     role: 'provider' as ActorRole,  ip: '172.16.4.22' },
  { id: 's0', name: 'PA Platform',     role: 'system' as ActorRole,    ip: '10.0.2.0' },
]

const CASE_REFS = ['PA-2024-001', 'PA-2024-002', 'PA-2024-003', 'PA-2024-004', 'PA-2024-005']
const CASE_IDS  = ['case-001', 'case-002', 'case-003', 'case-004', 'case-005']

const SYSTEM_PROMPT_SNIPPET = `You are a clinical prior authorization AI assistant. Your role is to evaluate PA requests against established medical policy criteria with clinical accuracy, evidence-based reasoning, and strict policy adherence. Always cite specific policy sections. Return structured JSON.`

const USER_PROMPTS = [
  `Evaluate PA request for Total Knee Arthroplasty (CPT 27447). Patient: 68y/o female. Dx: M17.11 (primary OA right knee, KL Grade IV). Conservative tx: 8 months PT (18 sessions), NSAIDs x6mo, viscosupplementation x3. WOMAC score: 72. BMI: 32. Pre-op cardiac clearance provided. Evaluate against policy MP-2024-TKA-001 v3.2.`,
  `Review PA for outpatient PT (CPT 97110, 97530). Patient: 54y/o male post-TKA day 14. Requesting 24 additional sessions. Functional assessment: KSS 48/100. Prior authorization granted for initial 12 sessions — extension request. Policy MP-2024-PT-002 v2.1.`,
  `Assess PA for MRI right knee (CPT 73721). Patient: 42y/o female. Dx: M25.361, M17.11. Complaint: worsening knee pain 6/10 unresponsive to conservative management x3 months. X-ray shows KL Grade II. Provider requesting MRI to rule out meniscal pathology. Policy MP-2024-IMG-003 v1.4.`,
]

const AI_COMPLETIONS = [
  `{"recommendation":"APPROVE","confidence":0.94,"rationale":"All medical necessity criteria are met. KL Grade IV confirmed by radiology. Conservative therapy failure documented with 18 PT sessions (>12 required) and 6 months pharmacological management. BMI 32 within threshold. WOMAC 72 exceeds cutoff of 50. Pre-operative cardiac clearance provided per §4.2 requirement.","criteriaResults":[{"criterion":"Radiographic confirmation KL Grade III-IV","status":"MET","confidence":0.98},{"criterion":"Conservative therapy ≥6 months","status":"MET","confidence":0.96},{"criterion":"WOMAC ≥50","status":"MET","confidence":1.0},{"criterion":"BMI ≤40","status":"MET","confidence":1.0},{"criterion":"Cardiac clearance","status":"MET","confidence":0.95}]}`,
  `{"recommendation":"PEND","confidence":0.71,"rationale":"Initial authorization covered 12 sessions. Extension request requires updated functional assessment and documented progress notes. KSS 48 suggests insufficient functional improvement trajectory. Requesting 90-day progress report and updated KSS assessment prior to approving additional sessions.","criteriaResults":[{"criterion":"Post-operative protocol compliance","status":"MET","confidence":0.88},{"criterion":"Functional improvement documented","status":"INSUFFICIENT","confidence":0.64},{"criterion":"Session count within policy limit","status":"NOT_MET","confidence":0.89}]}`,
  `{"recommendation":"DENY","confidence":0.82,"rationale":"MRI not medically necessary at this time per policy MP-2024-IMG-003. KL Grade II OA does not meet radiographic threshold for MRI authorization without prior failed conservative management of ≥6 months. Patient has only 3 months conservative treatment. Recommend continued conservative management and reassess at 6 months.","criteriaResults":[{"criterion":"Conservative management ≥6 months","status":"NOT_MET","confidence":0.95},{"criterion":"Radiographic evidence of advanced disease","status":"NOT_MET","confidence":0.78}]}`,
]

const RETRIEVAL_CHUNKS = [
  { id: 'c1', policyName: 'Total Knee Arthroplasty', sectionRef: '§3.1', text: 'Member must have a diagnosis of severe osteoarthritis (Grade III or IV on the Kellgren-Lawrence scale) confirmed by radiographic evidence within the past 12 months.', score: 0.97 },
  { id: 'c2', policyName: 'Total Knee Arthroplasty', sectionRef: '§3.2', text: 'Conservative therapy failure: member must have completed at least 6 months of documented conservative management including physical therapy (minimum 12 sessions).', score: 0.94 },
  { id: 'c3', policyName: 'Total Knee Arthroplasty', sectionRef: '§3.3', text: 'BMI requirement: member\'s BMI must be ≤40 at time of authorization request.', score: 0.89 },
  { id: 'c4', policyName: 'Total Knee Arthroplasty', sectionRef: '§3.4', text: 'Functional impairment: member must demonstrate significant functional limitation as evidenced by a WOMAC score ≥50.', score: 0.91 },
  { id: 'c5', policyName: 'Total Knee Arthroplasty', sectionRef: '§4.2', text: 'Pre-operative cardiac clearance required for all members with known cardiovascular disease, diabetes, or BMI >35.', score: 0.86 },
  { id: 'c6', policyName: 'Total Knee Arthroplasty', sectionRef: '§5.1', text: 'Inflammatory arthropathy as primary indication is an exclusion — refer to separate policy MP-2024-INFLAM.', score: 0.71 },
  { id: 'c7', policyName: 'Physical Therapy', sectionRef: '§2.1', text: 'Outpatient PT following TKA is covered for up to 60 visits within 6 months post-operatively.', score: 0.83 },
  { id: 'c8', policyName: 'MRI — Extremity', sectionRef: '§3.1', text: 'MRI of extremity joints requires documented failure of conservative management for at least 6 months.', score: 0.88 },
]

// ─── Mock entry factory ───────────────────────────────────────────────────────

function makeEntry(
  seed: number,
  caseIdx: number,
  minutesAgo: number,
  eventType: AuditEventType,
  category: EventCategory,
  actorIdx: number,
  description: string,
  extras: Partial<AuditEntry> = {},
): AuditEntry {
  const actor   = ACTORS[actorIdx]
  const caseRef = CASE_REFS[caseIdx]
  const caseId  = CASE_IDS[caseIdx]
  const at      = new Date(Date.now() - minutesAgo * 60000).toISOString()

  return {
    id:            `audit-${seed.toString().padStart(4, '0')}`,
    caseId,
    caseRef,
    eventType,
    category,
    description,
    actorId:       actor.id,
    actorName:     actor.name,
    actorRole:     actor.role,
    occurredAt:    at,
    ipAddress:     actor.ip,
    userAgent:     'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
    immutable:     true,
    integrityHash: makeHash(seed),
    ...extras,
  }
}

// ─── Build full audit log ─────────────────────────────────────────────────────

function buildAuditLog(): AuditEntry[] {
  const entries: AuditEntry[] = []
  let seed = 1

  // ── Case PA-2024-001 (TKA, APPROVED) ───────────────────────────────────────
  entries.push(makeEntry(seed++, 0, 2 * 24 * 60 + 480, 'SUBMITTED', 'document', 4, 'PA request submitted for CPT 27447 (Total Knee Arthroplasty) — patient DOB 1956-03-14, Dx M17.11', { metadata: { cptCode: '27447', dxCode: 'M17.11', submissionMethod: 'portal' } }))
  entries.push(makeEntry(seed++, 0, 2 * 24 * 60 + 470, 'DOCUMENT_UPLOADED', 'document', 6, 'Supporting documents uploaded: radiology report (3 pages), PT discharge summary (8 pages), physician notes (12 pages)', { metadata: { documentCount: 3, totalPages: 23, ocrQueued: true } }))
  entries.push(makeEntry(seed++, 0, 2 * 24 * 60 + 465, 'DOCUMENT_OCR', 'ai', 4, 'OCR extraction completed — 23 pages processed, 2,847 characters extracted, 99.2% confidence', { metadata: { pages: 23, chars: 2847, confidence: 99.2, engineVersion: 'tesseract-5.3' } }))
  entries.push(makeEntry(seed++, 0, 2 * 24 * 60 + 460, 'RETRIEVAL_TRACE', 'ai', 4, 'Semantic retrieval completed — 24 chunks retrieved, 11 above threshold (0.72), 5 policy sections matched', {
    retrievalTrace: {
      query: 'TKA medical necessity criteria osteoarthritis KL grade BMI WOMAC conservative therapy',
      totalChunks: 24, threshold: 0.72,
      chunks: RETRIEVAL_CHUNKS.slice(0, 6).map((c) => ({ ...c, used: c.score >= 0.72 })),
    },
  }))
  entries.push(makeEntry(seed++, 0, 2 * 24 * 60 + 455, 'PROMPT_TRACE', 'ai', 4, 'LLM evaluation initiated — claude-sonnet-4-6, 2,840 input tokens, 680 output tokens, 1.4s latency', {
    promptTrace: {
      model: 'claude-sonnet-4-6', inputTokens: 2840, outputTokens: 680, latencyMs: 1420,
      temperature: 0.05, groundingScore: 0.94, hallucinationFlag: false, cost: 0.0186,
      systemPrompt: SYSTEM_PROMPT_SNIPPET,
      userPrompt: USER_PROMPTS[0],
      completion: AI_COMPLETIONS[0],
    },
  }))
  entries.push(makeEntry(seed++, 0, 2 * 24 * 60 + 450, 'AI_PROCESSED', 'ai', 4, 'AI evaluation complete — recommendation: APPROVE (94% confidence), all 5 criteria MET, grounding score 0.94', {
    aiOutput: {
      recommendation: 'APPROVE', confidence: 0.94,
      rationale: 'All medical necessity criteria are met. KL Grade IV confirmed, conservative therapy failure documented, BMI within threshold, WOMAC exceeds cutoff, cardiac clearance provided.',
      criteriaResults: [
        { criterion: 'Radiographic confirmation KL Grade III-IV', status: 'MET', confidence: 0.98 },
        { criterion: 'Conservative therapy ≥6 months', status: 'MET', confidence: 0.96 },
        { criterion: 'WOMAC ≥50', status: 'MET', confidence: 1.0 },
        { criterion: 'BMI ≤40', status: 'MET', confidence: 1.0 },
        { criterion: 'Cardiac clearance', status: 'MET', confidence: 0.95 },
      ],
      modelChain: ['text-embedding-3-large', 'claude-haiku-4-5', 'claude-sonnet-4-6'],
    },
  }))
  entries.push(makeEntry(seed++, 0, 2 * 24 * 60 + 60, 'ASSIGNED', 'decision', 3, 'Case assigned to Dr. A. Torres for clinical review', { metadata: { assignedBy: 'auto-routing', priority: 'standard', slaHours: 24 } }))
  entries.push(makeEntry(seed++, 0, 2 * 24 * 60 + 30, 'DOCUMENT_VIEWED', 'document', 0, 'Radiology report viewed — Dr. A. Torres (duration: 4m 22s)', { metadata: { documentType: 'radiology', viewDuration: 262, pageCount: 3 } }))
  entries.push(makeEntry(seed++, 0, 2 * 24 * 60 + 25, 'DOCUMENT_VIEWED', 'document', 0, 'PT discharge summary viewed — Dr. A. Torres (duration: 6m 48s)', { metadata: { documentType: 'PT_notes', viewDuration: 408, pageCount: 8 } }))
  entries.push(makeEntry(seed++, 0, 2 * 24 * 60 + 15, 'REVIEWED', 'decision', 0, 'Clinical review completed — Dr. A. Torres reviewed AI recommendation and supporting evidence', { metadata: { reviewDuration: 900, aiAgreement: true } }))
  entries.push(makeEntry(seed++, 0, 2 * 24 * 60 + 10, 'APPROVED', 'decision', 0, 'Authorization APPROVED — PA-2024-001 — Dr. A. Torres (concurs with AI recommendation)', { metadata: { outcome: 'APPROVED', rationale: 'Clinical criteria met. AI recommendation concurred. Authorized for CPT 27447.', aiAgreement: true } }))

  // ── Case PA-2024-002 (PT extension, PEND + OVERRIDE) ────────────────────────
  entries.push(makeEntry(seed++, 1, 2 * 24 * 60 - 60, 'SUBMITTED', 'document', 6, 'PA extension request submitted — CPT 97110 (Physical Therapy, 24 additional sessions)', { metadata: { cptCode: '97110', requestType: 'extension' } }))
  entries.push(makeEntry(seed++, 1, 2 * 24 * 60 - 65, 'RETRIEVAL_TRACE', 'ai', 4, 'Semantic retrieval — 18 chunks retrieved, 8 above threshold, 3 PT policy sections matched', {
    retrievalTrace: {
      query: 'physical therapy extension post-surgical rehabilitation functional improvement KSS',
      totalChunks: 18, threshold: 0.72,
      chunks: [RETRIEVAL_CHUNKS[6], ...RETRIEVAL_CHUNKS.slice(0, 3)].map((c) => ({ ...c, used: c.score >= 0.72 })),
    },
  }))
  entries.push(makeEntry(seed++, 1, 2 * 24 * 60 - 70, 'PROMPT_TRACE', 'ai', 4, 'LLM evaluation — claude-haiku-4-5, 1,240 input tokens, 420 output tokens, 380ms latency', {
    promptTrace: {
      model: 'claude-haiku-4-5', inputTokens: 1240, outputTokens: 420, latencyMs: 380,
      temperature: 0.05, groundingScore: 0.81, hallucinationFlag: false, cost: 0.0004,
      systemPrompt: SYSTEM_PROMPT_SNIPPET,
      userPrompt: USER_PROMPTS[1],
      completion: AI_COMPLETIONS[1],
    },
  }))
  entries.push(makeEntry(seed++, 1, 2 * 24 * 60 - 75, 'AI_PROCESSED', 'ai', 4, 'AI evaluation — recommendation: PEND (71% confidence), insufficient functional improvement data', {
    aiOutput: {
      recommendation: 'PEND', confidence: 0.71,
      rationale: 'Extension request requires updated functional assessment and documented progress notes.',
      criteriaResults: [
        { criterion: 'Post-operative protocol compliance', status: 'MET', confidence: 0.88 },
        { criterion: 'Functional improvement documented', status: 'INSUFFICIENT', confidence: 0.64 },
        { criterion: 'Session count within policy limit', status: 'NOT_MET', confidence: 0.89 },
      ],
      modelChain: ['text-embedding-3-large', 'claude-haiku-4-5'],
    },
  }))
  entries.push(makeEntry(seed++, 1, 24 * 60 + 90, 'ASSIGNED', 'decision', 3, 'Case assigned to Dr. J. Park for clinical review', { metadata: { assignedBy: 'workload-balancer', priority: 'routine' } }))
  entries.push(makeEntry(seed++, 1, 24 * 60 + 60, 'CLARIFICATION_REQUESTED', 'clarification', 1, 'Clarification requested — provider to submit updated KSS functional assessment and 90-day progress notes', { metadata: { clarificationType: 'documentation', daysAllowed: 7, attemptNumber: 1 } }))
  entries.push(makeEntry(seed++, 1, 24 * 60 - 120, 'CLARIFICATION_ANSWERED', 'clarification', 5, 'Provider submitted updated KSS assessment (score: 62/100) and 3-month progress notes', { metadata: { kssScore: 62, documentsSubmitted: 2, daysToRespond: 1 } }))
  entries.push(makeEntry(seed++, 1, 24 * 60 - 180, 'AI_OVERRIDE', 'ai', 1, 'Reviewer override recorded — Dr. J. Park overrode AI PEND → APPROVE citing updated KSS improvement', {
    override: { aiDecision: 'PEND', reviewerDecision: 'APPROVE', reason: 'Updated KSS (62) demonstrates meaningful functional improvement. Provider compliant with documentation request. Clinically appropriate to approve continuation.', flaggedForReview: false },
  }))
  entries.push(makeEntry(seed++, 1, 24 * 60 - 190, 'APPROVED', 'decision', 1, 'Authorization APPROVED (override) — PA-2024-002 — Dr. J. Park (overrode AI PEND, 24 sessions approved)', { metadata: { outcome: 'APPROVED', aiAgreement: false, overrideReason: 'Clinical judgement, updated documentation' } }))

  // ── Case PA-2024-003 (MRI, DENIED, AI concurred) ───────────────────────────
  entries.push(makeEntry(seed++, 2, 24 * 60 - 30, 'SUBMITTED', 'document', 6, 'PA request submitted — CPT 73721 (MRI right knee extremity), Dx M25.361, M17.11', { metadata: { cptCode: '73721', dxCode: 'M25.361' } }))
  entries.push(makeEntry(seed++, 2, 24 * 60 - 35, 'DOCUMENT_OCR', 'ai', 4, 'OCR extraction — 7 pages processed, 1,240 chars extracted, 98.6% confidence', { metadata: { pages: 7, chars: 1240, confidence: 98.6 } }))
  entries.push(makeEntry(seed++, 2, 24 * 60 - 40, 'RETRIEVAL_TRACE', 'ai', 4, 'Retrieval — 12 chunks retrieved, 6 above threshold', {
    retrievalTrace: {
      query: 'MRI knee extremity medical necessity conservative management duration requirements',
      totalChunks: 12, threshold: 0.72,
      chunks: [RETRIEVAL_CHUNKS[7], RETRIEVAL_CHUNKS[1], RETRIEVAL_CHUNKS[0]].map((c) => ({ ...c, used: c.score >= 0.72 })),
    },
  }))
  entries.push(makeEntry(seed++, 2, 24 * 60 - 45, 'PROMPT_TRACE', 'ai', 4, 'LLM evaluation — claude-sonnet-4-6, 1,680 input tokens, 520 output tokens, 1.1s latency', {
    promptTrace: {
      model: 'claude-sonnet-4-6', inputTokens: 1680, outputTokens: 520, latencyMs: 1120,
      temperature: 0.05, groundingScore: 0.88, hallucinationFlag: false, cost: 0.0133,
      systemPrompt: SYSTEM_PROMPT_SNIPPET,
      userPrompt: USER_PROMPTS[2],
      completion: AI_COMPLETIONS[2],
    },
  }))
  entries.push(makeEntry(seed++, 2, 24 * 60 - 50, 'AI_PROCESSED', 'ai', 4, 'AI evaluation — recommendation: DENY (82% confidence), conservative management threshold not met (3 of 6 months)', {
    aiOutput: {
      recommendation: 'DENY', confidence: 0.82,
      rationale: 'MRI not medically necessary. Conservative management duration (3 months) does not meet 6-month policy requirement. KL Grade II does not meet advanced disease threshold.',
      criteriaResults: [
        { criterion: 'Conservative management ≥6 months', status: 'NOT_MET', confidence: 0.95 },
        { criterion: 'Radiographic evidence of advanced disease', status: 'NOT_MET', confidence: 0.78 },
      ],
      modelChain: ['text-embedding-3-large', 'claude-sonnet-4-6'],
    },
  }))
  entries.push(makeEntry(seed++, 2, 360, 'ASSIGNED', 'decision', 3, 'Case assigned to Dr. S. Kim', { metadata: { assignedBy: 'auto-routing', priority: 'routine' } }))
  entries.push(makeEntry(seed++, 2, 300, 'DENIED', 'decision', 2, 'Authorization DENIED — PA-2024-003 — Dr. S. Kim (concurs with AI recommendation per policy §3.1)', { metadata: { outcome: 'DENIED', aiAgreement: true, policyRef: 'MP-2024-IMG-003 §3.1' } }))

  // ── Case PA-2024-004 (SLA breach + escalation) ─────────────────────────────
  entries.push(makeEntry(seed++, 3, 4 * 24 * 60, 'SUBMITTED', 'document', 6, 'PA request submitted — viscosupplementation (CPT 20610)', { metadata: { cptCode: '20610', priority: 'urgent' } }))
  entries.push(makeEntry(seed++, 3, 4 * 24 * 60 - 5, 'AI_PROCESSED', 'ai', 4, 'AI evaluation — recommendation: PEND (68% confidence), additional documentation required', { metadata: { confidence: 0.68, recommendation: 'PEND' } }))
  entries.push(makeEntry(seed++, 3, 2 * 24 * 60 - 10, 'SLA_WARNING', 'system', 6, 'SLA warning triggered — case approaching 48-hour review deadline (4 hours remaining)', { metadata: { slaDeadlineHours: 4, notificationsSent: 2 } }))
  entries.push(makeEntry(seed++, 3, 2 * 24 * 60 - 120, 'SLA_BREACHED', 'system', 6, 'SLA BREACH — case exceeded 72-hour review window without decision', { metadata: { breachDurationHours: 72, escalationTriggered: true } }))
  entries.push(makeEntry(seed++, 3, 2 * 24 * 60 - 125, 'ESCALATED', 'decision', 6, 'Case auto-escalated to medical director due to SLA breach — PA-2024-004', { metadata: { escalationLevel: 'medical_director', trigger: 'sla_breach' } }))
  entries.push(makeEntry(seed++, 3, 90, 'CLARIFICATION_ESCALATED', 'clarification', 0, 'Clarification escalated — provider non-responsive after 2 attempts over 96 hours', { metadata: { attempts: 2, hoursWaited: 96, escalationLevel: 'senior_reviewer' } }))
  entries.push(makeEntry(seed++, 3, 60, 'PENDED', 'decision', 0, 'Case pended — awaiting provider supplemental documentation (deadline: 14 days)', { metadata: { outcome: 'PENDED', documentationDeadlineDays: 14 } }))

  // ── Case PA-2024-005 (AI fallback + policy update) ────────────────────────
  entries.push(makeEntry(seed++, 4, 3 * 24 * 60, 'SUBMITTED', 'document', 6, 'PA request submitted — arthroscopic procedure (CPT 29881)', { metadata: { cptCode: '29881' } }))
  entries.push(makeEntry(seed++, 4, 3 * 24 * 60 - 5, 'AI_FALLBACK', 'ai', 4, 'AI model fallback triggered — primary model timeout (>5s), fell back to claude-haiku-4-5', { metadata: { primaryModel: 'claude-sonnet-4-6', fallbackModel: 'claude-haiku-4-5', reason: 'timeout', latencyMs: 5240 } }))
  entries.push(makeEntry(seed++, 4, 3 * 24 * 60 - 10, 'AI_PROCESSED', 'ai', 4, 'AI evaluation (fallback model) — recommendation: APPROVE (88% confidence)', { metadata: { model: 'claude-haiku-4-5', confidence: 0.88, fallback: true } }))
  entries.push(makeEntry(seed++, 4, 2 * 24 * 60, 'POLICY_UPDATED', 'policy', 3, 'Policy MP-2024-ARTH-005 updated to v2.0 — affected case re-evaluated against new criteria', { metadata: { policyId: 'POL-005', oldVersion: '1.9', newVersion: '2.0', reEvalRequired: true } }))
  entries.push(makeEntry(seed++, 4, 2 * 24 * 60 - 5, 'POLICY_MATCHED', 'policy', 4, 'Re-evaluation completed — case re-scored against MP-2024-ARTH-005 v2.0, recommendation unchanged (APPROVE)', { metadata: { policyVersion: '2.0', recommendationChanged: false } }))
  entries.push(makeEntry(seed++, 4, 24 * 60 + 30, 'APPROVED', 'decision', 2, 'Authorization APPROVED — PA-2024-005 — Dr. S. Kim', { metadata: { outcome: 'APPROVED', aiAgreement: true } }))

  // ── System / compliance events ─────────────────────────────────────────────
  entries.push(makeEntry(seed++, 0, 30, 'COMPLIANCE_EXPORT', 'compliance', 3, 'Compliance export generated — Q4 2024 audit report (all cases, CSV + PDF)', { metadata: { format: 'CSV+PDF', recordCount: 284, exportedBy: 'Dr. A. Torres', period: 'Q4-2024' } }))
  entries.push(makeEntry(seed++, 1, 20, 'ACCESS_GRANTED', 'compliance', 3, 'Elevated access granted — Dr. J. Park granted temporary medical director permissions (24h)', { metadata: { grantedBy: 'Admin Console', duration: '24h', reason: 'medical_director_coverage' } }))
  entries.push(makeEntry(seed++, 0, 10, 'ACCESS_REVOKED', 'compliance', 3, 'Elevated access revoked — Dr. J. Park temporary permissions expired', { metadata: { revokedBy: 'system_auto', reason: 'duration_expired' } }))

  return entries.sort((a, b) => new Date(b.occurredAt).getTime() - new Date(a.occurredAt).getTime())
}

const INITIAL_ENTRIES = buildAuditLog()

// ─── Hook ─────────────────────────────────────────────────────────────────────

const DEFAULT_FILTERS: AuditFilters = {
  search: '', dateFrom: '', dateTo: '',
  categories: [], eventTypes: [], actorRoles: [], caseRef: '', outcomes: [],
}

export function useAuditData() {
  const [entries]                   = useState<AuditEntry[]>(INITIAL_ENTRIES)
  const [filters, setFilters]       = useState<AuditFilters>(DEFAULT_FILTERS)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [exportOpen, setExportOpen] = useState(false)

  const filtered = useMemo(() => {
    return entries.filter((e) => {
      if (filters.search) {
        const q = filters.search.toLowerCase()
        if (!e.description.toLowerCase().includes(q) &&
            !e.caseRef.toLowerCase().includes(q) &&
            !e.actorName.toLowerCase().includes(q)) return false
      }
      if (filters.caseRef && e.caseRef !== filters.caseRef) return false
      if (filters.categories.length > 0 && !filters.categories.includes(e.category)) return false
      if (filters.eventTypes.length > 0 && !filters.eventTypes.includes(e.eventType)) return false
      if (filters.actorRoles.length > 0 && !filters.actorRoles.includes(e.actorRole)) return false
      if (filters.dateFrom && new Date(e.occurredAt) < new Date(filters.dateFrom)) return false
      if (filters.dateTo   && new Date(e.occurredAt) > new Date(filters.dateTo + 'T23:59:59Z')) return false
      return true
    })
  }, [entries, filters])

  const selectedEntry = useMemo(() => entries.find((e) => e.id === selectedId) ?? null, [entries, selectedId])

  const stats = useMemo(() => ({
    total:       entries.length,
    approvals:   entries.filter((e) => e.eventType === 'APPROVED').length,
    denials:     entries.filter((e) => e.eventType === 'DENIED').length,
    aiEvents:    entries.filter((e) => e.category === 'ai').length,
    overrides:   entries.filter((e) => e.eventType === 'AI_OVERRIDE').length,
    breaches:    entries.filter((e) => e.eventType === 'SLA_BREACHED').length,
    compliance:  entries.filter((e) => e.category === 'compliance').length,
  }), [entries])

  const patchFilter = useCallback(<K extends keyof AuditFilters>(key: K, val: AuditFilters[K]) => {
    setFilters((f) => ({ ...f, [key]: val }))
  }, [])

  const toggleCategory = useCallback((cat: EventCategory) => {
    setFilters((f) => ({
      ...f,
      categories: f.categories.includes(cat) ? f.categories.filter((c) => c !== cat) : [...f.categories, cat],
    }))
  }, [])

  const toggleEventType = useCallback((et: AuditEventType) => {
    setFilters((f) => ({
      ...f,
      eventTypes: f.eventTypes.includes(et) ? f.eventTypes.filter((t) => t !== et) : [...f.eventTypes, et],
    }))
  }, [])

  const toggleRole = useCallback((role: ActorRole) => {
    setFilters((f) => ({
      ...f,
      actorRoles: f.actorRoles.includes(role) ? f.actorRoles.filter((r) => r !== role) : [...f.actorRoles, role],
    }))
  }, [])

  const clearFilters = useCallback(() => setFilters(DEFAULT_FILTERS), [])

  const activeFilterCount = useMemo(() =>
    (filters.search ? 1 : 0) + (filters.caseRef ? 1 : 0) + (filters.dateFrom ? 1 : 0) +
    filters.categories.length + filters.eventTypes.length + filters.actorRoles.length,
    [filters],
  )

  const CASE_REFS_LIST = CASE_REFS

  return {
    entries, filtered, selectedEntry, setSelectedId,
    filters, patchFilter, toggleCategory, toggleEventType, toggleRole, clearFilters,
    activeFilterCount, stats, exportOpen, setExportOpen,
    CASE_REFS_LIST,
  }
}
