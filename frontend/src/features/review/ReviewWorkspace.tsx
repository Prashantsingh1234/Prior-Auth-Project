import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { clsx } from 'clsx'
import { ArrowLeft, RefreshCw, AlertTriangle } from 'lucide-react'
import { useCase } from '@/hooks/useCase'
import { StatusBadge, PriorityBadge, RecommendationBadge } from '@/components/common/StatusBadge'
import { ConfidenceBar } from '@/components/common/ConfidenceBar'
import { DocumentViewer } from './DocumentViewer'
import { ExtractedEntitiesPanel } from './ExtractedEntitiesPanel'
import { PolicyCriteriaPanel } from './PolicyCriteriaPanel'
import { RationaleViewer } from './RationaleViewer'
import { ReviewerActions } from './ReviewerActions'
import { ClarificationResponses } from './ClarificationResponses'
import { AuditHistory } from './AuditHistory'

type CenterTab = 'entities' | 'criteria' | 'rationale'
type RightTab  = 'actions' | 'clarifications' | 'audit'

export function ReviewWorkspace() {
  const { caseId }  = useParams<{ caseId: string }>()
  const navigate    = useNavigate()
  const {
    data: caseData, isLoading, isError, refetch, isFetching,
  } = useCase(caseId!)

  const [centerTab, setCenterTab] = useState<CenterTab>('entities')
  const [rightTab, setRightTab]   = useState<RightTab>('actions')

  if (isLoading) return <WorkspaceLoader />

  if (isError || !caseData) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <AlertTriangle className="w-10 h-10 text-amber-400" />
        <p className="text-slate-600 font-medium">Failed to load case</p>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700"
        >
          Retry
        </button>
      </div>
    )
  }

  const c = caseData

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Case header bar */}
      <div className="flex items-center gap-3 px-5 py-3 bg-white border-b border-slate-200 flex-shrink-0">
        <button
          onClick={() => navigate('/dashboard')}
          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>

        <div className="flex items-center gap-2 flex-wrap min-w-0">
          <span className="font-mono text-sm font-bold text-slate-900">{c.case_number}</span>
          <StatusBadge status={c.status} />
          <PriorityBadge priority={c.priority} />
          {c.ai_recommendation && (
            <RecommendationBadge recommendation={c.ai_recommendation} />
          )}
        </div>

        <div className="hidden md:flex items-center gap-3 ml-auto text-xs text-slate-500">
          <span>{c.patient.first_name} {c.patient.last_name}</span>
          <span className="text-slate-300">·</span>
          <span>{c.service_type.replace(/_/g, ' ')}</span>
          {c.ai_confidence_score != null && (
            <>
              <span className="text-slate-300">·</span>
              <ConfidenceBar score={c.ai_confidence_score} size="sm" className="w-28" />
            </>
          )}
        </div>

        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="ml-auto md:ml-2 p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
          title="Refresh"
        >
          <RefreshCw className={clsx('w-4 h-4', isFetching && 'animate-spin')} />
        </button>
      </div>

      {/* 3-panel layout */}
      <div className="flex-1 flex overflow-hidden min-h-0">

        {/* Left: Document viewer (45%) */}
        <div className="w-[45%] min-w-0 flex-shrink-0 border-r border-slate-200 overflow-hidden">
          {c.documents.length > 0 ? (
            <DocumentViewer
              caseId={c.case_id}
              documents={c.documents}
              entities={c.extracted_entities}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-slate-400 text-sm">
              No documents attached
            </div>
          )}
        </div>

        {/* Center: Entities / Criteria / Rationale (30%) */}
        <div className="w-[30%] min-w-0 flex flex-col border-r border-slate-200 overflow-hidden">
          <TabBar
            tabs={[
              { id: 'entities',  label: `Entities (${c.extracted_entities.length})` },
              { id: 'criteria',  label: `Criteria (${c.policy_criteria.length})` },
              { id: 'rationale', label: 'Rationale' },
            ] as { id: CenterTab; label: string }[]}
            active={centerTab}
            onChange={(t) => setCenterTab(t as CenterTab)}
          />
          <div className="flex-1 overflow-y-auto p-3 min-h-0">
            {centerTab === 'entities' && (
              <ExtractedEntitiesPanel entities={c.extracted_entities} />
            )}
            {centerTab === 'criteria' && (
              <PolicyCriteriaPanel criteria={c.policy_criteria} />
            )}
            {centerTab === 'rationale' && (
              <RationaleViewer
                aiRecommendation={c.ai_recommendation}
                aiConfidenceScore={c.ai_confidence_score}
                aiRationale={c.ai_rationale}
                policyCriteria={c.policy_criteria}
              />
            )}
          </div>
        </div>

        {/* Right: Actions / Clarifications / Audit (flex-1) */}
        <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
          <TabBar
            tabs={[
              { id: 'actions',        label: 'Actions' },
              { id: 'clarifications', label: `Clarifications (${c.clarifications.length})` },
              { id: 'audit',          label: 'Audit' },
            ] as { id: RightTab; label: string }[]}
            active={rightTab}
            onChange={(t) => setRightTab(t as RightTab)}
          />
          <div className="flex-1 overflow-y-auto p-3 min-h-0">
            {rightTab === 'actions' && <ReviewerActions caseData={c} />}
            {rightTab === 'clarifications' && (
              <ClarificationResponses
                caseId={c.case_id}
                clarifications={c.clarifications}
              />
            )}
            {rightTab === 'audit' && (
              <AuditHistory events={c.audit_trail} />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function TabBar<T extends string>({
  tabs, active, onChange,
}: { tabs: { id: T; label: string }[]; active: T; onChange: (id: T) => void }) {
  return (
    <div className="flex bg-slate-50 border-b border-slate-200 flex-shrink-0">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={clsx(
            'flex-1 py-2 px-2 text-xs font-medium transition-colors border-b-2 whitespace-nowrap',
            active === tab.id
              ? 'border-brand-500 text-brand-700 bg-white'
              : 'border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-100',
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}

function WorkspaceLoader() {
  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="h-14 bg-white border-b border-slate-200 animate-pulse flex-shrink-0" />
      <div className="flex-1 flex">
        <div className="w-[45%] bg-slate-100 animate-pulse border-r border-slate-200" />
        <div className="w-[30%] bg-slate-50 animate-pulse border-r border-slate-200" />
        <div className="flex-1 bg-white animate-pulse" />
      </div>
    </div>
  )
}
