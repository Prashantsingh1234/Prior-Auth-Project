import { motion } from 'framer-motion'
import { Wifi, WifiOff, Clock, CheckCircle2, AlertTriangle } from 'lucide-react'
import type { Reviewer, QueueCase } from '../hooks/useReviewerWorkflow'

// ─── Workload ring ────────────────────────────────────────────────────────────

function WorkloadRing({ active, capacity, color }: { active: number; capacity: number; color: string }) {
  const pct   = Math.min(active / capacity, 1)
  const r     = 16
  const circ  = 2 * Math.PI * r
  const atCapacity = pct >= 1
  const atRisk     = pct >= 0.8
  const ringColor  = atCapacity ? '#ef4444' : atRisk ? '#f59e0b' : color

  return (
    <div className="relative w-10 h-10 shrink-0">
      <svg viewBox="0 0 40 40" className="w-full h-full -rotate-90">
        <circle cx="20" cy="20" r={r} fill="none" strokeWidth="3" stroke="var(--border)" />
        <motion.circle
          cx="20" cy="20" r={r} fill="none"
          strokeWidth="3" stroke={ringColor}
          strokeLinecap="round"
          strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: circ - pct * circ }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span
          className="text-[9px] font-bold tabular-nums leading-none"
          style={{ color: ringColor }}
        >
          {active}
        </span>
      </div>
    </div>
  )
}

// ─── Status dot ───────────────────────────────────────────────────────────────

const STATUS_CFG = {
  available: { color: '#10b981', label: 'Available' },
  reviewing: { color: '#f59e0b', label: 'Reviewing' },
  break:     { color: '#6b7280', label: 'On Break' },
  offline:   { color: '#374151', label: 'Offline' },
}

// ─── Assign button ────────────────────────────────────────────────────────────

function AssignBtn({ reviewer, unassignedCount, onAssign }: {
  reviewer:       Reviewer
  unassignedCount: number
  onAssign:       (reviewerId: string) => void
}) {
  const available   = reviewer.capacity - reviewer.activeCount
  const canAssign   = reviewer.isOnline && available > 0 && unassignedCount > 0
  const assignCount = Math.min(available, unassignedCount)

  if (!canAssign) return null

  return (
    <motion.button
      whileHover={{ scale: 1.03 }}
      whileTap={{ scale: 0.97 }}
      onClick={() => onAssign(reviewer.id)}
      className="text-[8px] font-bold px-1.5 py-0.5 rounded-md transition-all"
      style={{ background: `${reviewer.color}20`, color: reviewer.color, border: `1px solid ${reviewer.color}40` }}
    >
      +{assignCount}
    </motion.button>
  )
}

// ─── Reviewer card ────────────────────────────────────────────────────────────

interface CardProps {
  reviewer:         Reviewer
  isSelected:       boolean
  unassignedCount:  number
  onSelect:         (id: string) => void
  onQuickAssign:    (reviewerId: string) => void
}

function ReviewerCard({ reviewer, isSelected, unassignedCount, onSelect, onQuickAssign }: CardProps) {
  const statusCfg  = STATUS_CFG[reviewer.onlineStatus]
  const pct        = reviewer.activeCount / reviewer.capacity
  const loadColor  = pct >= 1 ? '#ef4444' : pct >= 0.8 ? '#f59e0b' : '#10b981'

  return (
    <motion.div
      whileHover={{ x: 2 }}
      onClick={() => reviewer.isOnline && onSelect(reviewer.id)}
      className="rounded-xl px-3 py-2.5 transition-all cursor-pointer"
      style={{
        background: isSelected ? `${reviewer.color}10` : 'var(--elevated)',
        border:     `1px solid ${isSelected ? `${reviewer.color}50` : 'var(--border)'}`,
        boxShadow:  isSelected ? `0 0 12px ${reviewer.color}20` : 'none',
        opacity:    reviewer.isOnline ? 1 : 0.5,
      }}
    >
      <div className="flex items-start gap-2">
        {/* Workload ring + initials */}
        <div className="relative shrink-0">
          <WorkloadRing active={reviewer.activeCount} capacity={reviewer.capacity} color={reviewer.color} />
          {/* Status dot */}
          <div
            className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border border-[var(--bg)]"
            style={{ background: statusCfg.color }}
          />
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-1">
            <span className="text-[11px] font-bold text-[var(--text-1)] truncate">{reviewer.name}</span>
            <AssignBtn reviewer={reviewer} unassignedCount={unassignedCount} onAssign={onQuickAssign} />
          </div>
          <p className="text-[9px] text-[var(--text-4)] truncate">{reviewer.title}</p>
          <div className="flex items-center gap-2 mt-1.5">
            <span className="text-[8px] font-bold uppercase tracking-wide" style={{ color: statusCfg.color }}>
              {statusCfg.label}
            </span>
            {reviewer.isOnline && (
              <>
                <span className="text-[8px] text-[var(--text-4)]">·</span>
                <span className="text-[8px] text-[var(--text-4)]">{reviewer.capacity - reviewer.activeCount} slots free</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Capacity bar */}
      {reviewer.isOnline && (
        <div className="mt-2">
          <div className="h-1 rounded-full bg-[var(--border)] overflow-hidden">
            <motion.div
              className="h-full rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${Math.min(pct * 100, 100)}%` }}
              transition={{ duration: 0.6, ease: 'easeOut' }}
              style={{ background: loadColor }}
            />
          </div>
          <div className="flex justify-between mt-1">
            <span className="text-[8px] text-[var(--text-4)]">{reviewer.activeCount}/{reviewer.capacity}</span>
            <span className="text-[8px] font-mono" style={{ color: loadColor }}>{Math.round(pct * 100)}%</span>
          </div>
        </div>
      )}

      {/* Today stats */}
      {reviewer.isOnline && (
        <div className="flex gap-3 mt-2 pt-2 border-t border-[var(--border)]">
          <div className="flex items-center gap-1">
            <CheckCircle2 className="w-2.5 h-2.5 text-[#10b981]" />
            <span className="text-[8px] text-[var(--text-4)]">{reviewer.completedToday} done</span>
          </div>
          <div className="flex items-center gap-1">
            <Clock className="w-2.5 h-2.5 text-[var(--text-4)]" />
            <span className="text-[8px] text-[var(--text-4)]">~{reviewer.avgReviewMins}m avg</span>
          </div>
        </div>
      )}
    </motion.div>
  )
}

// ─── Workload balance bar ─────────────────────────────────────────────────────

function WorkloadBalance({ reviewers }: { reviewers: Reviewer[] }) {
  const online     = reviewers.filter((r) => r.isOnline)
  const totalCap   = online.reduce((s, r) => s + r.capacity, 0)
  const totalActive = online.reduce((s, r) => s + r.activeCount, 0)
  const balancePct = totalCap > 0 ? Math.round((totalActive / totalCap) * 100) : 0

  return (
    <div
      className="rounded-xl p-3 mb-2"
      style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-[9px] uppercase tracking-widest font-bold text-[var(--text-4)]">Team Workload</span>
        <span
          className="text-[10px] font-bold font-mono tabular-nums"
          style={{ color: balancePct >= 80 ? '#ef4444' : balancePct >= 60 ? '#f59e0b' : '#10b981' }}
        >
          {balancePct}%
        </span>
      </div>
      <div className="flex gap-0.5 h-3 rounded-lg overflow-hidden">
        {online.map((r) => {
          const share = ((r.activeCount / (totalActive || 1)) * 100).toFixed(1)
          return (
            <motion.div
              key={r.id}
              initial={{ scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ duration: 0.6, ease: 'easeOut' }}
              className="h-full"
              style={{ width: `${share}%`, background: r.color, transformOrigin: 'left', minWidth: 2 }}
              title={`${r.name}: ${r.activeCount} active`}
            />
          )
        })}
      </div>
      <div className="flex flex-wrap gap-1.5 mt-1.5">
        {online.map((r) => (
          <div key={r.id} className="flex items-center gap-1">
            <div className="w-1.5 h-1.5 rounded-full" style={{ background: r.color }} />
            <span className="text-[8px] text-[var(--text-4)]">{r.initials}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  reviewers:        Reviewer[]
  cases:            QueueCase[]
  selectedReviewer: string | null
  onSelect:         (id: string | null) => void
  onQuickAssign:    (reviewerId: string) => void
}

export function ReviewerRoster({ reviewers, cases, selectedReviewer, onSelect, onQuickAssign }: Props) {
  const online    = reviewers.filter((r) => r.isOnline)
  const offline   = reviewers.filter((r) => !r.isOnline)
  const unassigned = cases.filter((c) => c.status === 'unassigned').length

  return (
    <div
      className="flex flex-col h-full"
      style={{ borderRight: '1px solid var(--border)' }}
    >
      {/* Header */}
      <div
        className="px-3 py-3 border-b border-[var(--border)] shrink-0"
        style={{ background: 'var(--elevated)' }}
      >
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-bold text-[var(--text-1)]">Reviewer Roster</span>
          <div className="flex items-center gap-1">
            <Wifi className="w-3 h-3 text-[#10b981]" />
            <span className="text-[9px] font-semibold text-[#10b981]">{online.length} online</span>
            {offline.length > 0 && (
              <>
                <span className="text-[var(--text-4)]">·</span>
                <WifiOff className="w-3 h-3 text-[var(--text-4)]" />
                <span className="text-[9px] text-[var(--text-4)]">{offline.length}</span>
              </>
            )}
          </div>
        </div>
        {unassigned > 0 && (
          <div
            className="flex items-center gap-1.5 px-2 py-1 rounded-lg mt-1"
            style={{ background: '#f59e0b12', border: '1px solid #f59e0b30' }}
          >
            <AlertTriangle className="w-3 h-3 text-[#f59e0b] shrink-0" />
            <span className="text-[9px] font-semibold text-[#f59e0b]">
              {unassigned} unassigned case{unassigned > 1 ? 's' : ''} in queue
            </span>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-2.5 space-y-2">
        {/* Balance bar */}
        <WorkloadBalance reviewers={reviewers} />

        {/* Online reviewers */}
        {online.map((r) => (
          <ReviewerCard
            key={r.id}
            reviewer={r}
            isSelected={selectedReviewer === r.id}
            unassignedCount={unassigned}
            onSelect={(id) => onSelect(selectedReviewer === id ? null : id)}
            onQuickAssign={onQuickAssign}
          />
        ))}

        {/* Offline */}
        {offline.length > 0 && (
          <>
            <p className="text-[8px] uppercase tracking-widest font-bold text-[var(--text-4)] px-1 pt-2">Offline</p>
            {offline.map((r) => (
              <ReviewerCard
                key={r.id}
                reviewer={r}
                isSelected={false}
                unassignedCount={0}
                onSelect={() => {}}
                onQuickAssign={() => {}}
              />
            ))}
          </>
        )}
      </div>
    </div>
  )
}
