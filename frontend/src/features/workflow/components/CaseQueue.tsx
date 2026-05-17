import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ChevronUp, ChevronDown, ChevronsUpDown,
  CheckCircle2, Bot,
  User, Zap, Search, X, SlidersHorizontal,
  ArrowUpCircle, ChevronRight,
} from 'lucide-react'
import type {
  QueueCase, Reviewer, SortField, SortDir,
  QueueFilters, CaseStatus, AIRecommendation,
} from '../hooks/useReviewerWorkflow'

// ─── Config ───────────────────────────────────────────────────────────────────

const STATUS_CFG: Record<CaseStatus, { color: string; bg: string; label: string; dot: string }> = {
  unassigned:   { color: '#f59e0b', bg: '#f59e0b12', label: 'Unassigned',   dot: '#f59e0b' },
  assigned:     { color: '#0ea5e9', bg: '#0ea5e912', label: 'Assigned',     dot: '#0ea5e9' },
  in_review:    { color: '#8b5cf6', bg: '#8b5cf612', label: 'In Review',    dot: '#8b5cf6' },
  pending_info: { color: '#6b7280', bg: '#6b728012', label: 'Pending Info', dot: '#6b7280' },
  escalated:    { color: '#ef4444', bg: '#ef444412', label: 'Escalated',    dot: '#ef4444' },
  completed:    { color: '#10b981', bg: '#10b98112', label: 'Completed',    dot: '#10b981' },
}

const AIRC_CFG: Record<AIRecommendation, { color: string; bg: string; label: string }> = {
  approve: { color: '#10b981', bg: '#10b98115', label: 'Approve' },
  deny:    { color: '#ef4444', bg: '#ef444415', label: 'Deny'    },
  review:  { color: '#f59e0b', bg: '#f59e0b15', label: 'Review'  },
}

const URGENCY_CFG = {
  routine: { color: '#6b7280', label: 'Routine' },
  urgent:  { color: '#f59e0b', label: 'Urgent'  },
  stat:    { color: '#ef4444', label: 'STAT'    },
}

// ─── SLA cell ─────────────────────────────────────────────────────────────────

function SLACell({ hoursLeft, status }: { hoursLeft: number; status: string }) {
  const color = status === 'breached' ? '#ef4444' : status === 'at_risk' ? '#f59e0b' : '#10b981'
  const label = hoursLeft < 0
    ? `${Math.abs(hoursLeft).toFixed(1)}h over`
    : hoursLeft < 1
    ? `${Math.round(hoursLeft * 60)}m`
    : `${hoursLeft.toFixed(1)}h`

  return (
    <div className="flex items-center gap-1.5">
      <motion.div
        className="w-1 rounded-full shrink-0"
        style={{ background: color, height: 28 }}
        animate={status !== 'on_track' ? { opacity: [1, 0.4, 1] } : {}}
        transition={{ duration: 1, repeat: Infinity }}
      />
      <div>
        <p className="text-[10px] font-bold tabular-nums font-mono" style={{ color }}>{label}</p>
        <p className="text-[8px] text-[var(--text-4)] uppercase tracking-wide">{status === 'breached' ? 'BREACHED' : status === 'at_risk' ? 'AT RISK' : 'ON TRACK'}</p>
      </div>
    </div>
  )
}

// ─── AI confidence cell ───────────────────────────────────────────────────────

function ConfidenceCell({ conf, rec }: { conf: number; rec: AIRecommendation }) {
  const pct   = Math.round(conf * 100)
  const color = conf >= 0.85 ? '#10b981' : conf >= 0.65 ? '#f59e0b' : '#ef4444'
  const rcfg  = AIRC_CFG[rec]

  return (
    <div className="flex items-center gap-2">
      <div>
        <div className="flex items-center gap-1 mb-0.5">
          <Bot className="w-2.5 h-2.5" style={{ color }} />
          <span className="text-[10px] font-bold font-mono tabular-nums" style={{ color }}>{pct}%</span>
        </div>
        <span
          className="text-[8px] font-bold px-1 py-0.5 rounded-md"
          style={{ background: rcfg.bg, color: rcfg.color }}
        >
          {rcfg.label}
        </span>
      </div>
    </div>
  )
}

// ─── Priority score badge ─────────────────────────────────────────────────────

function PriorityBadge({ score }: { score: number }) {
  const color = score >= 70 ? '#ef4444' : score >= 50 ? '#f59e0b' : score >= 30 ? '#0ea5e9' : '#6b7280'
  return (
    <div
      className="w-9 h-9 rounded-xl flex items-center justify-center font-bold text-xs tabular-nums font-mono shrink-0"
      style={{ background: `${color}15`, color, border: `1.5px solid ${color}40` }}
    >
      {score}
    </div>
  )
}

// ─── Assign dropdown ──────────────────────────────────────────────────────────

function AssignDropdown({
  c, reviewers, onAssign, onClose,
}: { c: QueueCase; reviewers: Reviewer[]; onAssign: (cid: string, rid: string) => void; onClose: () => void }) {
  const online = reviewers.filter((r) => r.isOnline && r.activeCount < r.capacity)
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95, y: -4 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95, y: -4 }}
      transition={{ duration: 0.12 }}
      className="absolute right-0 top-full mt-1 z-50 rounded-xl overflow-hidden shadow-xl min-w-48"
      style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
    >
      <div className="px-3 py-2 border-b border-[var(--border)]">
        <p className="text-[10px] font-bold text-[var(--text-1)]">Assign to reviewer</p>
        <p className="text-[9px] text-[var(--text-4)] truncate">{c.patientName} · {c.cpt}</p>
      </div>
      <div className="py-1">
        {online.map((r) => {
          const specialty = c.specialty && r.specialty.includes(c.specialty)
          return (
            <button
              key={r.id}
              onClick={() => { onAssign(c.id, r.id); onClose() }}
              className="w-full flex items-center gap-2 px-3 py-2 hover:bg-[var(--surface)] transition-colors text-left"
            >
              <div className="w-5 h-5 rounded-md flex items-center justify-center text-[8px] font-bold" style={{ background: `${r.color}20`, color: r.color }}>
                {r.initials}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[10px] font-semibold text-[var(--text-1)] truncate">{r.name}</p>
                <p className="text-[8px] text-[var(--text-4)]">{r.activeCount}/{r.capacity} active</p>
              </div>
              {specialty && (
                <span className="text-[8px] px-1 py-0.5 rounded-md font-bold" style={{ background: `${r.color}15`, color: r.color }}>
                  ★
                </span>
              )}
            </button>
          )
        })}
        {online.length === 0 && (
          <p className="text-[10px] text-[var(--text-4)] text-center py-3">No reviewers available</p>
        )}
      </div>
    </motion.div>
  )
}

// ─── Case row ─────────────────────────────────────────────────────────────────

interface RowProps {
  c:          QueueCase
  reviewers:  Reviewer[]
  isSelected: boolean
  onToggle:   (id: string) => void
  onAssign:   (caseId: string, reviewerId: string) => void
  onEscalate: (caseId: string) => void
  index:      number
}

function CaseRow({ c, reviewers, isSelected, onToggle, onAssign, onEscalate, index }: RowProps) {
  const [showAssign, setShowAssign] = useState(false)
  const statusCfg  = STATUS_CFG[c.status]
  const urgencyCfg = URGENCY_CFG[c.urgency]
  const assignee   = reviewers.find((r) => r.id === c.assignedTo)

  return (
    <motion.tr
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.025, duration: 0.2 }}
      className="group border-b border-[var(--border)] hover:bg-[var(--elevated)] transition-colors cursor-pointer"
      style={{ background: isSelected ? 'rgba(99,102,241,0.05)' : undefined }}
    >
      {/* Checkbox */}
      <td className="pl-3 py-2.5 w-8">
        <input
          type="checkbox"
          checked={isSelected}
          onChange={() => onToggle(c.id)}
          className="w-3 h-3 rounded cursor-pointer accent-[#6366f1]"
          onClick={(e) => e.stopPropagation()}
        />
      </td>

      {/* Priority */}
      <td className="px-2 py-2.5 w-12">
        <PriorityBadge score={c.aiScore} />
      </td>

      {/* SLA */}
      <td className="px-2 py-2.5 w-24">
        <SLACell hoursLeft={c.slaHoursLeft} status={c.slaStatus} />
      </td>

      {/* Patient + Case */}
      <td className="px-2 py-2.5 min-w-48">
        <div>
          <div className="flex items-center gap-1.5">
            <p className="text-[11px] font-bold text-[var(--text-1)]">{c.patientName}</p>
            {c.hasOverride && (
              <span className="text-[8px] font-bold px-1 py-0.5 rounded-md bg-[#ef444415] text-[#ef4444]">OVR</span>
            )}
            {c.attemptNum > 1 && (
              <span className="text-[8px] font-bold px-1 py-0.5 rounded-md bg-[#f59e0b15] text-[#f59e0b]">
                ×{c.attemptNum}
              </span>
            )}
          </div>
          <p className="text-[9px] text-[var(--text-4)] font-mono">{c.caseNum}</p>
          <p className="text-[9px] text-[var(--text-3)] truncate max-w-44">{c.procedure}</p>
        </div>
      </td>

      {/* CPT / Payer */}
      <td className="px-2 py-2.5 w-32 hidden lg:table-cell">
        <p className="text-[10px] font-mono font-bold text-[var(--text-2)]">{c.cpt}</p>
        <p className="text-[9px] text-[var(--text-4)] truncate">{c.payer}</p>
        <span
          className="text-[8px] font-bold uppercase"
          style={{ color: urgencyCfg.color }}
        >
          {urgencyCfg.label}
        </span>
      </td>

      {/* Specialty */}
      <td className="px-2 py-2.5 w-28 hidden xl:table-cell">
        <span
          className="text-[9px] font-semibold px-1.5 py-0.5 rounded-md"
          style={{ background: 'var(--border)', color: 'var(--text-3)' }}
        >
          {c.specialty}
        </span>
      </td>

      {/* AI Confidence */}
      <td className="px-2 py-2.5 w-24">
        <ConfidenceCell conf={c.aiConfidence} rec={c.aiRecommendation} />
      </td>

      {/* Status */}
      <td className="px-2 py-2.5 w-28 hidden md:table-cell">
        <div
          className="flex items-center gap-1 px-1.5 py-1 rounded-lg w-fit"
          style={{ background: statusCfg.bg }}
        >
          <div className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: statusCfg.dot }} />
          <span className="text-[9px] font-bold" style={{ color: statusCfg.color }}>{statusCfg.label}</span>
        </div>
      </td>

      {/* Assignee */}
      <td className="px-2 py-2.5 w-32 hidden lg:table-cell">
        {assignee ? (
          <div className="flex items-center gap-1.5">
            <div
              className="w-5 h-5 rounded-md flex items-center justify-center text-[8px] font-bold shrink-0"
              style={{ background: `${assignee.color}20`, color: assignee.color }}
            >
              {assignee.initials}
            </div>
            <span className="text-[10px] text-[var(--text-3)] truncate">{assignee.name.split(' ')[1]}</span>
          </div>
        ) : (
          <span className="text-[9px] text-[var(--text-4)]">—</span>
        )}
      </td>

      {/* Value */}
      <td className="px-2 py-2.5 w-20 hidden xl:table-cell">
        <span className="text-[10px] font-mono font-semibold text-[var(--text-3)]">
          ${(c.estimatedValue / 1000).toFixed(0)}k
        </span>
      </td>

      {/* Actions */}
      <td className="px-2 py-2.5 w-28">
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity relative">
          {/* Assign */}
          <div className="relative">
            <button
              onClick={(e) => { e.stopPropagation(); setShowAssign((v) => !v) }}
              className="flex items-center gap-0.5 px-2 py-1 rounded-lg text-[9px] font-bold transition-all"
              style={{ background: '#6366f115', color: '#6366f1', border: '1px solid #6366f130' }}
            >
              <User className="w-2.5 h-2.5" />
              Assign
            </button>
            <AnimatePresence>
              {showAssign && (
                <AssignDropdown
                  c={c}
                  reviewers={reviewers}
                  onAssign={onAssign}
                  onClose={() => setShowAssign(false)}
                />
              )}
            </AnimatePresence>
          </div>

          {/* Escalate */}
          {c.status !== 'escalated' && (
            <button
              onClick={(e) => { e.stopPropagation(); onEscalate(c.id) }}
              className="p-1 rounded-lg text-[var(--text-4)] hover:text-[#f59e0b] hover:bg-[#f59e0b10] transition-all"
              title="Escalate"
            >
              <ArrowUpCircle className="w-3.5 h-3.5" />
            </button>
          )}

          {/* Review arrow */}
          <button className="p-1 rounded-lg text-[var(--text-4)] hover:text-[var(--text-1)] transition-all">
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </td>
    </motion.tr>
  )
}

// ─── Sort header ──────────────────────────────────────────────────────────────

function SortTh({ label, field, active, dir, onSort, className = '' }: {
  label: string; field: SortField; active: boolean; dir: SortDir
  onSort: (f: SortField) => void; className?: string
}) {
  const Icon = active ? (dir === 'desc' ? ChevronDown : ChevronUp) : ChevronsUpDown
  return (
    <th
      className={`px-2 py-2.5 text-left cursor-pointer select-none hover:bg-[var(--surface)] transition-colors ${className}`}
      onClick={() => onSort(field)}
    >
      <div className="flex items-center gap-1">
        <span className="text-[9px] font-bold uppercase tracking-wide text-[var(--text-4)]">{label}</span>
        <Icon className="w-3 h-3 text-[var(--text-4)]" style={{ color: active ? '#6366f1' : undefined }} />
      </div>
    </th>
  )
}

// ─── Filter bar ───────────────────────────────────────────────────────────────

interface FilterBarProps {
  filters:    QueueFilters
  search:     string
  onSearch:   (s: string) => void
  onFilter:   (f: Partial<QueueFilters>) => void
  onClear:    () => void
  total:      number
  shown:      number
}

function FilterBar({ filters, search, onSearch, onFilter, onClear, total, shown }: FilterBarProps) {
  const activeFilters = Object.values(filters).flat().length
  const hasFilters    = activeFilters > 0 || search.length > 0

  type MultiKey = keyof QueueFilters
  function toggle(key: MultiKey, value: string) {
    const arr = filters[key] as string[]
    onFilter({ [key]: arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value] } as Partial<QueueFilters>)
  }

  const chips: Array<{ key: MultiKey; value: string; label: string; color: string }> = [
    { key: 'status',    value: 'unassigned',   label: 'Unassigned', color: '#f59e0b' },
    { key: 'status',    value: 'escalated',    label: 'Escalated',  color: '#ef4444' },
    { key: 'slaStatus', value: 'breached',     label: 'SLA Breach', color: '#ef4444' },
    { key: 'slaStatus', value: 'at_risk',      label: 'SLA Risk',   color: '#f59e0b' },
    { key: 'urgency',   value: 'stat',         label: 'STAT',       color: '#ef4444' },
    { key: 'urgency',   value: 'urgent',       label: 'Urgent',     color: '#f59e0b' },
    { key: 'aiRec',     value: 'deny',         label: 'AI: Deny',   color: '#ef4444' },
    { key: 'aiRec',     value: 'review',       label: 'AI: Review', color: '#8b5cf6' },
    { key: 'complexity', value: 'high',        label: 'Complex',    color: '#a855f7' },
  ]

  return (
    <div
      className="px-4 py-2.5 border-b border-[var(--border)] shrink-0"
      style={{ background: 'var(--elevated)' }}
    >
      {/* Search + count */}
      <div className="flex items-center gap-3 mb-2">
        <div className="flex items-center gap-2 flex-1 rounded-lg px-2.5 py-1.5" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
          <Search className="w-3 h-3 text-[var(--text-4)] shrink-0" />
          <input
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            placeholder="Search patient, case #, CPT…"
            className="flex-1 text-[11px] bg-transparent outline-none text-[var(--text-1)] placeholder-[var(--text-4)]"
          />
          {search && (
            <button onClick={() => onSearch('')} className="text-[var(--text-4)] hover:text-[var(--text-1)] transition-colors">
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-[var(--text-4)]">{shown} of {total}</span>
          {hasFilters && (
            <button
              onClick={onClear}
              className="flex items-center gap-1 text-[9px] font-semibold px-2 py-1 rounded-lg transition-all"
              style={{ background: '#ef444415', color: '#ef4444', border: '1px solid #ef444430' }}
            >
              <X className="w-2.5 h-2.5" />
              Clear
            </button>
          )}
          <SlidersHorizontal className="w-3.5 h-3.5 text-[var(--text-4)]" />
        </div>
      </div>

      {/* Quick filter chips */}
      <div className="flex flex-wrap gap-1">
        {chips.map((chip) => {
          const arr     = filters[chip.key] as string[]
          const isActive = arr.includes(chip.value)
          return (
            <button
              key={`${chip.key}-${chip.value}`}
              onClick={() => toggle(chip.key, chip.value)}
              className="text-[8px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-md transition-all"
              style={{
                background: isActive ? `${chip.color}20` : 'var(--surface)',
                color:      isActive ? chip.color : 'var(--text-4)',
                border:     `1px solid ${isActive ? `${chip.color}50` : 'var(--border)'}`,
              }}
            >
              {chip.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}

// ─── Batch action bar ─────────────────────────────────────────────────────────

function BatchBar({ count, reviewers, onBatchAssign, onClear }: {
  count:          number
  reviewers:      Reviewer[]
  onBatchAssign:  (rid: string) => void
  onClear:        () => void
}) {
  const [showPicker, setShowPicker] = useState(false)
  if (count === 0) return null

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, height: 0 }}
        animate={{ opacity: 1, height: 'auto' }}
        exit={{ opacity: 0, height: 0 }}
        className="px-4 py-2 border-b border-[var(--border)] flex items-center gap-3 shrink-0"
        style={{ background: '#6366f112' }}
      >
        <span className="text-[11px] font-semibold text-[#6366f1]">{count} selected</span>
        <div className="flex items-center gap-1.5 relative">
          <button
            onClick={() => setShowPicker((v) => !v)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-semibold transition-all"
            style={{ background: '#6366f1', color: '#fff' }}
          >
            <Zap className="w-3 h-3" />
            Batch Assign
          </button>
          <AnimatePresence>
            {showPicker && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95, y: -4 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="absolute left-0 top-full mt-1 z-50 rounded-xl overflow-hidden shadow-xl min-w-48"
                style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
              >
                {reviewers.filter((r) => r.isOnline && r.activeCount < r.capacity).map((r) => (
                  <button
                    key={r.id}
                    onClick={() => { onBatchAssign(r.id); setShowPicker(false) }}
                    className="w-full flex items-center gap-2 px-3 py-2 hover:bg-[var(--surface)] transition-colors text-left"
                  >
                    <div className="w-5 h-5 rounded-md flex items-center justify-center text-[8px] font-bold" style={{ background: `${r.color}20`, color: r.color }}>
                      {r.initials}
                    </div>
                    <p className="text-[10px] font-semibold text-[var(--text-1)]">{r.name}</p>
                    <span className="ml-auto text-[9px] text-[var(--text-4)]">{r.capacity - r.activeCount} free</span>
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        <button
          onClick={onClear}
          className="text-[10px] text-[var(--text-4)] hover:text-[var(--text-2)] transition-colors ml-auto"
        >
          Clear selection
        </button>
      </motion.div>
    </AnimatePresence>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  cases:          QueueCase[]
  reviewers:      Reviewer[]
  selectedIds:    Set<string>
  filters:        QueueFilters
  sortField:      SortField
  sortDir:        SortDir
  search:         string
  totalCount:     number
  onToggle:       (id: string) => void
  onClearSelected: () => void
  onAssign:       (caseId: string, reviewerId: string) => void
  onBatchAssign:  (caseIds: string[], reviewerId: string) => void
  onEscalate:     (caseId: string) => void
  onFilter:       (f: Partial<QueueFilters>) => void
  onSort:         (field: SortField) => void
  onSearch:       (s: string) => void
}

export function CaseQueue({
  cases, reviewers, selectedIds, filters, sortField, sortDir, search, totalCount,
  onToggle, onClearSelected, onAssign, onBatchAssign, onEscalate, onFilter, onSort, onSearch,
}: Props) {
  const selected = [...selectedIds]

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Filter bar */}
      <FilterBar
        filters={filters}
        search={search}
        onSearch={onSearch}
        onFilter={onFilter}
        onClear={() => { onFilter({ status: [], specialty: [], reviewer: [], urgency: [], slaStatus: [], aiRec: [], complexity: [] }); onSearch('') }}
        total={totalCount}
        shown={cases.length}
      />

      {/* Batch bar */}
      <BatchBar
        count={selected.length}
        reviewers={reviewers}
        onBatchAssign={(rid) => onBatchAssign(selected, rid)}
        onClear={onClearSelected}
      />

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 z-10" style={{ background: 'var(--surface)' }}>
            <tr className="border-b border-[var(--border)]">
              <th className="pl-3 py-2.5 w-8">
                <input
                  type="checkbox"
                  className="w-3 h-3 rounded accent-[#6366f1]"
                  onChange={(e) => { if (!e.target.checked) onClearSelected() }}
                  checked={selected.length === cases.length && cases.length > 0}
                />
              </th>
              <SortTh label="Priority" field="aiScore"        active={sortField === 'aiScore'}        dir={sortDir} onSort={onSort} />
              <SortTh label="SLA"      field="slaHoursLeft"   active={sortField === 'slaHoursLeft'}   dir={sortDir} onSort={onSort} />
              <th className="px-2 py-2.5 text-left"><span className="text-[9px] font-bold uppercase tracking-wide text-[var(--text-4)]">Patient / Case</span></th>
              <th className="px-2 py-2.5 text-left hidden lg:table-cell"><span className="text-[9px] font-bold uppercase tracking-wide text-[var(--text-4)]">CPT / Payer</span></th>
              <th className="px-2 py-2.5 text-left hidden xl:table-cell"><span className="text-[9px] font-bold uppercase tracking-wide text-[var(--text-4)]">Specialty</span></th>
              <SortTh label="AI" field="aiConfidence" active={sortField === 'aiConfidence'} dir={sortDir} onSort={onSort} />
              <th className="px-2 py-2.5 text-left hidden md:table-cell"><span className="text-[9px] font-bold uppercase tracking-wide text-[var(--text-4)]">Status</span></th>
              <th className="px-2 py-2.5 text-left hidden lg:table-cell"><span className="text-[9px] font-bold uppercase tracking-wide text-[var(--text-4)]">Reviewer</span></th>
              <SortTh label="Value" field="estimatedValue" active={sortField === 'estimatedValue'} dir={sortDir} onSort={onSort} className="hidden xl:table-cell" />
              <th className="px-2 py-2.5 w-28"><span className="text-[9px] font-bold uppercase tracking-wide text-[var(--text-4)]">Actions</span></th>
            </tr>
          </thead>
          <tbody>
            {cases.map((c, i) => (
              <CaseRow
                key={c.id}
                c={c}
                reviewers={reviewers}
                isSelected={selectedIds.has(c.id)}
                onToggle={onToggle}
                onAssign={onAssign}
                onEscalate={onEscalate}
                index={i}
              />
            ))}
          </tbody>
        </table>

        {cases.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16">
            <CheckCircle2 className="w-8 h-8 text-[var(--text-4)] mb-2" />
            <p className="text-sm text-[var(--text-4)]">No cases match current filters</p>
          </div>
        )}
      </div>
    </div>
  )
}
