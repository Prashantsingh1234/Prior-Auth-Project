import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ClipboardList, BookOpen, Users, FileText, MessageSquare, BarChart3 } from 'lucide-react'
import { CasesTable }          from './tables/CasesTable'
import { PoliciesTable }       from './tables/PoliciesTable'
import { ReviewersTable }      from './tables/ReviewersTable'
import { AuditTable }          from './tables/AuditTable'
import { ClarificationsTable } from './tables/ClarificationsTable'
import { MetricsTable }        from './tables/MetricsTable'

// ─── Tab config ───────────────────────────────────────────────────────────────

type TableTab = 'cases' | 'policies' | 'reviewers' | 'audit' | 'clarifications' | 'metrics'

const TABS: Array<{
  id: TableTab; label: string; icon: React.ElementType
  description: string; count: number; color: string
}> = [
  { id: 'cases',          label: 'Cases',          icon: ClipboardList, description: '250 authorization requests', count: 250, color: '#0ea5e9' },
  { id: 'policies',       label: 'Policies',       icon: BookOpen,      description: '40 clinical policy docs',   count: 40,  color: '#6366f1' },
  { id: 'reviewers',      label: 'Reviewers',      icon: Users,         description: '35 reviewer accounts',     count: 35,  color: '#10b981' },
  { id: 'audit',          label: 'Audit Log',      icon: FileText,      description: '500 immutable events',     count: 500, color: '#8b5cf6' },
  { id: 'clarifications', label: 'Clarifications', icon: MessageSquare, description: '120 clarification requests', count: 120, color: '#f59e0b' },
  { id: 'metrics',        label: 'Metrics',        icon: BarChart3,     description: '200 AI performance rows',  count: 200, color: '#ef4444' },
]

// ─── Page ──────────────────────────────────────────────────────────────────────

export function TablesPage() {
  const [tab, setTab] = useState<TableTab>('cases')
  const current = TABS.find((t) => t.id === tab)!

  return (
    <div className="h-full flex flex-col overflow-hidden" style={{ background: 'var(--bg)' }}>

      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b flex-shrink-0"
           style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
        <div>
          <h1 className="text-base font-bold text-[var(--text-1)]">Enterprise Data Tables</h1>
          <p className="text-[10px] text-[var(--text-4)] mt-0.5">
            Virtualized · Sticky headers · Advanced filters · Saved views · Row expansion · CSV export
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] px-2.5 py-1 rounded-full font-semibold"
                style={{ background: `${current.color}15`, color: current.color }}>
            {current.count.toLocaleString()} rows
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-end gap-0 px-6 border-b flex-shrink-0"
           style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
        {TABS.map((t) => {
          const Icon    = t.icon
          const active  = t.id === tab
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className="flex items-center gap-1.5 px-4 py-3 text-xs font-medium transition-all relative"
              style={{
                color:      active ? t.color : 'var(--text-3)',
                borderBottom: active ? `2px solid ${t.color}` : '2px solid transparent',
              }}
            >
              <Icon className="w-3.5 h-3.5 flex-shrink-0" />
              {t.label}
              {active && (
                <motion.span
                  layoutId="tab-count"
                  className="px-1.5 py-0.5 rounded-full text-[9px] font-bold"
                  style={{ background: `${t.color}20`, color: t.color }}
                >
                  {t.count}
                </motion.span>
              )}
            </button>
          )
        })}
      </div>

      {/* Table content */}
      <div className="flex-1 overflow-hidden p-4">
        <AnimatePresence mode="wait">
          <motion.div
            key={tab}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.12 }}
            className="h-full"
          >
            {tab === 'cases'          && <CasesTable />}
            {tab === 'policies'       && <PoliciesTable />}
            {tab === 'reviewers'      && <ReviewersTable />}
            {tab === 'audit'          && <AuditTable />}
            {tab === 'clarifications' && <ClarificationsTable />}
            {tab === 'metrics'        && <MetricsTable />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}
