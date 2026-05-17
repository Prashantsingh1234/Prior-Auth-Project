import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  FileText, Activity, CheckCircle2, XCircle, Brain, Zap,
  Clock, Shield, Download, PanelRightClose, PanelRightOpen, Lock,
} from 'lucide-react'
import { useAuditData }     from './hooks/useAuditData'
import { AuditFilters }     from './components/AuditFilters'
import { AuditTimeline }    from './components/AuditTimeline'
import { AuditDetailPanel } from './components/AuditDetailPanel'
import { ComplianceExport } from './components/ComplianceExport'

// ─── Stat chip ────────────────────────────────────────────────────────────────

function StatChip({
  icon: Icon, label, value, color, pulse = false,
}: { icon: React.ElementType; label: string; value: string | number; color: string; pulse?: boolean }) {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl relative overflow-hidden"
         style={{ background: `${color}10`, border: `1px solid ${color}25` }}>
      {pulse && (
        <motion.div className="absolute inset-0 rounded-xl"
          animate={{ opacity: [0, 0.12, 0] }} transition={{ duration: 1.6, repeat: Infinity }}
          style={{ background: color }} />
      )}
      <Icon className="w-3 h-3 relative z-10 shrink-0" style={{ color }} />
      <div className="relative z-10">
        <p className="text-[7px] uppercase tracking-widest font-bold text-[var(--text-4)] leading-none">{label}</p>
        <p className="text-sm font-bold tabular-nums font-mono leading-tight mt-0.5" style={{ color }}>{value}</p>
      </div>
    </div>
  )
}

// ─── Immutability notice bar ──────────────────────────────────────────────────

function ImmutabilityBar() {
  return (
    <div
      className="shrink-0 flex items-center gap-3 px-5 py-1.5 border-b border-[var(--border)]"
      style={{ background: 'rgba(16,185,129,0.04)', borderBottom: '1px solid rgba(16,185,129,0.12)' }}
    >
      <motion.div animate={{ opacity: [1, 0.4, 1] }} transition={{ duration: 3, repeat: Infinity }}>
        <Lock className="w-3 h-3 text-emerald-400" />
      </motion.div>
      <span className="text-[9px] font-semibold text-emerald-400">
        Immutable audit trail — all records cryptographically signed and tamper-evident
      </span>
      <div className="ml-auto flex items-center gap-3">
        {['HIPAA §164.312(b)', 'SOC 2 Type II', '21 CFR Part 11'].map((b) => (
          <span key={b} className="flex items-center gap-1 text-[8px] font-mono text-emerald-400/60">
            <Shield className="w-2 h-2" />{b}
          </span>
        ))}
      </div>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export function AuditLogPage() {
  const audit = useAuditData()
  const [showFilters, setShowFilters]   = useState(true)
  const [showDetail,  setShowDetail]    = useState(true)

  return (
    <div className="flex flex-col h-full min-h-0 overflow-hidden">

      {/* ── Page header ──────────────────────────────────────────────────────── */}
      <div className="shrink-0 border-b border-[var(--border)]" style={{ background: 'var(--elevated)' }}>
        <div className="flex items-center justify-between px-5 py-3 gap-4">
          {/* Title */}
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
                 style={{ background: '#6366f115', border: '1px solid #6366f130' }}>
              <FileText className="w-4 h-4 text-[#6366f1]" />
            </div>
            <div>
              <p className="text-sm font-bold text-[var(--text-1)]">Compliance Audit Log</p>
              <p className="text-[10px] text-[var(--text-4)]">
                Complete action timeline · AI traces · Reviewer decisions · Override history · Immutable records
              </p>
            </div>
          </div>

          {/* Stats */}
          <div className="flex items-center gap-2 shrink-0 flex-wrap">
            <StatChip icon={Activity}     label="Total Events"  value={audit.stats.total}       color="#6366f1" />
            <StatChip icon={CheckCircle2} label="Approvals"     value={audit.stats.approvals}   color="#10b981" />
            <StatChip icon={XCircle}      label="Denials"       value={audit.stats.denials}      color="#ef4444" />
            <StatChip icon={Brain}        label="AI Events"     value={audit.stats.aiEvents}     color="#8b5cf6" />
            <StatChip icon={Zap}          label="Overrides"     value={audit.stats.overrides}    color="#f59e0b" pulse={audit.stats.overrides > 0} />
            <StatChip icon={Clock}        label="SLA Breaches"  value={audit.stats.breaches}     color="#ef4444" pulse={audit.stats.breaches > 0} />
            <StatChip icon={Shield}       label="Compliance"    value={audit.stats.compliance}   color="#10b981" />
          </div>

          {/* Controls */}
          <div className="flex items-center gap-1.5 shrink-0">
            <motion.button
              whileTap={{ scale: 0.96 }}
              onClick={() => audit.setExportOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-semibold text-white transition-colors"
              style={{ background: '#10b981' }}
            >
              <Download className="w-3 h-3" />
              Export
            </motion.button>
            <button
              onClick={() => setShowFilters((v) => !v)}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[10px] text-[var(--text-3)] transition-colors hover:bg-[var(--surface)]"
              style={{ border: '1px solid var(--border)' }}
              title={showFilters ? 'Hide filters' : 'Show filters'}
            >
              {showFilters ? <PanelRightClose className="w-3.5 h-3.5" /> : <PanelRightOpen className="w-3.5 h-3.5" />}
            </button>
            <button
              onClick={() => setShowDetail((v) => !v)}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[10px] text-[var(--text-3)] transition-colors hover:bg-[var(--surface)]"
              style={{ border: '1px solid var(--border)' }}
              title={showDetail ? 'Hide detail panel' : 'Show detail panel'}
            >
              {showDetail ? <PanelRightClose className="w-3.5 h-3.5" /> : <PanelRightOpen className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Immutability bar */}
      <ImmutabilityBar />

      {/* ── Body ─────────────────────────────────────────────────────────────── */}
      <div className="flex-1 min-h-0 flex overflow-hidden">

        {/* LEFT — Filters */}
        <AnimatePresence initial={false}>
          {showFilters && (
            <motion.div
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 240, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
              className="shrink-0 border-r border-[var(--border)] overflow-hidden"
            >
              <div style={{ width: 240 }}>
                <AuditFilters
                  filters={audit.filters}
                  activeCount={audit.activeFilterCount}
                  onSearch={(v) => audit.patchFilter('search', v)}
                  onDateFrom={(v) => audit.patchFilter('dateFrom', v)}
                  onDateTo={(v) => audit.patchFilter('dateTo', v)}
                  onCaseRef={(v) => audit.patchFilter('caseRef', v)}
                  onCategory={audit.toggleCategory}
                  onEventType={audit.toggleEventType}
                  onRole={audit.toggleRole}
                  onClear={audit.clearFilters}
                />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* CENTER — Timeline */}
        <div className="flex-1 min-w-0 min-h-0 flex flex-col overflow-hidden" style={{ background: 'var(--surface)' }}>
          <AuditTimeline
            entries={audit.filtered}
            selectedId={audit.selectedEntry?.id ?? null}
            onSelect={audit.setSelectedId}
            totalCount={audit.entries.length}
          />
        </div>

        {/* RIGHT — Detail panel */}
        <AnimatePresence initial={false}>
          {showDetail && (
            <motion.div
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 420, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
              className="shrink-0 border-l border-[var(--border)] overflow-hidden flex flex-col"
              style={{ background: 'var(--surface)' }}
            >
              <div style={{ width: 420 }} className="flex flex-col h-full overflow-hidden">
                <AnimatePresence mode="wait">
                  {audit.selectedEntry ? (
                    <AuditDetailPanel key={audit.selectedEntry.id} entry={audit.selectedEntry} />
                  ) : (
                    <motion.div
                      key="empty"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="flex-1 flex flex-col items-center justify-center gap-3 px-6"
                    >
                      <div className="w-12 h-12 rounded-2xl flex items-center justify-center" style={{ background: '#6366f110', border: '1px solid #6366f125' }}>
                        <FileText className="w-6 h-6 text-[#6366f1]" />
                      </div>
                      <div className="text-center">
                        <p className="text-sm font-semibold text-[var(--text-2)]">Select an audit entry</p>
                        <p className="text-[10px] text-[var(--text-4)] mt-1">Click any entry in the timeline to view complete details, AI traces, and integrity proof</p>
                      </div>
                      <div className="mt-4 rounded-xl p-3 w-full" style={{ background: 'rgba(16,185,129,0.05)', border: '1px solid rgba(16,185,129,0.15)' }}>
                        <div className="flex items-center gap-2 mb-2">
                          <Lock className="w-3 h-3 text-emerald-400" />
                          <span className="text-[9px] font-bold text-emerald-400 uppercase tracking-wide">Record Integrity</span>
                        </div>
                        <p className="text-[8px] text-emerald-400/70 leading-relaxed">
                          All {audit.entries.length} audit entries are cryptographically hashed and immutable. Each record includes actor identity, timestamp, IP address, and a non-repudiable SHA-256 integrity hash.
                        </p>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── Compliance export drawer ──────────────────────────────────────────── */}
      <AnimatePresence>
        {audit.exportOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40"
              style={{ background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(2px)' }}
              onClick={() => audit.setExportOpen(false)}
            />
            <motion.div
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
              className="fixed right-0 top-0 bottom-0 z-50 flex flex-col shadow-2xl"
              style={{ width: 480, background: 'var(--surface)', borderLeft: '1px solid var(--border)' }}
            >
              <ComplianceExport
                totalEntries={audit.entries.length}
                onClose={() => audit.setExportOpen(false)}
              />
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}
