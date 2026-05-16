import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowLeft, FileText, Tag, ClipboardList, MessageSquare, Clock, Loader2 } from 'lucide-react'
import { StatusBadge, PriorityBadge } from '@/components/common/StatusBadge'
import { ConfidenceBar } from '@/components/common/ConfidenceBar'
import { DocumentViewer } from './DocumentViewer'
import { ExtractedEntitiesPanel } from './ExtractedEntitiesPanel'
import { PolicyCriteriaPanel } from './PolicyCriteriaPanel'
import { RationaleViewer } from './RationaleViewer'
import { ReviewerActions } from './ReviewerActions'
import { AuditHistory } from './AuditHistory'
import { cn } from '@/lib/utils'

const TABS = [
  { id: 'documents',  label: 'Documents',  icon: FileText },
  { id: 'entities',   label: 'Entities',   icon: Tag },
  { id: 'criteria',   label: 'Criteria',   icon: ClipboardList },
  { id: 'rationale',  label: 'AI Rationale', icon: MessageSquare },
  { id: 'audit',      label: 'Audit Trail', icon: Clock },
] as const

type TabId = typeof TABS[number]['id']

const MOCK_CASE = {
  id: 'c1',
  caseNumber: 'PA-2024-001',
  status: 'UNDER_REVIEW' as const,
  priority: 'URGENT' as const,
  aiRecommendation: 'APPROVE' as const,
  confidence: 0.91,
  patient: { firstName: 'Maria', lastName: 'Gonzalez', memberId: 'MBR-78934', dob: '1968-03-22' },
  provider: { name: 'Dr. Robert Stein', npi: '1234567890', specialty: 'Orthopedic Surgery' },
  procedure: 'Total Knee Arthroplasty',
  cptCode: '27447',
  diagnosisCodes: ['M17.11', 'M25.361'],
  submittedAt: new Date(Date.now() - 3600000).toISOString(),
}

export function ReviewWorkspace() {
  const { caseId } = useParams()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<TabId>('documents')

  const PANEL_MAP: Record<TabId, React.ReactNode> = {
    documents: <DocumentViewer />,
    entities:  <ExtractedEntitiesPanel />,
    criteria:  <PolicyCriteriaPanel />,
    rationale: <RationaleViewer />,
    audit:     <AuditHistory />,
  }

  return (
    <div className="flex flex-col h-full bg-[var(--bg)]">
      {/* Top bar */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-4 px-6 py-4 border-b border-[var(--border)] bg-[var(--surface)] flex-shrink-0"
      >
        <button
          onClick={() => navigate('/dashboard')}
          className="p-1.5 rounded-lg text-[var(--text-3)] hover:bg-[var(--elevated)] hover:text-[var(--text-1)] transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>

        <div className="flex-1 flex items-center gap-4 min-w-0">
          <div>
            <div className="flex items-center gap-2">
              <span className="mono text-xs text-brand-400">{MOCK_CASE.caseNumber}</span>
              <StatusBadge status={MOCK_CASE.status} />
              <PriorityBadge priority={MOCK_CASE.priority} />
            </div>
            <p className="text-sm font-semibold text-[var(--text-1)] mt-0.5">
              {MOCK_CASE.patient.firstName} {MOCK_CASE.patient.lastName} — {MOCK_CASE.procedure}
            </p>
          </div>
        </div>

        {/* AI confidence summary */}
        <div className="flex items-center gap-3 px-4 py-2 rounded-lg bg-[var(--elevated)] border border-[var(--border)]">
          <div>
            <p className="text-xs text-[var(--text-3)]">AI Recommendation</p>
            <p className="text-sm font-semibold text-emerald-400">Approve</p>
          </div>
          <div className="w-px h-8 bg-[var(--border)]" />
          <div className="min-w-28">
            <p className="text-xs text-[var(--text-3)] mb-1">Confidence</p>
            <ConfidenceBar value={MOCK_CASE.confidence} size="sm" />
          </div>
        </div>
      </motion.div>

      {/* Main body — left panel + right actions */}
      <div className="flex flex-1 min-h-0">
        {/* Left: tabs + content */}
        <div className="flex flex-col flex-1 min-w-0">
          {/* Tabs */}
          <div className="flex items-center gap-1 px-6 pt-4 border-b border-[var(--border)] bg-[var(--surface)] flex-shrink-0">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-2 text-sm rounded-t-lg border-b-2 transition-colors relative -mb-px',
                  activeTab === id
                    ? 'border-brand-400 text-brand-400 bg-brand-500/5'
                    : 'border-transparent text-[var(--text-3)] hover:text-[var(--text-2)]'
                )}
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
              </button>
            ))}
          </div>

          {/* Panel */}
          <div className="flex-1 overflow-auto p-6">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.15 }}
              >
                {PANEL_MAP[activeTab]}
              </motion.div>
            </AnimatePresence>
          </div>
        </div>

        {/* Right: reviewer actions */}
        <div className="w-80 xl:w-96 flex-shrink-0 border-l border-[var(--border)] overflow-y-auto">
          <ReviewerActions caseData={MOCK_CASE} />
        </div>
      </div>
    </div>
  )
}