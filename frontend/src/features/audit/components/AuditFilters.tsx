import { motion, AnimatePresence } from 'framer-motion'
import { Search, X, Filter, Calendar, ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'
import type { AuditFilters, EventCategory, AuditEventType, ActorRole } from '../hooks/useAuditData'

const CATEGORY_CFG: Record<EventCategory, { label: string; color: string }> = {
  decision:    { label: 'Decision',    color: '#10b981' },
  ai:          { label: 'AI System',   color: '#6366f1' },
  clarification: { label: 'Clarification', color: '#f59e0b' },
  document:    { label: 'Document',    color: '#0ea5e9' },
  policy:      { label: 'Policy',      color: '#8b5cf6' },
  system:      { label: 'System',      color: '#6b7280' },
  compliance:  { label: 'Compliance',  color: '#ef4444' },
}

const EVENT_TYPE_GROUPS: Array<{ label: string; types: AuditEventType[] }> = [
  { label: 'Decisions',    types: ['SUBMITTED', 'ASSIGNED', 'REVIEWED', 'APPROVED', 'DENIED', 'PENDED', 'ESCALATED', 'STATUS_CHANGED'] },
  { label: 'AI Events',    types: ['AI_PROCESSED', 'AI_OUTPUT', 'AI_OVERRIDE', 'AI_FALLBACK', 'PROMPT_TRACE', 'RETRIEVAL_TRACE'] },
  { label: 'Clarifications', types: ['CLARIFICATION_REQUESTED', 'CLARIFICATION_ANSWERED', 'CLARIFICATION_ESCALATED'] },
  { label: 'Documents',    types: ['DOCUMENT_UPLOADED', 'DOCUMENT_VIEWED', 'DOCUMENT_OCR'] },
  { label: 'Policy',       types: ['POLICY_MATCHED', 'POLICY_UPDATED'] },
  { label: 'Compliance',   types: ['COMPLIANCE_EXPORT', 'ACCESS_GRANTED', 'ACCESS_REVOKED', 'SLA_BREACHED', 'SLA_WARNING'] },
]

const ROLE_CFG: Record<ActorRole, { label: string; color: string }> = {
  reviewer:   { label: 'Reviewer',   color: '#10b981' },
  admin:      { label: 'Admin',      color: '#6366f1' },
  ai_system:  { label: 'AI System',  color: '#8b5cf6' },
  provider:   { label: 'Provider',   color: '#0ea5e9' },
  system:     { label: 'System',     color: '#6b7280' },
}

const CASE_REFS = ['PA-2024-001', 'PA-2024-002', 'PA-2024-003', 'PA-2024-004', 'PA-2024-005']

interface AuditFiltersProps {
  filters:         AuditFilters
  activeCount:     number
  onSearch:        (v: string) => void
  onDateFrom:      (v: string) => void
  onDateTo:        (v: string) => void
  onCaseRef:       (v: string) => void
  onCategory:      (c: EventCategory) => void
  onEventType:     (t: AuditEventType) => void
  onRole:          (r: ActorRole) => void
  onClear:         () => void
}

export function AuditFilters({
  filters, activeCount, onSearch, onDateFrom, onDateTo, onCaseRef,
  onCategory, onEventType, onRole, onClear,
}: AuditFiltersProps) {
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())

  function toggleGroup(label: string) {
    setExpandedGroups((s) => {
      const next = new Set(s)
      next.has(label) ? next.delete(label) : next.add(label)
      return next
    })
  }

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--surface)' }}>
      {/* Header */}
      <div className="px-3 pt-3 pb-2 border-b border-[var(--border)]">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5">
            <Filter className="w-3 h-3 text-[var(--text-4)]" />
            <span className="text-[10px] font-bold uppercase tracking-wide text-[var(--text-3)]">Filters</span>
            {activeCount > 0 && (
              <span className="px-1.5 py-0.5 rounded-full text-[8px] font-bold bg-[#6366f1] text-white">{activeCount}</span>
            )}
          </div>
          {activeCount > 0 && (
            <button
              onClick={onClear}
              className="flex items-center gap-1 text-[9px] text-[var(--text-4)] hover:text-red-400 transition-colors"
            >
              <X className="w-3 h-3" /> Clear all
            </button>
          )}
        </div>

        {/* Search */}
        <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg" style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
          <Search className="w-3 h-3 text-[var(--text-4)]" />
          <input
            className="flex-1 bg-transparent text-[10px] text-[var(--text-1)] placeholder:text-[var(--text-4)] outline-none"
            placeholder="Search entries…"
            value={filters.search}
            onChange={(e) => onSearch(e.target.value)}
          />
          {filters.search && <button onClick={() => onSearch('')}><X className="w-3 h-3 text-[var(--text-4)] hover:text-[var(--text-2)]" /></button>}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-3">

        {/* Case ref */}
        <div>
          <p className="text-[8px] font-bold uppercase tracking-widest text-[var(--text-4)] mb-1.5">Case</p>
          <div className="flex flex-wrap gap-1">
            <button
              onClick={() => onCaseRef('')}
              className={cn('px-2 py-0.5 rounded-full text-[8px] font-semibold transition-colors border',
                !filters.caseRef ? 'bg-[#6366f1] text-white border-[#6366f1]' : 'bg-[var(--elevated)] text-[var(--text-4)] border-[var(--border)]')}
            >All</button>
            {CASE_REFS.map((ref) => (
              <button key={ref}
                onClick={() => onCaseRef(filters.caseRef === ref ? '' : ref)}
                className={cn('px-2 py-0.5 rounded-full text-[8px] font-mono font-semibold transition-colors border',
                  filters.caseRef === ref ? 'bg-[#6366f1] text-white border-[#6366f1]' : 'bg-[var(--elevated)] text-[var(--text-4)] border-[var(--border)]')}
              >{ref}</button>
            ))}
          </div>
        </div>

        {/* Date range */}
        <div>
          <p className="text-[8px] font-bold uppercase tracking-widest text-[var(--text-4)] mb-1.5">Date Range</p>
          <div className="space-y-1.5">
            {[
              { label: 'From', value: filters.dateFrom, onChange: onDateFrom },
              { label: 'To',   value: filters.dateTo,   onChange: onDateTo },
            ].map(({ label, value, onChange }) => (
              <div key={label} className="flex items-center gap-1.5 px-2 py-1 rounded-lg" style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
                <Calendar className="w-2.5 h-2.5 text-[var(--text-4)]" />
                <span className="text-[8px] text-[var(--text-4)] w-6 shrink-0">{label}</span>
                <input
                  type="date"
                  className="flex-1 bg-transparent text-[9px] text-[var(--text-1)] outline-none"
                  value={value}
                  onChange={(e) => onChange(e.target.value)}
                />
                {value && <button onClick={() => onChange('')}><X className="w-2.5 h-2.5 text-[var(--text-4)]" /></button>}
              </div>
            ))}
          </div>
        </div>

        {/* Categories */}
        <div>
          <p className="text-[8px] font-bold uppercase tracking-widest text-[var(--text-4)] mb-1.5">Category</p>
          <div className="flex flex-wrap gap-1">
            {(Object.entries(CATEGORY_CFG) as Array<[EventCategory, typeof CATEGORY_CFG[EventCategory]]>).map(([cat, cfg]) => {
              const active = filters.categories.includes(cat)
              return (
                <button key={cat} onClick={() => onCategory(cat)}
                  className="px-2 py-0.5 rounded-full text-[8px] font-semibold transition-all border"
                  style={{
                    background: active ? cfg.color : 'var(--elevated)',
                    color:      active ? 'white' : 'var(--text-4)',
                    border:     `1px solid ${active ? cfg.color : 'var(--border)'}`,
                  }}
                >{cfg.label}</button>
              )
            })}
          </div>
        </div>

        {/* Actor roles */}
        <div>
          <p className="text-[8px] font-bold uppercase tracking-widest text-[var(--text-4)] mb-1.5">Actor</p>
          <div className="flex flex-wrap gap-1">
            {(Object.entries(ROLE_CFG) as Array<[ActorRole, typeof ROLE_CFG[ActorRole]]>).map(([role, cfg]) => {
              const active = filters.actorRoles.includes(role)
              return (
                <button key={role} onClick={() => onRole(role)}
                  className="px-2 py-0.5 rounded-full text-[8px] font-semibold transition-all border"
                  style={{
                    background: active ? cfg.color : 'var(--elevated)',
                    color:      active ? 'white' : 'var(--text-4)',
                    border:     `1px solid ${active ? cfg.color : 'var(--border)'}`,
                  }}
                >{cfg.label}</button>
              )
            })}
          </div>
        </div>

        {/* Event types — collapsible groups */}
        <div>
          <p className="text-[8px] font-bold uppercase tracking-widest text-[var(--text-4)] mb-1.5">Event Type</p>
          <div className="space-y-1">
            {EVENT_TYPE_GROUPS.map((group) => {
              const expanded = expandedGroups.has(group.label)
              const activeInGroup = group.types.filter((t) => filters.eventTypes.includes(t)).length
              return (
                <div key={group.label} className="rounded-lg overflow-hidden" style={{ border: '1px solid var(--border)' }}>
                  <button
                    onClick={() => toggleGroup(group.label)}
                    className="w-full flex items-center justify-between px-2 py-1.5 hover:bg-[var(--elevated)] transition-colors"
                  >
                    <span className="text-[9px] font-semibold text-[var(--text-3)]">{group.label}</span>
                    <div className="flex items-center gap-1">
                      {activeInGroup > 0 && (
                        <span className="px-1 py-0.5 rounded text-[7px] font-bold bg-[#6366f1] text-white">{activeInGroup}</span>
                      )}
                      {expanded ? <ChevronUp className="w-2.5 h-2.5 text-[var(--text-4)]" /> : <ChevronDown className="w-2.5 h-2.5 text-[var(--text-4)]" />}
                    </div>
                  </button>
                  <AnimatePresence>
                    {expanded && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden"
                      >
                        <div className="px-2 pb-1.5 flex flex-wrap gap-1">
                          {group.types.map((t) => {
                            const active = filters.eventTypes.includes(t)
                            return (
                              <button key={t} onClick={() => onEventType(t)}
                                className="px-1.5 py-0.5 rounded text-[7px] font-mono font-semibold transition-all"
                                style={{
                                  background: active ? '#6366f1' : 'var(--surface)',
                                  color:      active ? 'white' : 'var(--text-4)',
                                  border:     `1px solid ${active ? '#6366f1' : 'var(--border)'}`,
                                }}
                              >{t}</button>
                            )
                          })}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
