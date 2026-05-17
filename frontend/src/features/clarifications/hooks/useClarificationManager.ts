import { useState, useCallback, useRef } from 'react'

// ─── Types ────────────────────────────────────────────────────────────────────

export type MessageAuthor = 'ai' | 'reviewer' | 'provider' | 'system'
export type ThreadStatus  = 'pending' | 'answered' | 'resolved' | 'escalated' | 'overdue'
export type EvidenceStatus = 'received' | 'pending' | 'overdue' | 'waived' | 'not_required'
export type QuestionSource  = 'ai_generated' | 'reviewer_added' | 'template'

export interface Message {
  id:        string
  author:    MessageAuthor
  authorName: string
  content:   string
  timestamp: Date
  isTyping?: boolean
  attachments?: string[]
  replyTo?:  string
}

export interface ClarificationThread {
  id:          string
  title:       string
  category:    string
  source:      QuestionSource
  status:      ThreadStatus
  priority:    'high' | 'medium' | 'low'
  messages:    Message[]
  createdAt:   Date
  updatedAt:   Date
  daysOpen:    number
  attemptNum:  number
  evidenceIds?: string[]
  policyRef?:  string
  isUnread:    boolean
}

export interface MissingEvidence {
  id:          string
  label:       string
  description: string
  type:        'document' | 'lab' | 'imaging' | 'clinical_note' | 'specialist_note'
  status:      EvidenceStatus
  requestedAt: Date
  receivedAt?: Date
  daysWaiting: number
  threadId?:   string
  required:    boolean
}

export interface EscalationState {
  maxAttempts:  number
  usedAttempts: number
  daysSinceFirst: number
  autoEscalateAt: number
  daysUntilEscalation: number
  level: 'normal' | 'warning' | 'critical' | 'escalated'
}

export interface TimelineEvent {
  id:        string
  type:      'sent' | 'responded' | 'reviewed' | 'escalated' | 'resolved' | 'attempt' | 'system'
  label:     string
  detail:    string
  actor:     MessageAuthor
  timestamp: Date
  threadId?: string
}

export interface ClarificationCase {
  caseId:       string
  patientName:  string
  procedure:    string
  payer:        string
  submittedAt:  Date
  threads:      ClarificationThread[]
  evidence:     MissingEvidence[]
  escalation:   EscalationState
  timeline:     TimelineEvent[]
  providerName: string
  providerOrg:  string
  reviewerName: string
}

// ─── AI suggestion chips ──────────────────────────────────────────────────────

export interface AIChip {
  id:       string
  label:    string
  question: string
  category: string
  color:    string
}

export const AI_CHIPS: AIChip[] = [
  { id: 'chip1', label: 'PT Duration',    color: '#0ea5e9', category: 'treatment',  question: 'Please confirm the exact start and end dates of the physical therapy program, including the name and credentials of the treating therapist.' },
  { id: 'chip2', label: 'KL Grading',     color: '#8b5cf6', category: 'imaging',    question: 'The radiology report requires an explicit Kellgren-Lawrence grading score (I–IV) documented by the radiologist. Please resubmit with this classification.' },
  { id: 'chip3', label: 'Viscosuppl.',    color: '#a855f7', category: 'treatment',  question: 'Per policy §4.2.3b, please confirm which viscosupplementation agent was administered, the dates of administration, and the number of injections completed.' },
  { id: 'chip4', label: 'WOMAC Score',    color: '#6366f1', category: 'functional', question: 'A validated functional assessment score (WOMAC or equivalent) dated within 90 days of this submission is required. Please provide the complete scoring documentation.' },
  { id: 'chip5', label: 'Cardiac Clearance', color: '#10b981', category: 'pre-op', question: 'Pre-operative cardiac clearance must be from a board-certified cardiologist and dated within 90 days of the planned procedure. Please resubmit if the current documentation is outside this window.' },
  { id: 'chip6', label: 'BMI Evidence',   color: '#f59e0b', category: 'clinical',   question: 'BMI documentation must appear in the treating physician\'s clinical notes with height and weight measurements. Please provide this from the most recent office visit.' },
  { id: 'chip7', label: 'Steroid Tx',     color: '#ef4444', category: 'treatment',  question: 'Policy requires documentation of at least two corticosteroid injection attempts with documented dates. Please confirm the injection dates and response to treatment.' },
  { id: 'chip8', label: 'NSAID Trial',    color: '#06b6d4', category: 'treatment',  question: 'Please provide documentation of the NSAID trial, including the specific agent, dosage, duration, and clinical response or reason for discontinuation.' },
]

// ─── Mock data ────────────────────────────────────────────────────────────────

function daysAgo(d: number): Date { return new Date(Date.now() - d * 86400000) }
function hoursAgo(h: number): Date { return new Date(Date.now() - h * 3600000) }

const THREADS: ClarificationThread[] = [
  {
    id: 't1',
    title: 'Physical Therapy Documentation',
    category: 'treatment',
    source: 'ai_generated',
    status: 'answered',
    priority: 'high',
    attemptNum: 1,
    daysOpen: 6,
    policyRef: 'UHC-LCD §4.1.1',
    evidenceIds: ['ev1'],
    isUnread: false,
    createdAt: daysAgo(6),
    updatedAt: hoursAgo(18),
    messages: [
      {
        id: 'm1a',
        author: 'system',
        authorName: 'System',
        content: 'Thread created automatically — AI identified missing documentation for policy criterion C1.',
        timestamp: daysAgo(6),
      },
      {
        id: 'm1b',
        author: 'ai',
        authorName: 'AI System',
        content: 'Please provide the physical therapy discharge summary documenting the full course of treatment, including: (1) treatment start/end dates, (2) number of sessions completed, (3) functional outcomes measured at discharge, and (4) therapist recommendation for surgical intervention. This is required for criterion C1 — Conservative Treatment Documentation (UHC-LCD §4.1.1).',
        timestamp: daysAgo(6),
        attachments: ['Criterion C1 Policy Text'],
      },
      {
        id: 'm1c',
        author: 'provider',
        authorName: 'Dr. Sarah Chen, MD',
        content: 'Attached is the PT discharge summary from Summit Physical Therapy. Mr. Mitchell completed 24 sessions over 6 months (Apr–Oct 2025). The discharge note from therapist Mark Davies, DPT documents all outcomes. A signed letter from our office is also included confirming our recommendation for surgical evaluation.',
        timestamp: daysAgo(5),
        attachments: ['PT_Discharge_Summary_Mitchell.pdf', 'Physician_Letter_Surgery_Rec.pdf'],
      },
      {
        id: 'm1d',
        author: 'reviewer',
        authorName: 'Dr. Amanda Torres',
        content: 'Documentation received and reviewed. PT records confirm 6-month conservative treatment course. Criterion C1 marked as satisfied. Thank you for the prompt response.',
        timestamp: hoursAgo(18),
      },
    ],
  },
  {
    id: 't2',
    title: 'Radiology Report — KL Grading Required',
    category: 'imaging',
    source: 'ai_generated',
    status: 'overdue',
    priority: 'high',
    attemptNum: 2,
    daysOpen: 4,
    policyRef: 'UHC-LCD §4.1.2',
    evidenceIds: ['ev2'],
    isUnread: true,
    createdAt: daysAgo(4),
    updatedAt: daysAgo(1),
    messages: [
      {
        id: 'm2a',
        author: 'ai',
        authorName: 'AI System',
        content: 'The submitted radiology report does not include an explicit Kellgren-Lawrence (KL) severity grade. Policy §4.1.2 requires radiographic confirmation of Grade III or IV osteoarthritis with documented KL scoring by a licensed radiologist. The current report describes "severe osteoarthritis" without a standardized grading.\n\nPlease resubmit the radiology report with explicit KL grading, or obtain an addendum from the reading radiologist.',
        timestamp: daysAgo(4),
        attachments: ['Radiology Policy §4.1.2'],
      },
      {
        id: 'm2b',
        author: 'system',
        authorName: 'System',
        content: 'Reminder sent automatically — no response received after 48 hours.',
        timestamp: daysAgo(2),
      },
      {
        id: 'm2c',
        author: 'reviewer',
        authorName: 'Dr. Amanda Torres',
        content: 'Sending second request. This is attempt 2 of 3. A radiology addendum with explicit KL grading is the minimum requirement — a verbal description of severity is not sufficient for this policy. Please have the radiologist provide a formal addendum or reissue the report.',
        timestamp: daysAgo(1),
      },
    ],
  },
  {
    id: 't3',
    title: 'Viscosupplementation Records',
    category: 'treatment',
    source: 'reviewer_added',
    status: 'pending',
    priority: 'medium',
    attemptNum: 1,
    daysOpen: 2,
    policyRef: 'UHC-LCD §4.2.3b',
    evidenceIds: ['ev3'],
    isUnread: true,
    createdAt: daysAgo(2),
    updatedAt: hoursAgo(6),
    messages: [
      {
        id: 'm3a',
        author: 'reviewer',
        authorName: 'Dr. Amanda Torres',
        content: 'Per policy §4.2.3b, viscosupplementation with a recognized agent is required as part of the conservative treatment pathway for patients without contraindications. The submitted records reference hyaluronic acid injections but do not specify the agent name, number of injection cycles, or dates.\n\nPlease provide office visit notes or injection logs documenting: agent name (e.g., Synvisc-One, Hyalgan), injection dates, number of cycles, and documented clinical response.',
        timestamp: daysAgo(2),
      },
      {
        id: 'm3b',
        author: 'system',
        authorName: 'System',
        content: 'Awaiting provider response. SLA: 3 business days.',
        timestamp: daysAgo(2),
      },
    ],
  },
  {
    id: 't4',
    title: 'Cardiac Clearance Documentation',
    category: 'pre-op',
    source: 'ai_generated',
    status: 'resolved',
    priority: 'low',
    attemptNum: 1,
    daysOpen: 8,
    policyRef: 'UHC-LCD §4.3.1',
    evidenceIds: ['ev4'],
    isUnread: false,
    createdAt: daysAgo(8),
    updatedAt: daysAgo(3),
    messages: [
      {
        id: 'm4a',
        author: 'ai',
        authorName: 'AI System',
        content: 'Pre-operative cardiac clearance documentation is required for elective surgical procedures under policy §4.3.1. The current submission does not include a cardiology clearance letter. Please submit documentation from a cardiologist that: (1) confirms fitness for general or spinal anesthesia, (2) is dated within 90 days of the planned procedure, and (3) includes the cardiologist\'s signature and credentials.',
        timestamp: daysAgo(8),
      },
      {
        id: 'm4b',
        author: 'provider',
        authorName: 'Dr. Sarah Chen, MD',
        content: 'Cardiac clearance from Dr. Emily Walsh (Cardiologist, Summit Cardiology Group) dated October 28, 2025 is attached. EF 62%, NSR, cleared for elective procedure.',
        timestamp: daysAgo(7),
        attachments: ['Cardiac_Clearance_Walsh_20251028.pdf'],
      },
      {
        id: 'm4c',
        author: 'reviewer',
        authorName: 'Dr. Amanda Torres',
        content: 'Cardiac clearance verified. Documentation meets all policy requirements. Thread resolved.',
        timestamp: daysAgo(3),
      },
      {
        id: 'm4d',
        author: 'system',
        authorName: 'System',
        content: 'Thread resolved — criterion C6 satisfied.',
        timestamp: daysAgo(3),
      },
    ],
  },
]

const EVIDENCE: MissingEvidence[] = [
  { id: 'ev1', label: 'PT Discharge Summary',         type: 'clinical_note',    status: 'received',      required: true,  description: 'Full physical therapy course documentation', requestedAt: daysAgo(6), receivedAt: daysAgo(5), daysWaiting: 0,  threadId: 't1' },
  { id: 'ev2', label: 'Radiology — KL Grading',       type: 'imaging',          status: 'overdue',        required: true,  description: 'Radiologist addendum with KL score III or IV',  requestedAt: daysAgo(4), daysWaiting: 4,  threadId: 't2' },
  { id: 'ev3', label: 'Viscosupplementation Log',     type: 'clinical_note',    status: 'pending',        required: true,  description: 'Agent name, dates, cycles, clinical response',  requestedAt: daysAgo(2), daysWaiting: 2,  threadId: 't3' },
  { id: 'ev4', label: 'Cardiac Clearance Letter',     type: 'specialist_note',  status: 'received',       required: true,  description: 'Cardiologist sign-off within 90 days',          requestedAt: daysAgo(8), receivedAt: daysAgo(7), daysWaiting: 0, threadId: 't4' },
  { id: 'ev5', label: 'DEXA Bone Density Scan',       type: 'imaging',          status: 'waived',         required: false, description: 'Not required for standard TKA per §4.2.1',       requestedAt: daysAgo(8), daysWaiting: 0 },
  { id: 'ev6', label: 'WOMAC Functional Score',       type: 'document',         status: 'received',       required: true,  description: 'Functional assessment within 90 days',          requestedAt: daysAgo(8), receivedAt: daysAgo(7), daysWaiting: 0 },
]

const ESCALATION: EscalationState = {
  maxAttempts:          3,
  usedAttempts:         2,
  daysSinceFirst:       6,
  autoEscalateAt:       10,
  daysUntilEscalation:  4,
  level:                'warning',
}

const TIMELINE: TimelineEvent[] = [
  { id: 'tl1', type: 'system',    label: 'Case submitted',             detail: 'PA-2024-18847 received for review',                       actor: 'system',   timestamp: daysAgo(8) },
  { id: 'tl2', type: 'sent',      label: 'Clarification #1 sent',      detail: 'AI: Cardiac clearance documentation requested',           actor: 'ai',       timestamp: daysAgo(8),  threadId: 't4' },
  { id: 'tl3', type: 'sent',      label: 'Clarification #2 sent',      detail: 'AI: Physical therapy discharge summary requested',        actor: 'ai',       timestamp: daysAgo(6),  threadId: 't1' },
  { id: 'tl4', type: 'responded', label: 'Provider responded',         detail: 'Cardiac clearance letter submitted',                      actor: 'provider', timestamp: daysAgo(7),  threadId: 't4' },
  { id: 'tl5', type: 'reviewed',  label: 'Cardiac clearance verified', detail: 'Criterion C6 marked as satisfied',                       actor: 'reviewer', timestamp: daysAgo(3),  threadId: 't4' },
  { id: 'tl6', type: 'responded', label: 'Provider responded',         detail: 'PT discharge summary and physician letter submitted',     actor: 'provider', timestamp: daysAgo(5),  threadId: 't1' },
  { id: 'tl7', type: 'resolved',  label: 'PT documentation resolved',  detail: 'Criterion C1 satisfied — 6-month conservative treatment confirmed', actor: 'reviewer', timestamp: hoursAgo(18), threadId: 't1' },
  { id: 'tl8', type: 'sent',      label: 'Clarification #3 sent',      detail: 'AI: Radiology KL grading required (attempt 1)',           actor: 'ai',       timestamp: daysAgo(4),  threadId: 't2' },
  { id: 'tl9', type: 'attempt',   label: 'Attempt 2 — no response',    detail: 'Radiology request escalated to second attempt',          actor: 'reviewer', timestamp: daysAgo(1),  threadId: 't2' },
  { id: 'tl10', type: 'sent',     label: 'Clarification #4 sent',      detail: 'Reviewer: Viscosupplementation records requested',       actor: 'reviewer', timestamp: daysAgo(2),  threadId: 't3' },
]

// ─── Hook ─────────────────────────────────────────────────────────────────────

export interface ClarificationManagerState {
  caseData:          ClarificationCase
  activeThreadId:    string
  composerText:      string
  isProviderTyping:  boolean
  isSending:         boolean
  showTimeline:      boolean
  setActiveThread:   (id: string) => void
  setComposerText:   (text: string) => void
  sendMessage:       (content: string, author: MessageAuthor) => Promise<void>
  resolveThread:     (id: string) => void
  addThread:         (title: string, question: string, source: QuestionSource) => void
  toggleTimeline:    () => void
  applyChip:         (chip: AIChip) => void
  markEvidenceReceived: (id: string) => void
}

export function useClarificationManager(): ClarificationManagerState {
  const [threads, setThreads]         = useState<ClarificationThread[]>(THREADS)
  const [evidence, setEvidence]       = useState<MissingEvidence[]>(EVIDENCE)
  const [activeThreadId, setActiveThreadId] = useState<string>('t2')
  const [composerText, setComposerText]     = useState('')
  const [isProviderTyping, setIsProviderTyping] = useState(false)
  const [isSending, setIsSending]     = useState(false)
  const [showTimeline, setShowTimeline] = useState(false)
  const [timeline, setTimeline]       = useState<TimelineEvent[]>(TIMELINE)
  const msgCounter = useRef(100)

  function nextId() { return `m${++msgCounter.current}` }

  const sendMessage = useCallback(async (content: string, author: MessageAuthor) => {
    if (!content.trim()) return
    setIsSending(true)

    const newMsg: Message = {
      id:         nextId(),
      author,
      authorName: author === 'reviewer' ? 'Dr. Amanda Torres' : author === 'ai' ? 'AI System' : 'Dr. Sarah Chen, MD',
      content,
      timestamp: new Date(),
    }

    setThreads((prev) => prev.map((t) =>
      t.id !== activeThreadId ? t : {
        ...t,
        messages:  [...t.messages, newMsg],
        updatedAt: new Date(),
        isUnread:  false,
        status:    author === 'reviewer' || author === 'ai'
          ? (t.status === 'answered' || t.status === 'resolved' ? t.status : 'pending')
          : 'answered',
      }
    ))

    const newEvent: TimelineEvent = {
      id:        `tl${Date.now()}`,
      type:      author === 'provider' ? 'responded' : 'sent',
      label:     author === 'provider' ? 'Provider responded' : 'Message sent',
      detail:    content.slice(0, 80) + (content.length > 80 ? '…' : ''),
      actor:     author,
      timestamp: new Date(),
      threadId:  activeThreadId,
    }
    setTimeline((prev) => [...prev, newEvent])

    setIsSending(false)

    // Simulate provider typing & response when reviewer sends
    if (author === 'reviewer') {
      await new Promise((r) => setTimeout(r, 1200))
      setIsProviderTyping(true)
      await new Promise((r) => setTimeout(r, 2800))
      setIsProviderTyping(false)

      const providerReply: Message = {
        id:         nextId(),
        author:     'provider',
        authorName: 'Dr. Sarah Chen, MD',
        content:    'Thank you for the follow-up. We are gathering the requested documentation and will submit within 24 hours. We apologize for the delay.',
        timestamp:  new Date(),
      }
      setThreads((prev) => prev.map((t) =>
        t.id !== activeThreadId ? t : {
          ...t,
          messages:  [...t.messages, newMsg, providerReply],
          updatedAt: new Date(),
          status:    'answered',
          isUnread:  false,
        }
      ))
    }
  }, [activeThreadId])

  const resolveThread = useCallback((id: string) => {
    setThreads((prev) => prev.map((t) => t.id !== id ? t : { ...t, status: 'resolved', isUnread: false }))
  }, [])

  const addThread = useCallback((title: string, question: string, source: QuestionSource) => {
    const id = `t${Date.now()}`
    const newThread: ClarificationThread = {
      id,
      title,
      category:   'general',
      source,
      status:     'pending',
      priority:   'medium',
      attemptNum: 1,
      daysOpen:   0,
      isUnread:   false,
      createdAt:  new Date(),
      updatedAt:  new Date(),
      messages: [
        {
          id:         nextId(),
          author:     source === 'ai_generated' ? 'ai' : 'reviewer',
          authorName: source === 'ai_generated' ? 'AI System' : 'Dr. Amanda Torres',
          content:    question,
          timestamp:  new Date(),
        },
      ],
    }
    setThreads((prev) => [newThread, ...prev])
    setActiveThreadId(id)
  }, [])

  const applyChip = useCallback((chip: AIChip) => {
    setComposerText(chip.question)
  }, [])

  const markEvidenceReceived = useCallback((id: string) => {
    setEvidence((prev) => prev.map((e) => e.id !== id ? e : { ...e, status: 'received', receivedAt: new Date(), daysWaiting: 0 }))
  }, [])

  const caseData: ClarificationCase = {
    caseId:       'PA-2024-18847',
    patientName:  'James R. Mitchell',
    procedure:    'Total Knee Arthroplasty (CPT 27447)',
    payer:        'UHC PPO Gold',
    submittedAt:  daysAgo(8),
    threads,
    evidence,
    escalation:   ESCALATION,
    timeline,
    providerName: 'Dr. Sarah Chen, MD',
    providerOrg:  'Summit Orthopedic Associates',
    reviewerName: 'Dr. Amanda Torres',
  }

  return {
    caseData,
    activeThreadId,
    composerText,
    isProviderTyping,
    isSending,
    showTimeline,
    setActiveThread:     setActiveThreadId,
    setComposerText,
    sendMessage,
    resolveThread,
    addThread,
    toggleTimeline:      () => setShowTimeline((v) => !v),
    applyChip,
    markEvidenceReceived,
  }
}
