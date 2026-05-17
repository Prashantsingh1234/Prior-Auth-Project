import { useState, useCallback, useEffect, useRef } from 'react'

// ─── Types ────────────────────────────────────────────────────────────────────

export type CaseStatus     = 'unassigned' | 'assigned' | 'in_review' | 'pending_info' | 'escalated' | 'completed'
export type SLAStatus      = 'on_track' | 'at_risk' | 'breached'
export type AIRecommendation = 'approve' | 'deny' | 'review'
export type RoutingMethod  = 'ai_auto' | 'ai_recommended' | 'manual' | 'escalated'
export type Urgency        = 'routine' | 'urgent' | 'stat'
export type Complexity     = 'low' | 'medium' | 'high'
export type ReviewerStatus = 'available' | 'reviewing' | 'break' | 'offline'

export interface QueueCase {
  id:              string
  caseNum:         string
  patientName:     string
  patientDOB:      string
  procedure:       string
  cpt:             string
  icd:             string
  payer:           string
  specialty:       string
  submittedAt:     Date
  slaDeadline:     Date
  slaStatus:       SLAStatus
  slaHoursLeft:    number
  aiScore:         number       // 1–100 queue priority
  aiConfidence:    number       // 0–1
  aiRecommendation: AIRecommendation
  routingMethod:   RoutingMethod
  status:          CaseStatus
  assignedTo:      string | null  // reviewer id
  urgency:         Urgency
  complexity:      Complexity
  hasOverride:     boolean
  attemptNum:      number
  diagnosisGroup:  string
  estimatedValue:  number        // $ authorization value
}

export interface Reviewer {
  id:               string
  name:             string
  initials:         string
  title:            string
  specialty:        string[]
  capacity:         number
  activeCount:      number
  completedToday:   number
  avgReviewMins:    number
  overrideRate:     number       // %
  accuracy:         number       // %
  onlineStatus:     ReviewerStatus
  isOnline:         boolean
  color:            string
  pendingCount:     number
}

export interface RoutingRule {
  id:          string
  name:        string
  condition:   string
  action:      string
  priority:    number
  triggeredToday: number
  color:       string
  enabled:     boolean
}

export interface OverrideRecord {
  id:           string
  caseId:       string
  reviewerId:   string
  reviewerName: string
  aiRecommendation: AIRecommendation
  reviewerDecision: AIRecommendation
  reason:       string
  timestamp:    Date
  flaggedForReview: boolean
}

export interface EscalationRecord {
  id:         string
  caseId:     string
  caseNum:    string
  patientName: string
  from:        string
  to:          string
  reason:      string
  level:       1 | 2 | 3
  resolvedAt?: Date
  timestamp:   Date
  status:      'open' | 'resolved'
}

export interface ReviewerMetric {
  reviewerId:     string
  name:           string
  color:          string
  today:          number
  week:           number
  avgMins:        number
  accuracy:       number
  overrideRate:   number
  slaBreaches:    number
  throughputTrend: number[]
}

// ─── Deterministic seed helpers ───────────────────────────────────────────────

function seed(n: number) { return Math.abs(Math.sin(n * 9301 + 49297) % 1) }
function hoursAgo(h: number) { return new Date(Date.now() - h * 3600000) }
function minsFromNow(m: number) { return new Date(Date.now() + m * 60000) }

// ─── Mock reviewers ───────────────────────────────────────────────────────────

const REVIEWERS: Reviewer[] = [
  { id: 'r1', name: 'Dr. Amanda Torres', initials: 'AT', title: 'MD, Senior Reviewer', specialty: ['Orthopedics', 'Rheumatology'], capacity: 12, activeCount: 8, completedToday: 6, avgReviewMins: 28, overrideRate: 5.2, accuracy: 97.4, onlineStatus: 'available', isOnline: true,  color: '#6366f1', pendingCount: 2 },
  { id: 'r2', name: 'Dr. James Park',    initials: 'JP', title: 'MD, Cardiology',      specialty: ['Cardiology', 'Vascular'],          capacity: 10, activeCount: 5, completedToday: 8, avgReviewMins: 34, overrideRate: 8.1, accuracy: 95.8, onlineStatus: 'reviewing', isOnline: true,  color: '#0ea5e9', pendingCount: 1 },
  { id: 'r3', name: 'Dr. Sarah Kim',     initials: 'SK', title: 'MD, Orthopedics',     specialty: ['Orthopedics', 'Spine'],            capacity: 10, activeCount: 10, completedToday: 4, avgReviewMins: 22, overrideRate: 3.8, accuracy: 98.1, onlineStatus: 'reviewing', isOnline: true,  color: '#10b981', pendingCount: 0 },
  { id: 'r4', name: 'Dr. Robert Chen',   initials: 'RC', title: 'MD, Oncology',        specialty: ['Oncology', 'Hematology'],          capacity: 8,  activeCount: 3, completedToday: 5, avgReviewMins: 41, overrideRate: 12.4, accuracy: 94.2, onlineStatus: 'available', isOnline: true,  color: '#a855f7', pendingCount: 3 },
  { id: 'r5', name: 'Dr. Lisa Wong',     initials: 'LW', title: 'NP, Clinical Review', specialty: ['General', 'Internal Medicine'],    capacity: 10, activeCount: 6, completedToday: 9, avgReviewMins: 19, overrideRate: 6.7, accuracy: 96.3, onlineStatus: 'available', isOnline: true,  color: '#f59e0b', pendingCount: 1 },
  { id: 'r6', name: 'Dr. Marcus Webb',   initials: 'MW', title: 'MD, Neurology',       specialty: ['Neurology', 'Neurosurgery'],       capacity: 8,  activeCount: 0, completedToday: 0, avgReviewMins: 0,  overrideRate: 9.3, accuracy: 93.8, onlineStatus: 'offline',   isOnline: false, color: '#6b7280', pendingCount: 0 },
]

// ─── Mock queue cases ─────────────────────────────────────────────────────────

function makeCase(
  id: string, caseNum: string, patient: string, dob: string,
  proc: string, cpt: string, icd: string, payer: string, specialty: string,
  diagGroup: string, status: CaseStatus, assignedTo: string | null,
  aiConf: number, aiRec: AIRecommendation, urgency: Urgency, complexity: Complexity,
  slaHours: number, routingMethod: RoutingMethod, hasOverride: boolean,
  attemptNum: number, value: number,
): QueueCase {
  const slaStatus: SLAStatus = slaHours < 0 ? 'breached' : slaHours < 2 ? 'at_risk' : 'on_track'
  const aiScore = Math.round(
    (slaHours < 0 ? 40 : slaHours < 2 ? 32 : slaHours < 6 ? 20 : 10)
    + (Math.abs(aiConf - 0.5) < 0.2 ? 25 : aiConf > 0.85 ? 5 : 15)
    + (complexity === 'high' ? 20 : complexity === 'medium' ? 12 : 5)
    + (attemptNum > 1 ? 15 : 0)
  )
  return {
    id, caseNum, patientName: patient, patientDOB: dob,
    procedure: proc, cpt, icd, payer, specialty, diagnosisGroup: diagGroup,
    submittedAt: hoursAgo(Math.round(seed(id.length) * 48 + 1)),
    slaDeadline: minsFromNow(slaHours * 60),
    slaStatus, slaHoursLeft: slaHours,
    aiScore, aiConfidence: aiConf, aiRecommendation: aiRec,
    routingMethod, status, assignedTo, urgency, complexity,
    hasOverride, attemptNum, estimatedValue: value,
  }
}

const QUEUE_CASES: QueueCase[] = [
  makeCase('c01','PA-2024-18900','Elena M. Vasquez','1978-04-12','Lumbar Fusion L4-L5','22612','M51.16','Aetna PPO','Spine','Spinal Surgery','unassigned',null,0.47,'review','stat','high',0.3,'ai_recommended',false,1,28400),
  makeCase('c02','PA-2024-18901','Thomas R. Briggs','1965-09-23','Cardiac Cath + PCI','92941','I21.01','BCBS HMO','Cardiology','Cardiac Intervention','unassigned',null,0.52,'review','stat','high',0.8,'ai_recommended',false,1,41200),
  makeCase('c03','PA-2024-18902','Aisha D. Okafor','1983-11-07','Right TKA','27447','M17.11','UHC PPO','Orthopedics','Joint Replacement','unassigned',null,0.94,'approve','urgent','low',1.4,'ai_auto',false,1,22100),
  makeCase('c04','PA-2024-18903','David L. Huang','1971-06-15','Lumbar Discectomy','63030','M51.16','Cigna PPO','Spine','Spinal Surgery','assigned','r1',0.71,'review','urgent','medium',2.1,'ai_recommended',false,1,18600),
  makeCase('c05','PA-2024-18904','Margaret J. Collins','1959-03-28','TAVR Procedure','33361','I35.1','Medicare Adv.','Cardiology','Cardiac Surgery','assigned','r2',0.58,'review','urgent','high',2.8,'ai_recommended',false,2,89300),
  makeCase('c06','PA-2024-18905','Kevin B. Nakamura','1988-12-04','Shoulder Arthroscopy','29827','M75.121','Humana HMO','Orthopedics','Joint Surgery','in_review','r3',0.91,'approve','routine','low',5.2,'ai_auto',false,1,8400),
  makeCase('c07','PA-2024-18906','Priya S. Chandrasekhar','1976-08-19','Chemotherapy Cycle 3','96413','C50.912','Aetna PPO','Oncology','Oncology Tx','in_review','r4',0.88,'approve','routine','medium',6.1,'ai_recommended',false,1,31700),
  makeCase('c08','PA-2024-18907','James F. Morrison','1962-01-31','Hip Replacement','27130','M16.11','UHC PPO','Orthopedics','Joint Replacement','assigned','r1',0.86,'approve','routine','low',7.3,'ai_auto',false,1,24800),
  makeCase('c09','PA-2024-18908','Sandra L. Perez','1969-05-17','Brain Tumor Resection','61510','C71.1','BCBS PPO','Neurology','Neurosurgery','unassigned',null,0.63,'review','urgent','high',1.1,'manual',false,3,62100),
  makeCase('c10','PA-2024-18909','Richard M. Ostrowski','1981-10-09','Coronary Bypass CABG x3','33511','I25.110','Medicare Adv.','Cardiology','Cardiac Surgery','escalated','r2',0.38,'deny','stat','high',-0.5,'escalated',true,3,94500),
  makeCase('c11','PA-2024-18910','Laura B. Fitzgerald','1974-07-22','Spinal Cord Stimulator','63685','G89.29','Cigna HMO','Spine','Spinal Device','pending_info','r1',0.55,'review','routine','high',8.2,'ai_recommended',false,2,47200),
  makeCase('c12','PA-2024-18911','Carlos E. Rivera','1990-02-14','ACL Reconstruction','27407','S83.201A','Humana PPO','Orthopedics','Joint Surgery','assigned','r3',0.89,'approve','routine','low',9.4,'ai_auto',false,1,14200),
  makeCase('c13','PA-2024-18912','Nancy T. Williams','1955-12-03','Breast Cancer Surgery','19357','C50.211','Aetna PPO','Oncology','Oncology Surgery','in_review','r4',0.77,'approve','urgent','medium',3.6,'ai_recommended',false,1,38900),
  makeCase('c14','PA-2024-18913','Anthony M. DeMarco','1967-04-28','Lumbar Spine Fusion x2','22633','M51.17','UHC PPO','Spine','Spinal Surgery','unassigned',null,0.49,'deny','routine','high',11.2,'ai_recommended',true,2,34600),
  makeCase('c15','PA-2024-18914','Michelle P. Huang','1985-09-11','Knee Meniscus Repair','29881','S83.201A','BCBS HMO','Orthopedics','Joint Surgery','assigned','r5',0.93,'approve','routine','low',14.5,'ai_auto',false,1,9800),
  makeCase('c16','PA-2024-18915','Frederick K. Salter','1948-06-07','Dialysis - ESRD','90935','N18.6','Medicare Adv.','General','Nephrology','in_review','r5',0.97,'approve','routine','low',18.3,'ai_auto',false,1,6400),
  makeCase('c17','PA-2024-18916','Olivia J. Banks','1979-03-19','MRI Brain w Contrast','70553','G89.29','Cigna PPO','Neurology','Neuroradiology','assigned','r5',0.78,'approve','routine','low',22.1,'ai_recommended',false,1,2100),
  makeCase('c18','PA-2024-18917','Gregory N. Papadopoulos','1960-11-25','Pancreatic Cancer Resection','48153','C25.0','Aetna PPO','Oncology','Oncology Surgery','unassigned',null,0.61,'review','urgent','high',1.9,'ai_recommended',false,1,78400),
  makeCase('c19','PA-2024-18918','Daniela M. Santos','1993-07-08','Shoulder Replacement','23472','M75.101','Humana PPO','Orthopedics','Joint Replacement','assigned','r3',0.82,'approve','routine','medium',28.7,'ai_recommended',false,1,19300),
  makeCase('c20','PA-2024-18919','Harold J. Blackwood','1972-01-16','Carotid Endarterectomy','35301','I65.21','BCBS PPO','Cardiology','Vascular Surgery','unassigned',null,0.44,'deny','urgent','high',1.6,'ai_recommended',true,2,31800),
]

// ─── Routing rules ────────────────────────────────────────────────────────────

const ROUTING_RULES: RoutingRule[] = [
  { id: 'rr1', name: 'High Confidence Auto-Route', condition: 'AI Confidence ≥ 90% + Approve', action: 'Assign to next available reviewer', priority: 1, triggeredToday: 8,  color: '#10b981', enabled: true },
  { id: 'rr2', name: 'Low Confidence Flag',        condition: 'AI Confidence < 55%',           action: 'Route to Senior Reviewer',         priority: 2, triggeredToday: 4,  color: '#f59e0b', enabled: true },
  { id: 'rr3', name: 'Denial Requires Senior',     condition: 'AI Recommendation = Deny',      action: 'Senior Reviewer + 2nd Opinion',    priority: 3, triggeredToday: 3,  color: '#ef4444', enabled: true },
  { id: 'rr4', name: 'Stat Urgency Immediate',     condition: 'Urgency = STAT',                action: 'Immediate assignment, override SLA', priority: 4, triggeredToday: 2,  color: '#ef4444', enabled: true },
  { id: 'rr5', name: 'Specialty Match',            condition: 'Case specialty matches reviewer', action: 'Prefer specialty-matched reviewer', priority: 5, triggeredToday: 11, color: '#6366f1', enabled: true },
  { id: 'rr6', name: 'Capacity Balancing',         condition: 'Reviewer at ≥ 80% capacity',    action: 'Route to next available reviewer', priority: 6, triggeredToday: 5,  color: '#a855f7', enabled: true },
  { id: 'rr7', name: 'Repeat Attempt Escalation',  condition: 'Attempt count ≥ 3',             action: 'Auto-escalate to Medical Director', priority: 7, triggeredToday: 1,  color: '#f59e0b', enabled: false },
]

// ─── Override records ─────────────────────────────────────────────────────────

const OVERRIDES: OverrideRecord[] = [
  { id: 'ov1', caseId: 'c10', reviewerId: 'r2', reviewerName: 'Dr. James Park',  aiRecommendation: 'deny',    reviewerDecision: 'review',  reason: 'Clinical notes indicate patient improved since last scan. Scheduling additional cardiac eval.', timestamp: hoursAgo(2),  flaggedForReview: true },
  { id: 'ov2', caseId: 'c14', reviewerId: 'r1', reviewerName: 'Dr. Amanda Torres', aiRecommendation: 'deny',  reviewerDecision: 'approve', reason: 'AI did not account for comorbidities documented in specialist notes. Case meets medical necessity criteria.', timestamp: hoursAgo(6),  flaggedForReview: true },
  { id: 'ov3', caseId: 'c20', reviewerId: 'r5', reviewerName: 'Dr. Lisa Wong',    aiRecommendation: 'deny',  reviewerDecision: 'approve', reason: 'Imaging shows progression not captured in structured data. Approving for urgent vascular intervention.', timestamp: hoursAgo(18), flaggedForReview: false },
  { id: 'ov4', caseId: 'c09', reviewerId: 'r1', reviewerName: 'Dr. Amanda Torres', aiRecommendation: 'review', reviewerDecision: 'approve', reason: 'Pathology report confirmed malignancy. Surgical urgency elevated to STAT.', timestamp: hoursAgo(28), flaggedForReview: false },
  { id: 'ov5', caseId: 'c07', reviewerId: 'r4', reviewerName: 'Dr. Robert Chen',  aiRecommendation: 'approve', reviewerDecision: 'review', reason: 'Drug interaction flagged not in AI knowledge base. Holding for pharmacist consultation.', timestamp: hoursAgo(31), flaggedForReview: true },
]

// ─── Escalations ──────────────────────────────────────────────────────────────

const ESCALATIONS: EscalationRecord[] = [
  { id: 'es1', caseId: 'c10', caseNum: 'PA-2024-18909', patientName: 'Richard Ostrowski', from: 'Dr. James Park', to: 'Medical Director', reason: 'CABG denial — patient in acute distress, requires immediate review', level: 3, timestamp: hoursAgo(1),  status: 'open' },
  { id: 'es2', caseId: 'c09', caseNum: 'PA-2024-18908', patientName: 'Sandra Perez',      from: 'Dr. Amanda Torres', to: 'Senior Reviewer', reason: 'Neurosurgery case — 3rd attempt, insufficient documentation', level: 2, timestamp: hoursAgo(4),  status: 'open' },
  { id: 'es3', caseId: 'c05', caseNum: 'PA-2024-18904', patientName: 'Margaret Collins',  from: 'Dr. James Park', to: 'Sr. Reviewer', reason: 'TAVR — conflicting specialist opinions, second review required', level: 2, timestamp: hoursAgo(8),  status: 'open' },
  { id: 'es4', caseId: 'c11', caseNum: 'PA-2024-18910', patientName: 'Laura Fitzgerald',  from: 'Auto-Router', to: 'Dr. Amanda Torres', reason: 'Missing documentation after 2 clarification attempts', level: 1, timestamp: hoursAgo(14), status: 'resolved', resolvedAt: hoursAgo(2) },
]

// ─── Analytics ────────────────────────────────────────────────────────────────

const METRICS: ReviewerMetric[] = [
  { reviewerId: 'r1', name: 'Dr. Torres',  color: '#6366f1', today: 6,  week: 34, avgMins: 28, accuracy: 97.4, overrideRate: 5.2, slaBreaches: 0, throughputTrend: [5,6,7,5,8,6,6] },
  { reviewerId: 'r2', name: 'Dr. Park',    color: '#0ea5e9', today: 8,  week: 41, avgMins: 34, accuracy: 95.8, overrideRate: 8.1, slaBreaches: 1, throughputTrend: [7,8,9,8,10,8,8] },
  { reviewerId: 'r3', name: 'Dr. Kim',     color: '#10b981', today: 4,  week: 28, avgMins: 22, accuracy: 98.1, overrideRate: 3.8, slaBreaches: 0, throughputTrend: [4,5,4,6,4,5,4] },
  { reviewerId: 'r4', name: 'Dr. Chen',    color: '#a855f7', today: 5,  week: 29, avgMins: 41, accuracy: 94.2, overrideRate: 12.4, slaBreaches: 2, throughputTrend: [4,5,6,4,7,5,5] },
  { reviewerId: 'r5', name: 'Dr. Wong',    color: '#f59e0b', today: 9,  week: 47, avgMins: 19, accuracy: 96.3, overrideRate: 6.7, slaBreaches: 0, throughputTrend: [8,9,10,9,11,9,9] },
]

// ─── Hook state ───────────────────────────────────────────────────────────────

export type SortField  = 'aiScore' | 'slaHoursLeft' | 'submittedAt' | 'aiConfidence' | 'estimatedValue'
export type SortDir    = 'asc' | 'desc'

export interface QueueFilters {
  status:     string[]
  specialty:  string[]
  reviewer:   string[]
  urgency:    string[]
  slaStatus:  string[]
  aiRec:      string[]
  complexity: string[]
}

export interface WorkflowState {
  cases:           QueueCase[]
  reviewers:       Reviewer[]
  routingRules:    RoutingRule[]
  overrides:       OverrideRecord[]
  escalations:     EscalationRecord[]
  metrics:         ReviewerMetric[]
  filters:         QueueFilters
  sortField:       SortField
  sortDir:         SortDir
  selectedIds:     Set<string>
  search:          string
  assignCase:      (caseId: string, reviewerId: string) => void
  batchAssign:     (caseIds: string[], reviewerId: string) => void
  escalateCase:    (caseId: string, reason: string) => void
  toggleSelected:  (id: string) => void
  clearSelected:   () => void
  setFilters:      (f: Partial<QueueFilters>) => void
  setSort:         (field: SortField) => void
  setSearch:       (s: string) => void
  toggleRule:      (id: string) => void
  filteredCases:   QueueCase[]
  stats: {
    total: number; unassigned: number; inReview: number; slaAtRisk: number
    slaBreached: number; avgAIScore: number; openEscalations: number
    throughputToday: number
  }
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useReviewerWorkflow(): WorkflowState {
  const [cases,      setCases]      = useState<QueueCase[]>(QUEUE_CASES)
  const [reviewers,  setReviewers]  = useState<Reviewer[]>(REVIEWERS)
  const [rules,      setRules]      = useState<RoutingRule[]>(ROUTING_RULES)
  const [overrides]                 = useState<OverrideRecord[]>(OVERRIDES)
  const [escalations, setEscalations] = useState<EscalationRecord[]>(ESCALATIONS)
  const [filters,    setFiltersState] = useState<QueueFilters>({ status: [], specialty: [], reviewer: [], urgency: [], slaStatus: [], aiRec: [], complexity: [] })
  const [sortField,  setSortField]  = useState<SortField>('aiScore')
  const [sortDir,    setSortDir]    = useState<SortDir>('desc')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [search,     setSearch]     = useState('')
  const tickRef = useRef(0)

  // Live SLA countdown
  useEffect(() => {
    const timer = setInterval(() => {
      setCases((prev) => prev.map((c) => {
        const hoursLeft = (c.slaDeadline.getTime() - Date.now()) / 3600000
        const slaStatus: SLAStatus = hoursLeft < 0 ? 'breached' : hoursLeft < 2 ? 'at_risk' : 'on_track'
        return { ...c, slaHoursLeft: Math.round(hoursLeft * 10) / 10, slaStatus }
      }))
      tickRef.current++
    }, 30000)
    return () => clearInterval(timer)
  }, [])

  const assignCase = useCallback((caseId: string, reviewerId: string) => {
    setCases((prev) => prev.map((c) =>
      c.id !== caseId ? c : { ...c, assignedTo: reviewerId, status: 'assigned' as CaseStatus }
    ))
    setReviewers((prev) => prev.map((r) =>
      r.id !== reviewerId ? r : { ...r, activeCount: r.activeCount + 1 }
    ))
  }, [])

  const batchAssign = useCallback((caseIds: string[], reviewerId: string) => {
    caseIds.forEach((id) => assignCase(id, reviewerId))
    setSelectedIds(new Set())
  }, [assignCase])

  const escalateCase = useCallback((caseId: string, reason: string) => {
    const c = cases.find((x) => x.id === caseId)
    if (!c) return
    setCases((prev) => prev.map((x) => x.id !== caseId ? x : { ...x, status: 'escalated' as CaseStatus }))
    const newEsc: EscalationRecord = {
      id:          `es${Date.now()}`,
      caseId,
      caseNum:     c.caseNum,
      patientName: c.patientName,
      from:        c.assignedTo ? reviewers.find((r) => r.id === c.assignedTo)?.name ?? 'Reviewer' : 'Auto-Router',
      to:          'Senior Reviewer',
      reason,
      level:       2,
      timestamp:   new Date(),
      status:      'open',
    }
    setEscalations((prev) => [newEsc, ...prev])
  }, [cases, reviewers])

  const toggleSelected = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }, [])

  const setFilters = useCallback((f: Partial<QueueFilters>) => {
    setFiltersState((prev) => ({ ...prev, ...f }))
  }, [])

  const setSort = useCallback((field: SortField) => {
    setSortField((prev) => {
      if (prev === field) setSortDir((d) => d === 'asc' ? 'desc' : 'asc')
      return field
    })
  }, [])

  const toggleRule = useCallback((id: string) => {
    setRules((prev) => prev.map((r) => r.id !== id ? r : { ...r, enabled: !r.enabled }))
  }, [])

  // Filter + sort
  const filteredCases = cases
    .filter((c) => {
      if (search && !c.patientName.toLowerCase().includes(search.toLowerCase()) && !c.caseNum.toLowerCase().includes(search.toLowerCase()) && !c.cpt.includes(search)) return false
      if (filters.status.length    && !filters.status.includes(c.status))          return false
      if (filters.specialty.length && !filters.specialty.includes(c.specialty))    return false
      if (filters.urgency.length   && !filters.urgency.includes(c.urgency))        return false
      if (filters.slaStatus.length && !filters.slaStatus.includes(c.slaStatus))   return false
      if (filters.aiRec.length     && !filters.aiRec.includes(c.aiRecommendation)) return false
      if (filters.complexity.length && !filters.complexity.includes(c.complexity)) return false
      if (filters.reviewer.length) {
        if (c.assignedTo === null) { if (!filters.reviewer.includes('unassigned')) return false }
        else if (!filters.reviewer.includes(c.assignedTo)) return false
      }
      return true
    })
    .sort((a, b) => {
      let diff = 0
      if (sortField === 'aiScore')       diff = a.aiScore - b.aiScore
      if (sortField === 'slaHoursLeft')  diff = a.slaHoursLeft - b.slaHoursLeft
      if (sortField === 'submittedAt')   diff = a.submittedAt.getTime() - b.submittedAt.getTime()
      if (sortField === 'aiConfidence')  diff = a.aiConfidence - b.aiConfidence
      if (sortField === 'estimatedValue') diff = a.estimatedValue - b.estimatedValue
      return sortDir === 'desc' ? -diff : diff
    })

  const stats = {
    total:           cases.length,
    unassigned:      cases.filter((c) => c.status === 'unassigned').length,
    inReview:        cases.filter((c) => c.status === 'in_review').length,
    slaAtRisk:       cases.filter((c) => c.slaStatus === 'at_risk').length,
    slaBreached:     cases.filter((c) => c.slaStatus === 'breached').length,
    avgAIScore:      Math.round(cases.reduce((s, c) => s + c.aiScore, 0) / cases.length),
    openEscalations: escalations.filter((e) => e.status === 'open').length,
    throughputToday: reviewers.reduce((s, r) => s + r.completedToday, 0),
  }

  return {
    cases, reviewers, routingRules: rules, overrides, escalations, metrics: METRICS,
    filters, sortField, sortDir, selectedIds, search,
    assignCase, batchAssign, escalateCase,
    toggleSelected, clearSelected: () => setSelectedIds(new Set()),
    setFilters, setSort, setSearch: setSearch, toggleRule,
    filteredCases, stats,
  }
}
