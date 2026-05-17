import { motion } from 'framer-motion'
import { AlertTriangle, TrendingUp, Clock, ArrowUpCircle, Shield } from 'lucide-react'
import type { EscalationState } from '../hooks/useClarificationManager'

// ─── Attempt gauge ────────────────────────────────────────────────────────────

function AttemptGauge({ used, max }: { used: number; max: number }) {
  const color = used >= max ? '#ef4444' : used >= max - 1 ? '#f59e0b' : '#10b981'

  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[9px] uppercase tracking-widest font-bold text-[var(--text-4)]">Attempts Used</span>
        <span className="text-sm font-bold tabular-nums font-mono" style={{ color }}>
          {used}<span className="text-[var(--text-4)] font-normal">/{max}</span>
        </span>
      </div>
      <div className="flex gap-1">
        {Array.from({ length: max }).map((_, i) => (
          <motion.div
            key={i}
            className="flex-1 h-2 rounded-full"
            initial={{ scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{ duration: 0.4, delay: i * 0.1, ease: 'easeOut' }}
            style={{
              background: i < used
                ? (i === max - 1 ? '#ef4444' : i === max - 2 ? '#f59e0b' : '#10b981')
                : 'var(--border)',
              transformOrigin: 'left',
            }}
          />
        ))}
      </div>
      <p className="text-[9px] text-[var(--text-4)] mt-1">
        {max - used} attempt{max - used !== 1 ? 's' : ''} remaining before auto-escalation
      </p>
    </div>
  )
}

// ─── Countdown ring ───────────────────────────────────────────────────────────

function CountdownRing({ daysLeft, total }: { daysLeft: number; total: number }) {
  const pct   = Math.max(0, daysLeft / total)
  const r     = 20
  const circ  = 2 * Math.PI * r
  const dash  = pct * circ
  const color = pct > 0.5 ? '#10b981' : pct > 0.25 ? '#f59e0b' : '#ef4444'

  return (
    <div className="relative w-12 h-12 shrink-0">
      <svg viewBox="0 0 48 48" className="w-full h-full -rotate-90">
        <circle cx="24" cy="24" r={r} fill="none" strokeWidth="3" stroke="var(--border)" />
        <motion.circle
          cx="24" cy="24" r={r} fill="none"
          strokeWidth="3" stroke={color}
          strokeLinecap="round"
          strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: circ - dash }}
          transition={{ duration: 1, ease: 'easeOut', delay: 0.3 }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-xs font-bold tabular-nums leading-none" style={{ color }}>{daysLeft}</span>
        <span className="text-[7px] text-[var(--text-4)]">days</span>
      </div>
    </div>
  )
}

// ─── Warning banner ───────────────────────────────────────────────────────────

function WarningBanner({ level }: { level: EscalationState['level'] }) {
  const cfg = {
    normal:    { color: '#10b981', bg: '#10b98112', text: 'Escalation risk is low.',                      Icon: Shield },
    warning:   { color: '#f59e0b', bg: '#f59e0b12', text: 'Escalation risk is elevated. Provider response needed.', Icon: AlertTriangle },
    critical:  { color: '#ef4444', bg: '#ef444412', text: 'Final attempt reached. Auto-escalation imminent.', Icon: AlertTriangle },
    escalated: { color: '#ef4444', bg: '#ef444412', text: 'Case escalated to Senior Reviewer.',            Icon: ArrowUpCircle },
  }[level]

  return (
    <motion.div
      animate={level === 'warning' || level === 'critical'
        ? { boxShadow: [`0 0 0 0 ${cfg.color}30`, `0 0 6px 3px ${cfg.color}20`, `0 0 0 0 ${cfg.color}30`] }
        : {}}
      transition={{ duration: 2, repeat: Infinity }}
      className="flex items-start gap-2 px-3 py-2.5 rounded-xl"
      style={{ background: cfg.bg, border: `1px solid ${cfg.color}30` }}
    >
      <cfg.Icon className="w-3.5 h-3.5 mt-0.5 shrink-0" style={{ color: cfg.color }} />
      <div>
        <p className="text-[10px] font-semibold" style={{ color: cfg.color }}>
          {level === 'normal' ? 'On Track' : level === 'warning' ? 'Warning' : level === 'critical' ? 'Critical' : 'Escalated'}
        </p>
        <p className="text-[9px] text-[var(--text-3)] mt-0.5">{cfg.text}</p>
      </div>
    </motion.div>
  )
}

// ─── Stat row ─────────────────────────────────────────────────────────────────

function StatRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[10px] text-[var(--text-4)]">{label}</span>
      <span className="text-[10px] font-semibold font-mono" style={{ color: color ?? 'var(--text-2)' }}>
        {value}
      </span>
    </div>
  )
}

// ─── Escalation action buttons ────────────────────────────────────────────────

function ActionButton({ label, color, onClick }: { label: string; color: string; onClick?: () => void }) {
  return (
    <motion.button
      whileHover={{ scale: 1.01, y: -1 }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      className="w-full text-[10px] font-semibold py-2 rounded-lg transition-all text-left px-3 flex items-center gap-2"
      style={{ background: `${color}12`, color, border: `1px solid ${color}30` }}
    >
      <TrendingUp className="w-3 h-3 shrink-0" />
      {label}
    </motion.button>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  escalation: EscalationState
}

export function EscalationPanel({ escalation }: Props) {
  const { usedAttempts, maxAttempts, daysSinceFirst, autoEscalateAt, daysUntilEscalation, level } = escalation

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      {/* Header */}
      <div
        className="px-4 py-3 border-b border-[var(--border)]"
        style={{ background: 'var(--elevated)' }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-3.5 h-3.5 text-[#f59e0b]" />
            <span className="text-xs font-bold text-[var(--text-1)]">Escalation Status</span>
          </div>
          <span
            className="text-[8px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full"
            style={{
              background: level === 'normal' ? '#10b98115' : level === 'warning' ? '#f59e0b15' : '#ef444415',
              color:      level === 'normal' ? '#10b981'   : level === 'warning' ? '#f59e0b'   : '#ef4444',
            }}
          >
            {level}
          </span>
        </div>
      </div>

      <div className="p-3 space-y-3">
        {/* Warning banner */}
        <WarningBanner level={level} />

        {/* Attempt gauge */}
        <div
          className="rounded-xl p-3"
          style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
        >
          <AttemptGauge used={usedAttempts} max={maxAttempts} />
        </div>

        {/* Countdown + stats */}
        <div
          className="rounded-xl p-3 flex items-start gap-3"
          style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
        >
          <CountdownRing daysLeft={daysUntilEscalation} total={autoEscalateAt} />
          <div className="flex-1 space-y-1.5">
            <StatRow label="Days since first request"  value={`${daysSinceFirst}d`} />
            <StatRow label="Auto-escalate threshold"   value={`${autoEscalateAt}d`} />
            <StatRow label="Days until escalation"     value={`${daysUntilEscalation}d`} color={daysUntilEscalation <= 2 ? '#ef4444' : daysUntilEscalation <= 4 ? '#f59e0b' : '#10b981'} />
          </div>
        </div>

        {/* SLA clock */}
        <div className="flex items-center gap-2 px-2">
          <Clock className="w-3 h-3 text-[var(--text-4)]" />
          <span className="text-[9px] text-[var(--text-4)]">
            Provider SLA: 3 business days per request · Current SLA: {Math.max(0, 3 - (daysSinceFirst % 3))} days remaining
          </span>
        </div>

        {/* Action buttons */}
        <div className="space-y-1.5">
          <p className="text-[9px] uppercase tracking-widest font-bold text-[var(--text-4)] px-1">Escalation Actions</p>
          <ActionButton label="Escalate to Senior Reviewer" color="#f59e0b" />
          <ActionButton label="Escalate to Medical Director" color="#ef4444" />
          <ActionButton label="Request External Review" color="#8b5cf6" />
        </div>
      </div>
    </div>
  )
}
