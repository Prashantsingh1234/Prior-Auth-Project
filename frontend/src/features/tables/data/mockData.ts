// ─── Seeded PRNG ─────────────────────────────────────────────────────────────

function rng(seed: number) {
  return Math.abs(Math.sin(seed * 9301 + 49297) % 1)
}
function pick<T>(arr: T[], seed: number): T {
  return arr[Math.floor(rng(seed) * arr.length)]
}
function fmtDate(daysAgo: number, base = new Date('2024-11-01')): string {
  const d = new Date(base.getTime() - daysAgo * 86_400_000)
  return d.toISOString()
}

// ─── Cases ────────────────────────────────────────────────────────────────────

export type CaseRow = {
  id: string; caseNumber: string; status: string; priority: string
  patientName: string; patientId: string; dob: string
  procedureCode: string; procedureDesc: string
  provider: string; specialty: string; npi: string
  aiRecommendation: string; aiConfidence: number
  diagnosisCodes: string; submittedAt: string; updatedAt: string
  reviewer?: string; slaHours: number; documentsCount: number
  insurancePlan: string
}

const STATUSES    = ['SUBMITTED','UNDER_REVIEW','PENDING_INFO','APPROVED','DENIED','ESCALATED','WITHDRAWN']
const PRIORITIES  = ['ROUTINE','URGENT','EMERGENT']
const AI_RECS     = ['APPROVE','DENY','REQUEST_INFO','ESCALATE']
const SPECIALTIES = ['Orthopedics','Cardiology','Neurology','Oncology','Physical Therapy','Radiology','Urology','Gastroenterology']
const PROCEDURES  = [
  ['27447','Total Knee Arthroplasty'],['27130','Total Hip Arthroplasty'],
  ['29827','Shoulder Arthroscopy'],['22612','Lumbar Fusion'],
  ['70553','MRI Brain w/ Contrast'],['93306','Echo Transthoracic'],
  ['43239','Upper GI Endoscopy'],['52000','Cystoscopy'],
  ['90837','Psychotherapy 60 min'],['97110','Therapeutic Exercise'],
]
const ICD_CODES   = ['M17.11','I25.10','G35','C50.911','M51.16','Z87.891','E11.9','F32.1','M54.5','N40.0']
const REVIEWERS   = ['Sarah Chen','Michael Torres','Emily Watson','James Park','Aisha Johnson']
const PLANS       = ['BlueCross PPO','Aetna HMO','United Choice','Cigna OAP','Humana Connect']
const FIRST_NAMES = ['James','Maria','Robert','Linda','David','Patricia','Michael','Barbara','William','Susan','Richard','Jessica','Thomas','Sarah','Charles','Karen']
const LAST_NAMES  = ['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis','Wilson','Martinez','Anderson','Taylor','Thomas','Hernandez','Moore']

export function generateCases(count = 250): CaseRow[] {
  return Array.from({ length: count }, (_, i) => {
    const s = i + 1
    const proc = PROCEDURES[Math.floor(rng(s * 7) * PROCEDURES.length)]
    return {
      id:              `case-${String(s).padStart(4,'0')}`,
      caseNumber:      `PA-2024-${String(s).padStart(4,'0')}`,
      status:          pick(STATUSES, s * 3),
      priority:        pick(PRIORITIES, s * 5),
      patientName:     `${pick(FIRST_NAMES, s * 11)} ${pick(LAST_NAMES, s * 13)}`,
      patientId:       `MBR${String(100000 + s).slice(1)}`,
      dob:             fmtDate(365 * 20 + Math.floor(rng(s) * 365 * 50), new Date('2024-01-01')),
      procedureCode:   proc[0],
      procedureDesc:   proc[1],
      provider:        `Dr. ${pick(FIRST_NAMES, s * 17)} ${pick(LAST_NAMES, s * 19)}`,
      specialty:       pick(SPECIALTIES, s * 23),
      npi:             `${1000000000 + Math.floor(rng(s * 2) * 999999999)}`,
      aiRecommendation: pick(AI_RECS, s * 7),
      aiConfidence:    Math.round((0.65 + rng(s * 3) * 0.30) * 100) / 100,
      diagnosisCodes:  `${pick(ICD_CODES, s * 29)}, ${pick(ICD_CODES, s * 31)}`,
      submittedAt:     fmtDate(Math.floor(rng(s * 37) * 90)),
      updatedAt:       fmtDate(Math.floor(rng(s * 41) * 30)),
      reviewer:        rng(s * 43) > 0.35 ? pick(REVIEWERS, s * 43) : undefined,
      slaHours:        Math.floor(rng(s * 47) * 72),
      documentsCount:  1 + Math.floor(rng(s * 53) * 8),
      insurancePlan:   pick(PLANS, s * 59),
    }
  })
}

// ─── Policies ─────────────────────────────────────────────────────────────────

export type PolicyRow = {
  id: string; name: string; version: string; status: string
  category: string; procedureCodes: string; icdCodes: string
  chunksCount: number; retrievalScore: number; lastUpdated: string
  createdBy: string; approvedBy?: string; approvedAt?: string
  description: string; effectiveDate: string; expiryDate?: string
  documentSizeKb: number; reviewCycle: string
}

const POL_STATUSES  = ['active','draft','under_review','archived']
const POL_CATS      = ['Medical/Surgical','Behavioral Health','Radiology','Physical Therapy','Cardiology','Oncology','Preventive']
const REVIEW_CYCLES = ['Annual','Bi-Annual','Quarterly','On-Demand']

export function generatePolicies(count = 40): PolicyRow[] {
  const names = [
    'Total Knee Arthroplasty','Hip Replacement','Lumbar Spinal Fusion','Cardiac Catheterization',
    'MRI Brain Authorization','Physical Therapy Extended','Bariatric Surgery','TAVR Procedure',
    'Cochlear Implant','Spinal Cord Stimulator','Breast Reconstruction','Proton Therapy',
    'CAR-T Cell Therapy','Deep Brain Stimulation','Penile Prosthesis','Vagus Nerve Stimulator',
    'Left Ventricular Assist Device','Lung Volume Reduction','Pancreas Transplant','Liver Transplant',
    'Kidney Dialysis Extended','Home Health Services','Skilled Nursing Facility','Inpatient Rehab',
    'Ambulance Air Transport','Durable Medical Equipment','Infusion Therapy Home','Gene Therapy',
    'Robotic Surgery Prostatectomy','Sleep Study Polysomnography',
  ]
  return Array.from({ length: count }, (_, i) => {
    const s = i + 1
    const name = names[i % names.length]
    return {
      id:              `pol-${String(s).padStart(3,'0')}`,
      name:            `${name} Policy`,
      version:         `${1 + Math.floor(rng(s*3) * 4)}.${Math.floor(rng(s*7) * 10)}`,
      status:          pick(POL_STATUSES, s*11),
      category:        pick(POL_CATS, s*13),
      procedureCodes:  `${pick(PROCEDURES,s*17)[0]}, ${pick(PROCEDURES,s*19)[0]}`,
      icdCodes:        `${pick(ICD_CODES,s*23)}, ${pick(ICD_CODES,s*29)}`,
      chunksCount:     4 + Math.floor(rng(s*31) * 20),
      retrievalScore:  Math.round((0.70 + rng(s*37) * 0.28) * 100) / 100,
      lastUpdated:     fmtDate(Math.floor(rng(s*41) * 180)),
      createdBy:       pick(REVIEWERS, s*43),
      approvedBy:      rng(s*47) > 0.3 ? pick(REVIEWERS, s*47) : undefined,
      approvedAt:      rng(s*47) > 0.3 ? fmtDate(Math.floor(rng(s*53) * 120)) : undefined,
      description:     `Clinical criteria for ${name.toLowerCase()} authorization requests`,
      effectiveDate:   fmtDate(Math.floor(rng(s*59) * 365) + 30, new Date('2024-01-01')),
      expiryDate:      rng(s*61) > 0.4 ? fmtDate(-Math.floor(rng(s*67) * 365)) : undefined,
      documentSizeKb:  20 + Math.floor(rng(s*71) * 480),
      reviewCycle:     pick(REVIEW_CYCLES, s*73),
    }
  })
}

// ─── Reviewers ────────────────────────────────────────────────────────────────

export type ReviewerRow = {
  id: string; name: string; email: string; role: string
  specialty: string; casesAssigned: number; casesCompleted: number
  avgDecisionHours: number; agreementRate: number; overrideRate: number
  status: string; lastActive: string; joinedAt: string
  certifications: string; region: string; caseload: number
  nps: number
}

const ROLES   = ['reviewer','senior_reviewer','admin','medical_director']
const REGIONS = ['Northeast','Southeast','Midwest','Southwest','West','Central']
const CERTS   = ['ABIM','ABFM','ABP','ABO','ABNS','ABPM','ABPN','ABR','ABS','ABU']
const REV_STATUSES = ['active','on_leave','inactive']

export function generateReviewers(count = 35): ReviewerRow[] {
  return Array.from({ length: count }, (_, i) => {
    const s = i + 1
    const fn = pick(FIRST_NAMES, s*11)
    const ln = pick(LAST_NAMES,  s*13)
    const completed = 50 + Math.floor(rng(s*17) * 450)
    return {
      id:               `rev-${String(s).padStart(3,'0')}`,
      name:             `Dr. ${fn} ${ln}`,
      email:            `${fn.toLowerCase()}.${ln.toLowerCase()}@healthsystem.org`,
      role:             pick(ROLES, s*23),
      specialty:        pick(SPECIALTIES, s*29),
      casesAssigned:    completed + Math.floor(rng(s*31) * 20),
      casesCompleted:   completed,
      avgDecisionHours: Math.round((1.5 + rng(s*37) * 18) * 10) / 10,
      agreementRate:    Math.round((0.72 + rng(s*41) * 0.24) * 100) / 100,
      overrideRate:     Math.round((rng(s*43) * 0.25) * 100) / 100,
      status:           pick(REV_STATUSES, s*47),
      lastActive:       fmtDate(Math.floor(rng(s*53) * 14)),
      joinedAt:         fmtDate(365 + Math.floor(rng(s*59) * 1825)),
      certifications:   `${pick(CERTS,s*61)}, ${pick(CERTS,s*67)}`,
      region:           pick(REGIONS, s*71),
      caseload:         1 + Math.floor(rng(s*73) * 25),
      nps:              Math.floor(30 + rng(s*79) * 70),
    }
  })
}

// ─── Audit entries ────────────────────────────────────────────────────────────

export type AuditRow = {
  id: string; caseRef: string; eventType: string; category: string
  actorName: string; actorRole: string; description: string
  ipAddress: string; occurredAt: string; immutable: boolean
  integrityHash: string; metadata: string; sessionId: string
}

const AUDIT_EVENTS = [
  ['SUBMITTED','decision'],['ASSIGNED','decision'],['REVIEWED','decision'],
  ['APPROVED','decision'],['DENIED','decision'],['ESCALATED','decision'],
  ['AI_PROCESSED','ai'],['AI_OUTPUT','ai'],['AI_OVERRIDE','ai'],
  ['PROMPT_TRACE','ai'],['RETRIEVAL_TRACE','ai'],
  ['CLARIFICATION_REQUESTED','clarification'],['CLARIFICATION_ANSWERED','clarification'],
  ['DOCUMENT_UPLOADED','document'],['DOCUMENT_OCR','document'],
  ['POLICY_MATCHED','policy'],['COMPLIANCE_EXPORT','compliance'],
  ['ACCESS_GRANTED','system'],['SLA_WARNING','system'],['SLA_BREACHED','system'],
]
const ACTOR_ROLES = ['reviewer','admin','ai_system','provider','system']
const IP_PREFIXES = ['192.168.1','10.0.0','172.16.0','10.10.1']

function makeHash(s: number): string {
  return Array.from({ length: 16 }, (_, i) =>
    Math.floor(rng(s * 997 + i * 97) * 16).toString(16)
  ).join('')
}

export function generateAuditEntries(count = 500): AuditRow[] {
  return Array.from({ length: count }, (_, i) => {
    const s = i + 1
    const ev = AUDIT_EVENTS[Math.floor(rng(s*3) * AUDIT_EVENTS.length)]
    const role = pick(ACTOR_ROLES, s*11)
    const caseNum = `PA-2024-${String(1 + Math.floor(rng(s*13) * 200)).padStart(4,'0')}`
    return {
      id:             `audit-${String(s).padStart(5,'0')}`,
      caseRef:        caseNum,
      eventType:      ev[0],
      category:       ev[1],
      actorName:      role === 'ai_system' ? 'LangGraph AI' : role === 'system' ? 'System' : pick(REVIEWERS, s*17),
      actorRole:      role,
      description:    `${ev[0].replace(/_/g,' ')} event for case ${caseNum}`,
      ipAddress:      `${pick(IP_PREFIXES, s*19)}.${1 + Math.floor(rng(s*23) * 254)}`,
      occurredAt:     fmtDate(Math.floor(rng(s*29) * 90) + rng(s*31) / 24),
      immutable:      true,
      integrityHash:  `sha256:${makeHash(s)}${makeHash(s*997)}`,
      metadata:       JSON.stringify({ latency: Math.floor(rng(s*37) * 2000), tokens: Math.floor(rng(s*41) * 4000) }),
      sessionId:      `sess-${makeHash(s).slice(0,8)}`,
    }
  })
}

// ─── Clarifications ───────────────────────────────────────────────────────────

export type ClarificationRow = {
  id: string; caseRef: string; questionText: string; status: string
  requestedBy: string; requestedAt: string; answeredAt?: string
  answeredBy?: string; answerText?: string; priority: string
  dueDate: string; category: string; aiSuggested: boolean
  escalated: boolean; attachments: number; responseTimeHours?: number
}

const CLAR_STATUSES  = ['pending','answered','expired','escalated','withdrawn']
const CLAR_CATS      = ['Clinical Documentation','Diagnosis Clarification','Treatment Plan','Provider Information','Insurance Eligibility','Medical History']
const QUESTIONS = [
  'Please provide documentation supporting medical necessity for this procedure.',
  'Confirm patient has failed conservative treatment for at least 6 months.',
  'Submit most recent imaging results with radiology report.',
  'Provide specialist referral letter from primary care physician.',
  'Clarify ICD-10 diagnosis code and supporting clinical notes.',
  'Documentation showing failed physical therapy trials required.',
  'Recent lab results (within 90 days) needed for this authorization.',
  'Provide surgical operative notes from prior related procedures.',
]

export function generateClarifications(count = 120): ClarificationRow[] {
  return Array.from({ length: count }, (_, i) => {
    const s = i + 1
    const status = pick(CLAR_STATUSES, s*7)
    const reqAt  = fmtDate(Math.floor(rng(s*11) * 60))
    const answered = status === 'answered'
    const rth = answered ? Math.round((0.5 + rng(s*13) * 47) * 10) / 10 : undefined
    return {
      id:                `clar-${String(s).padStart(4,'0')}`,
      caseRef:           `PA-2024-${String(1 + Math.floor(rng(s*3) * 200)).padStart(4,'0')}`,
      questionText:      pick(QUESTIONS, s*17),
      status,
      requestedBy:       pick(REVIEWERS, s*19),
      requestedAt:       reqAt,
      answeredAt:        answered ? fmtDate(Math.floor(rng(s*23) * 30)) : undefined,
      answeredBy:        answered ? `${pick(FIRST_NAMES,s*29)} ${pick(LAST_NAMES,s*31)} (Provider)` : undefined,
      answerText:        answered ? 'Clinical documentation has been submitted as requested.' : undefined,
      priority:          pick(PRIORITIES, s*37),
      dueDate:           fmtDate(-Math.floor(rng(s*41) * 14)),
      category:          pick(CLAR_CATS, s*43),
      aiSuggested:       rng(s*47) > 0.45,
      escalated:         status === 'escalated',
      attachments:       Math.floor(rng(s*53) * 4),
      responseTimeHours: rth,
    }
  })
}

// ─── Metrics ──────────────────────────────────────────────────────────────────

export type MetricRow = {
  id: string; date: string; model: string; metric: string
  value: number; unit: string; trend: string; baseline: number
  delta: number; category: string; environment: string; p95: number
  sampleCount: number; alertThreshold: number; breached: boolean
}

const METRICS_DEFS: [string, string, string, number, number][] = [
  ['hallucination_rate',   'Hallucination Rate',   '%',    3.0,   8.0  ],
  ['grounding_score',      'Grounding Score',       'score',0.85,  0.70 ],
  ['retrieval_precision',  'Retrieval Precision',   '%',    88.0,  75.0 ],
  ['ocr_accuracy',         'OCR Accuracy',          '%',    96.0,  90.0 ],
  ['avg_latency_ms',       'Avg Latency',           'ms',   1200,  3000 ],
  ['p95_latency_ms',       'P95 Latency',           'ms',   2800,  6000 ],
  ['token_usage_avg',      'Token Usage Avg',       'tok',  1800,  3500 ],
  ['clarification_freq',   'Clarification Freq',    '%',    12.0,  25.0 ],
  ['override_rate',        'Override Rate',         '%',    8.0,   20.0 ],
  ['agreement_rate',       'Agreement Rate',        '%',    91.0,  80.0 ],
  ['fallback_rate',        'Fallback Rate',         '%',    2.0,   5.0  ],
  ['cost_per_case',        'Cost per Case',         '$',    0.42,  1.50 ],
]
const MODELS     = ['claude-sonnet-4-6','claude-haiku-4-5','gpt-4o','gpt-4o-mini','llama-3-70b']
const ENVS       = ['production','staging','development']
const METRIC_CATS = ['Accuracy','Performance','Cost','Quality','Safety']

export function generateMetrics(count = 200): MetricRow[] {
  return Array.from({ length: count }, (_, i) => {
    const s = i + 1
    const [metricId, metricName, unit, baseline, threshold] = METRICS_DEFS[i % METRICS_DEFS.length]
    const noise = (rng(s * 97) - 0.5) * 0.2
    const value = Math.round((baseline * (1 + noise)) * 100) / 100
    const delta = Math.round((value - baseline) * 100) / 100
    return {
      id:              `met-${String(s).padStart(4,'0')}`,
      date:            fmtDate(Math.floor(rng(s*3) * 90)),
      model:           pick(MODELS, s*7),
      metric:          metricName,
      value,
      unit,
      trend:           delta > 0.01 ? 'up' : delta < -0.01 ? 'down' : 'stable',
      baseline,
      delta,
      category:        pick(METRIC_CATS, s*11),
      environment:     pick(ENVS, s*13),
      p95:             Math.round(value * (1 + rng(s*17) * 0.4) * 100) / 100,
      sampleCount:     100 + Math.floor(rng(s*19) * 4900),
      alertThreshold:  threshold,
      breached:        metricId.includes('rate') || metricId.includes('latency')
                       ? value > threshold
                       : value < threshold,
    }
  })
}
