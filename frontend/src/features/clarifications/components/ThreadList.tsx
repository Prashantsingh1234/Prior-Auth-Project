import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Bot, User, CheckCircle2, Clock, AlertTriangle,
  Plus, Filter, MessageSquare,
} from 'lucide-react'
import type { ClarificationThread, QuestionSource, ThreadStatus } from '../hooks/useClarificationManager'

// ─── Status config ────────────────────────────────────────────────────────────

const STATUS_CFG: Record<ThreadStatus, { color: string; bg: string; label: string; Icon: React.ElementType }> = {
  pending:   { color: '#f59e0b', bg: '#f59e0b15', label: 'Pending',   Icon: Clock },
  answered:  { color: '#0ea5e9', bg: '#0ea5e915', label: 'Answered',  Icon: CheckCircle2 },
  resolved:  { color: '#10b981', bg: '#10b98115', label: 'Resolved',  Icon: CheckCircle2 },
  escalated: { color: '#ef4444', bg: '#ef444415', label: 'Escalated', Icon: AlertTriangle },
  overdue:   { color: '#ef4444', bg: '#ef444415', label: 'Overdue',   Icon: AlertTriangle },
}

const SOURCE_CFG: Record<QuestionSource, { color: string; label: string; Icon: React.ElementType }> = {
  ai_generated:   { color: '#8b5cf6', label: 'AI',       Icon: Bot },
  reviewer_added: { color: '#0ea5e9', label: 'Reviewer', Icon: User },
  template:       { color: '#6b7280', label: 'Template', Icon: MessageSquare },
}

const PRIORITY_DOT: Record<string, string> = {
  high:   '#ef4444',
  medium: '#f59e0b',
  low:    '#6b7280',
}

// ─── Thread row ───────────────────────────────────────────────────────────────

function ThreadRow({
  thread, isActive, onClick,
}: {
  thread:   ClarificationThread
  isActive: boolean
  onClick:  () => void
}) {
  const statusCfg = STATUS_CFG[thread.status]
  const sourceCfg = SOURCE_CFG[thread.source]
  const SourceIcon = sourceCfg.Icon
  const StatusIcon = statusCfg.Icon
  const lastMsg   = thread.messages[thread.messages.length - 1]

  return (
    <motion.div
      whileHover={{ x: 2 }}
      onClick={onClick}
      className="relative flex items-start gap-2.5 px-3 py-2.5 cursor-pointer rounded-xl transition-all mx-1"
      style={{
        background: isActive ? 'var(--elevated)' : 'transparent',
        border:     `1px solid ${isActive ? 'var(--border)' : 'transparent'}`,
      }}
    >
      {/* Active indicator */}
      {isActive && (
        <motion.div
          layoutId="thread-active"
          className="absolute left-0 top-2 bottom-2 w-0.5 rounded-full"
          style={{ background: sourceCfg.color }}
        />
      )}

      {/* Source icon */}
      <div
        className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
        style={{ background: `${sourceCfg.color}15`, border: `1px solid ${sourceCfg.color}30` }}
      >
        <SourceIcon style={{ color: sourceCfg.color, width: 13, height: 13 }} />
      </div>

      <div className="flex-1 min-w-0">
        {/* Title row */}
        <div className="flex items-center gap-1.5 mb-0.5">
          <div className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: PRIORITY_DOT[thread.priority] }} />
          <span className={`text-[11px] font-semibold truncate ${isActive ? 'text-[var(--text-1)]' : 'text-[var(--text-2)]'}`}>
            {thread.title}
          </span>
          {thread.isUnread && (
            <div className="w-1.5 h-1.5 rounded-full shrink-0 bg-[#0ea5e9]" />
          )}
        </div>

        {/* Last message preview */}
        {lastMsg && (
          <p className="text-[10px] text-[var(--text-4)] truncate leading-snug">
            {lastMsg.authorName}: {lastMsg.content.slice(0, 60)}…
          </p>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between mt-1.5">
          <div
            className="flex items-center gap-1 px-1.5 py-0.5 rounded-md"
            style={{ background: statusCfg.bg }}
          >
            <StatusIcon style={{ color: statusCfg.color, width: 9, height: 9 }} />
            <span className="text-[8px] font-bold uppercase tracking-wide" style={{ color: statusCfg.color }}>
              {statusCfg.label}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {thread.attemptNum > 1 && (
              <span className="text-[8px] font-mono text-[#ef4444]">Attempt {thread.attemptNum}</span>
            )}
            <span className="text-[8px] text-[var(--text-4)]">{thread.daysOpen}d</span>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

// ─── New thread modal ─────────────────────────────────────────────────────────

interface NewThreadFormProps {
  onAdd:   (title: string, question: string, source: QuestionSource) => void
  onClose: () => void
}

function NewThreadForm({ onAdd, onClose }: NewThreadFormProps) {
  const [title,    setTitle]    = useState('')
  const [question, setQuestion] = useState('')
  const [source,   setSource]   = useState<QuestionSource>('reviewer_added')

  function submit() {
    if (!title.trim() || !question.trim()) return
    onAdd(title.trim(), question.trim(), source)
    onClose()
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      className="mx-2 mb-2 rounded-xl overflow-hidden"
      style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
    >
      <div className="px-3 py-2 border-b border-[var(--border)] flex items-center justify-between">
        <span className="text-[11px] font-semibold text-[var(--text-1)]">New Clarification</span>
        <button onClick={onClose} className="text-[var(--text-4)] hover:text-[var(--text-1)] transition-colors text-xs">✕</button>
      </div>
      <div className="p-3 space-y-2">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Topic title…"
          className="w-full text-[11px] rounded-lg px-2.5 py-1.5 outline-none text-[var(--text-1)] placeholder-[var(--text-4)]"
          style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
        />
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Clarification question…"
          rows={3}
          className="w-full text-[11px] rounded-lg px-2.5 py-1.5 outline-none text-[var(--text-1)] placeholder-[var(--text-4)] resize-none"
          style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
        />
        <div className="flex gap-1">
          {(['reviewer_added', 'ai_generated'] as QuestionSource[]).map((s) => (
            <button
              key={s}
              onClick={() => setSource(s)}
              className="flex-1 text-[9px] font-semibold py-1 rounded-lg transition-all"
              style={{
                background: source === s ? `${SOURCE_CFG[s].color}20` : 'var(--surface)',
                color:      source === s ? SOURCE_CFG[s].color : 'var(--text-4)',
                border:     `1px solid ${source === s ? `${SOURCE_CFG[s].color}40` : 'var(--border)'}`,
              }}
            >
              {SOURCE_CFG[s].label}
            </button>
          ))}
        </div>
        <button
          onClick={submit}
          disabled={!title || !question}
          className="w-full text-[11px] font-semibold py-1.5 rounded-lg transition-all"
          style={{
            background: title && question ? '#6366f1' : 'var(--border)',
            color:      title && question ? '#fff' : 'var(--text-4)',
          }}
        >
          Send Question
        </button>
      </div>
    </motion.div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

const FILTER_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'all',      label: 'All' },
  { value: 'pending',  label: 'Pending' },
  { value: 'answered', label: 'Answered' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'overdue',  label: 'Overdue' },
]

interface Props {
  threads:         ClarificationThread[]
  activeThreadId:  string
  onSelectThread:  (id: string) => void
  onAddThread:     (title: string, question: string, source: QuestionSource) => void
}

export function ThreadList({ threads, activeThreadId, onSelectThread, onAddThread }: Props) {
  const [filter,   setFilter]   = useState('all')
  const [showForm, setShowForm] = useState(false)

  const filtered = threads.filter((t) => filter === 'all' || t.status === filter)
  const unread   = threads.filter((t) => t.isUnread).length
  const pending  = threads.filter((t) => t.status === 'pending' || t.status === 'overdue').length

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
        <div className="flex items-center justify-between mb-2">
          <div>
            <span className="text-xs font-bold text-[var(--text-1)]">Clarifications</span>
            <div className="flex items-center gap-1.5 mt-0.5">
              {pending > 0 && (
                <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-[#f59e0b20] text-[#f59e0b]">
                  {pending} open
                </span>
              )}
              {unread > 0 && (
                <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-[#0ea5e920] text-[#0ea5e9]">
                  {unread} new
                </span>
              )}
            </div>
          </div>
          <button
            onClick={() => setShowForm((v) => !v)}
            className="w-7 h-7 rounded-lg flex items-center justify-center transition-all"
            style={{ background: showForm ? '#6366f120' : 'var(--surface)', border: '1px solid var(--border)', color: showForm ? '#6366f1' : 'var(--text-4)' }}
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Filter chips */}
        <div className="flex gap-1 overflow-x-auto">
          {FILTER_OPTIONS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className="text-[8px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-md whitespace-nowrap transition-all"
              style={{
                background: filter === f.value ? 'var(--border)' : 'transparent',
                color:      filter === f.value ? 'var(--text-1)' : 'var(--text-4)',
              }}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* New thread form */}
      <AnimatePresence>
        {showForm && (
          <NewThreadForm
            onAdd={onAddThread}
            onClose={() => setShowForm(false)}
          />
        )}
      </AnimatePresence>

      {/* Thread list */}
      <div className="flex-1 overflow-y-auto py-1.5 space-y-0.5">
        {filtered.length === 0 ? (
          <div className="text-center py-8">
            <Filter className="w-5 h-5 text-[var(--text-4)] mx-auto mb-2" />
            <p className="text-[11px] text-[var(--text-4)]">No threads match filter</p>
          </div>
        ) : (
          filtered.map((thread) => (
            <ThreadRow
              key={thread.id}
              thread={thread}
              isActive={thread.id === activeThreadId}
              onClick={() => onSelectThread(thread.id)}
            />
          ))
        )}
      </div>

      {/* Footer count */}
      <div
        className="px-3 py-2 border-t border-[var(--border)] shrink-0"
        style={{ background: 'var(--elevated)' }}
      >
        <p className="text-[9px] text-[var(--text-4)] text-center">
          {threads.length} threads · {threads.filter((t) => t.status === 'resolved').length} resolved
        </p>
      </div>
    </div>
  )
}
