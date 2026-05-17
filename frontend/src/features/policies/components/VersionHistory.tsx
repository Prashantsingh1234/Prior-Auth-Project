import { motion } from 'framer-motion'
import { GitBranch, CheckCircle2, Clock, Archive, AlertCircle, ArrowRight } from 'lucide-react'
import type { PolicyVersion, PolicyStatus } from '../hooks/usePolicyManager'

const STATUS_CFG: Record<PolicyStatus, { color: string; icon: React.ElementType }> = {
  active:       { color: '#10b981', icon: CheckCircle2 },
  draft:        { color: '#f59e0b', icon: Clock },
  archived:     { color: '#6b7280', icon: Archive },
  under_review: { color: '#6366f1', icon: AlertCircle },
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function VersionBadge({ version, status, isCurrent }: { version: string; status: PolicyStatus; isCurrent: boolean }) {
  const cfg = STATUS_CFG[status]
  return (
    <div
      className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg"
      style={{
        background: `${cfg.color}12`,
        border:     `1px solid ${cfg.color}${isCurrent ? '60' : '25'}`,
      }}
    >
      <cfg.icon className="w-3 h-3" style={{ color: cfg.color }} />
      <span className="text-[10px] font-bold font-mono" style={{ color: cfg.color }}>v{version}</span>
      {isCurrent && (
        <span className="text-[8px] px-1 py-0.5 rounded bg-[#10b981]/20 text-emerald-400 font-semibold uppercase tracking-wide">current</span>
      )}
    </div>
  )
}

interface VersionHistoryProps {
  versions:       PolicyVersion[]
  currentVersion: string
}

export function VersionHistory({ versions, currentVersion }: VersionHistoryProps) {
  return (
    <div className="p-4 space-y-3">
      <div className="flex items-center gap-2 mb-2">
        <GitBranch className="w-3.5 h-3.5 text-[var(--text-4)]" />
        <span className="text-[10px] font-bold uppercase tracking-wide text-[var(--text-3)]">Version History</span>
        <span className="text-[9px] text-[var(--text-4)]">({versions.length} versions)</span>
      </div>

      {/* Timeline */}
      <div className="relative">
        {/* Vertical rail */}
        <div
          className="absolute left-[14px] top-4 bottom-4 w-px"
          style={{ background: 'var(--border)' }}
        />

        <div className="space-y-0">
          {versions.map((v, i) => {
            const isCurrent = v.version === currentVersion
            const cfg = STATUS_CFG[v.status]
            return (
              <motion.div
                key={v.version}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.06 }}
                className="flex gap-4 relative"
              >
                {/* Node */}
                <div className="relative z-10 mt-3 shrink-0">
                  <motion.div
                    className="w-7 h-7 rounded-full flex items-center justify-center"
                    style={{
                      background: isCurrent ? `${cfg.color}25` : 'var(--surface)',
                      border:     `2px solid ${isCurrent ? cfg.color : 'var(--border)'}`,
                      boxShadow:  isCurrent ? `0 0 8px ${cfg.color}40` : 'none',
                    }}
                    animate={isCurrent ? { boxShadow: [`0 0 4px ${cfg.color}30`, `0 0 12px ${cfg.color}50`, `0 0 4px ${cfg.color}30`] } : {}}
                    transition={{ duration: 2, repeat: Infinity }}
                  >
                    <cfg.icon className="w-3 h-3" style={{ color: cfg.color }} />
                  </motion.div>
                </div>

                {/* Card */}
                <div
                  className="flex-1 mb-3 rounded-xl p-3 transition-all"
                  style={{
                    background: isCurrent ? `${cfg.color}08` : 'var(--elevated)',
                    border:     `1px solid ${isCurrent ? cfg.color + '30' : 'var(--border)'}`,
                  }}
                >
                  <div className="flex items-center justify-between mb-2">
                    <VersionBadge version={v.version} status={v.status} isCurrent={isCurrent} />
                    <span className="text-[9px] text-[var(--text-4)]">{formatDate(v.uploadedAt)}</span>
                  </div>
                  <p className="text-[10px] text-[var(--text-2)] mb-2">{v.changeSummary}</p>
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="text-[8px] text-[var(--text-4)]">by {v.uploadedBy}</span>
                    <span className="text-[8px] text-[var(--text-4)]">·</span>
                    <span className="text-[8px] text-[var(--text-4)]">{v.chunkCount} chunks</span>
                    <span className="text-[8px] text-[var(--text-4)]">·</span>
                    <span className="text-[8px] text-[var(--text-4)]">{v.fileSize}</span>
                  </div>

                  {/* Diff indicator for non-first versions */}
                  {i < versions.length - 1 && (
                    <div className="flex items-center gap-1 mt-2 pt-2 border-t border-[var(--border)]">
                      <ArrowRight className="w-2.5 h-2.5 text-[var(--text-4)]" />
                      <span className="text-[8px] text-[var(--text-4)]">
                        {Math.abs(v.chunkCount - versions[i + 1].chunkCount)} chunk change from v{versions[i + 1].version}
                      </span>
                    </div>
                  )}
                </div>
              </motion.div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
