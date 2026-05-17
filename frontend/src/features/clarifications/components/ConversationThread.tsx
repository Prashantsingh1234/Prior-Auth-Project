import { useRef, useEffect, useState, KeyboardEvent } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Bot, User, Building2, AlertTriangle, CheckCircle2, Clock,
  Send, Paperclip, MoreHorizontal, RotateCcw, Sparkles,
} from 'lucide-react'
import type {
  ClarificationThread, Message, MessageAuthor, AIChip,
} from '../hooks/useClarificationManager'
import { AI_CHIPS } from '../hooks/useClarificationManager'

// ─── Author config ────────────────────────────────────────────────────────────

const AUTHOR_CFG: Record<MessageAuthor, {
  color: string; bg: string; side: 'left' | 'right' | 'center'
  Icon: React.ElementType; bgBubble: string; textColor: string
}> = {
  ai:       { color: '#8b5cf6', bg: '#8b5cf615', side: 'left',   Icon: Bot,       bgBubble: '#8b5cf618', textColor: 'var(--text-1)' },
  reviewer: { color: '#6366f1', bg: '#6366f115', side: 'right',  Icon: User,      bgBubble: '#6366f1',   textColor: '#fff' },
  provider: { color: '#10b981', bg: '#10b98115', side: 'left',   Icon: Building2, bgBubble: '#10b98115', textColor: 'var(--text-1)' },
  system:   { color: '#6b7280', bg: '#6b728015', side: 'center', Icon: AlertTriangle, bgBubble: 'transparent', textColor: 'var(--text-4)' },
}

function formatTime(date: Date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function formatDay(date: Date) {
  const now   = new Date()
  const diff  = Math.floor((now.getTime() - date.getTime()) / 86400000)
  if (diff === 0) return 'Today'
  if (diff === 1) return 'Yesterday'
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

// ─── Typing indicator ─────────────────────────────────────────────────────────

function TypingBubble() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 4 }}
      className="flex items-end gap-2 mb-3"
    >
      <div className="w-6 h-6 rounded-lg flex items-center justify-center shrink-0" style={{ background: '#10b98115' }}>
        <Building2 style={{ color: '#10b981', width: 12, height: 12 }} />
      </div>
      <div className="px-3 py-2.5 rounded-2xl rounded-bl-sm" style={{ background: '#10b98115', border: '1px solid #10b98125' }}>
        <div className="flex items-center gap-1">
          {[0, 1, 2].map((i) => (
            <motion.div
              key={i}
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: '#10b981' }}
              animate={{ y: [0, -4, 0], opacity: [0.4, 1, 0.4] }}
              transition={{ duration: 0.7, repeat: Infinity, delay: i * 0.15, ease: 'easeInOut' }}
            />
          ))}
        </div>
      </div>
      <span className="text-[9px] text-[var(--text-4)] mb-1">Dr. Sarah Chen is typing…</span>
    </motion.div>
  )
}

// ─── Message bubble ───────────────────────────────────────────────────────────

interface BubbleProps {
  msg:       Message
  showHead:  boolean
  isLast:    boolean
}

function MessageBubble({ msg, showHead, isLast }: BubbleProps) {
  const cfg = AUTHOR_CFG[msg.author]

  if (msg.author === 'system') {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex items-center gap-2 my-2 px-4"
      >
        <div className="flex-1 h-px bg-[var(--border)]" />
        <span className="text-[9px] text-[var(--text-4)] whitespace-nowrap px-2">{msg.content}</span>
        <div className="flex-1 h-px bg-[var(--border)]" />
      </motion.div>
    )
  }

  const isRight = cfg.side === 'right'

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={`flex items-end gap-2 mb-1 ${isRight ? 'flex-row-reverse' : ''}`}
    >
      {/* Avatar */}
      {showHead ? (
        <div
          className="w-6 h-6 rounded-lg flex items-center justify-center shrink-0 mb-0.5"
          style={{ background: cfg.bg, border: `1px solid ${cfg.color}30` }}
        >
          <cfg.Icon style={{ color: cfg.color, width: 12, height: 12 }} />
        </div>
      ) : (
        <div className="w-6 shrink-0" />
      )}

      <div className={`flex flex-col max-w-[72%] ${isRight ? 'items-end' : 'items-start'}`}>
        {/* Author name + time */}
        {showHead && (
          <div className={`flex items-center gap-1.5 mb-1 ${isRight ? 'flex-row-reverse' : ''}`}>
            <span className="text-[10px] font-semibold" style={{ color: cfg.color }}>{msg.authorName}</span>
            <span className="text-[9px] text-[var(--text-4)]">{formatTime(msg.timestamp)}</span>
          </div>
        )}

        {/* Bubble */}
        <div
          className="px-3 py-2 rounded-2xl leading-relaxed text-[12px]"
          style={{
            background:  cfg.bgBubble,
            color:       cfg.textColor,
            border:      isRight ? 'none' : `1px solid ${cfg.color}20`,
            borderRadius: isRight
              ? '18px 18px 4px 18px'
              : '18px 18px 18px 4px',
            boxShadow:   isRight ? '0 1px 8px rgba(99,102,241,0.25)' : 'none',
          }}
        >
          {/* Preserve newlines */}
          {msg.content.split('\n').map((line, i) => (
            <span key={i}>{line}{i < msg.content.split('\n').length - 1 && <br />}</span>
          ))}
        </div>

        {/* Attachments */}
        {msg.attachments && msg.attachments.length > 0 && (
          <div className={`flex flex-wrap gap-1 mt-1 ${isRight ? 'justify-end' : ''}`}>
            {msg.attachments.map((a) => (
              <div
                key={a}
                className="flex items-center gap-1 px-2 py-0.5 rounded-lg text-[9px] font-medium cursor-pointer hover:opacity-80 transition-opacity"
                style={{ background: `${cfg.color}15`, color: cfg.color, border: `1px solid ${cfg.color}25` }}
              >
                <Paperclip className="w-2.5 h-2.5" />
                {a}
              </div>
            ))}
          </div>
        )}

        {/* Read receipt on last reviewer message */}
        {isRight && isLast && (
          <span className="text-[8px] text-[var(--text-4)] mt-0.5">Delivered</span>
        )}
      </div>
    </motion.div>
  )
}

// ─── AI chip bar ──────────────────────────────────────────────────────────────

interface ChipBarProps {
  onApply: (chip: AIChip) => void
}

function AIChipBar({ onApply }: ChipBarProps) {
  const [expanded, setExpanded] = useState(false)
  const visible = expanded ? AI_CHIPS : AI_CHIPS.slice(0, 4)

  return (
    <div
      className="px-3 py-2 border-t border-[var(--border)]"
      style={{ background: 'var(--elevated)' }}
    >
      <div className="flex items-center gap-1.5 mb-1.5">
        <Sparkles className="w-3 h-3 text-[#8b5cf6]" />
        <span className="text-[9px] font-bold uppercase tracking-wide text-[var(--text-4)]">AI Suggestions</span>
        <button
          onClick={() => setExpanded((v) => !v)}
          className="ml-auto text-[9px] text-[var(--text-4)] hover:text-[var(--text-2)] transition-colors"
        >
          {expanded ? 'Less' : 'More'}
        </button>
      </div>
      <div className="flex flex-wrap gap-1">
        {visible.map((chip) => (
          <motion.button
            key={chip.id}
            whileHover={{ y: -1, scale: 1.02 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => onApply(chip)}
            className="text-[9px] font-semibold px-2 py-1 rounded-lg transition-all"
            style={{
              background: `${chip.color}12`,
              color:      chip.color,
              border:     `1px solid ${chip.color}30`,
            }}
          >
            {chip.label}
          </motion.button>
        ))}
      </div>
    </div>
  )
}

// ─── Composer ─────────────────────────────────────────────────────────────────

interface ComposerProps {
  value:       string
  onChange:    (v: string) => void
  onSend:      (content: string, author: MessageAuthor) => void
  isSending:   boolean
  threadStatus: string
  onApplyChip: (chip: AIChip) => void
}

function Composer({ value, onChange, onSend, isSending, threadStatus, onApplyChip }: ComposerProps) {
  const [sendAs, setSendAs] = useState<MessageAuthor>('reviewer')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const isResolved = threadStatus === 'resolved'

  function handleKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (value.trim() && !isSending) {
        onSend(value, sendAs)
        onChange('')
      }
    }
  }

  const SEND_AS_OPTIONS: Array<{ value: MessageAuthor; label: string; color: string }> = [
    { value: 'reviewer', label: 'Reviewer',  color: '#6366f1' },
    { value: 'ai',       label: 'AI System', color: '#8b5cf6' },
    { value: 'provider', label: 'Provider',  color: '#10b981' },
  ]

  return (
    <div>
      {/* AI chips */}
      <AIChipBar onApply={(chip) => { onApplyChip(chip); textareaRef.current?.focus() }} />

      {/* Composer box */}
      <div className="p-3" style={{ background: 'var(--surface)' }}>
        {isResolved ? (
          <div
            className="rounded-xl px-4 py-3 text-center text-[11px] text-[var(--text-4)]"
            style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
          >
            <CheckCircle2 className="w-4 h-4 text-[#10b981] mx-auto mb-1" />
            Thread resolved — no further messages
          </div>
        ) : (
          <div
            className="rounded-xl overflow-hidden"
            style={{ border: '1px solid var(--border)', background: 'var(--elevated)' }}
          >
            {/* Send-as selector */}
            <div className="flex items-center gap-1 px-3 pt-2 pb-1">
              <span className="text-[9px] text-[var(--text-4)] mr-1">Send as</span>
              {SEND_AS_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setSendAs(opt.value)}
                  className="text-[9px] font-semibold px-2 py-0.5 rounded-lg transition-all"
                  style={{
                    background: sendAs === opt.value ? `${opt.color}20` : 'transparent',
                    color:      sendAs === opt.value ? opt.color : 'var(--text-4)',
                    border:     `1px solid ${sendAs === opt.value ? `${opt.color}40` : 'transparent'}`,
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Type a message… (⏎ send, ⇧⏎ newline)"
              rows={3}
              className="w-full px-3 py-2 text-[12px] outline-none resize-none text-[var(--text-1)] placeholder-[var(--text-4)] bg-transparent"
            />

            <div className="flex items-center justify-between px-3 pb-2">
              <span className="text-[9px] text-[var(--text-4)]">{value.length > 0 ? `${value.length} chars` : 'Shift+Enter for new line'}</span>
              <button
                onClick={() => { if (value.trim()) { onSend(value, sendAs); onChange('') } }}
                disabled={!value.trim() || isSending}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-all"
                style={{
                  background: value.trim() ? '#6366f1' : 'var(--border)',
                  color:      value.trim() ? '#fff' : 'var(--text-4)',
                }}
              >
                {isSending ? (
                  <motion.div animate={{ rotate: 360 }} transition={{ duration: 0.8, repeat: Infinity, ease: 'linear' }}>
                    <RotateCcw className="w-3 h-3" />
                  </motion.div>
                ) : (
                  <Send className="w-3 h-3" />
                )}
                Send
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  thread:          ClarificationThread
  composerText:    string
  isProviderTyping: boolean
  isSending:       boolean
  onSend:          (content: string, author: MessageAuthor) => void
  onComposerChange: (v: string) => void
  onResolve:       (id: string) => void
  onApplyChip:     (chip: AIChip) => void
}

export function ConversationThread({
  thread, composerText, isProviderTyping, isSending,
  onSend, onComposerChange, onResolve, onApplyChip,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [thread.messages, isProviderTyping])

  // Group messages by day for date dividers
  const grouped: Array<{ day: string; messages: Message[] }> = []
  for (const msg of thread.messages) {
    const day = formatDay(msg.timestamp)
    const last = grouped[grouped.length - 1]
    if (last && last.day === day) last.messages.push(msg)
    else grouped.push({ day, messages: [msg] })
  }

  const statusCfg: Record<string, { color: string; label: string }> = {
    pending:   { color: '#f59e0b', label: 'Awaiting Response' },
    answered:  { color: '#0ea5e9', label: 'Response Received' },
    resolved:  { color: '#10b981', label: 'Resolved' },
    escalated: { color: '#ef4444', label: 'Escalated' },
    overdue:   { color: '#ef4444', label: 'Overdue — No Response' },
  }
  const sc = statusCfg[thread.status] ?? { color: '#6b7280', label: thread.status }

  return (
    <div className="flex flex-col h-full">
      {/* Thread header */}
      <div
        className="px-4 py-3 border-b border-[var(--border)] shrink-0"
        style={{ background: 'var(--elevated)' }}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-sm font-bold text-[var(--text-1)] leading-tight">{thread.title}</h2>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <span
                className="text-[9px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-md"
                style={{ background: `${sc.color}15`, color: sc.color }}
              >
                {sc.label}
              </span>
              {thread.policyRef && (
                <span className="text-[9px] font-mono text-[var(--text-4)]">{thread.policyRef}</span>
              )}
              <span className="text-[9px] text-[var(--text-4)]">{thread.attemptNum} attempt{thread.attemptNum > 1 ? 's' : ''}</span>
              <span className="text-[9px] text-[var(--text-4)]">{thread.messages.length} messages</span>
            </div>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            {thread.status !== 'resolved' && (
              <button
                onClick={() => onResolve(thread.id)}
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[10px] font-semibold transition-all"
                style={{ background: '#10b98115', color: '#10b981', border: '1px solid #10b98130' }}
              >
                <CheckCircle2 className="w-3 h-3" />
                Resolve
              </button>
            )}
            <button className="w-7 h-7 rounded-lg flex items-center justify-center text-[var(--text-4)] hover:text-[var(--text-1)] hover:bg-[var(--surface)] transition-all">
              <MoreHorizontal className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Overdue banner */}
        {(thread.status === 'overdue' || thread.attemptNum >= 2) && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="mt-2 px-2.5 py-1.5 rounded-lg flex items-center gap-1.5"
            style={{ background: '#ef444412', border: '1px solid #ef444430' }}
          >
            <AlertTriangle className="w-3 h-3 text-[#ef4444] shrink-0" />
            <span className="text-[10px] text-[#ef4444] font-medium">
              {thread.attemptNum >= 2
                ? `Attempt ${thread.attemptNum} of 3 — escalation will be triggered if no response received within 48 hours.`
                : 'Provider has not responded. A reminder has been sent automatically.'}
            </span>
          </motion.div>
        )}
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-0.5">
        {grouped.map((group) => (
          <div key={group.day}>
            {/* Day divider */}
            <div className="flex items-center gap-2 my-3">
              <div className="flex-1 h-px bg-[var(--border)]" />
              <span className="text-[9px] font-semibold text-[var(--text-4)] px-2">{group.day}</span>
              <div className="flex-1 h-px bg-[var(--border)]" />
            </div>

            {group.messages.map((msg, i) => {
              const prev = group.messages[i - 1]
              const showHead = !prev || prev.author !== msg.author || prev.author === 'system'
              const isLast   = i === group.messages.length - 1
              return (
                <MessageBubble key={msg.id} msg={msg} showHead={showHead} isLast={isLast} />
              )
            })}
          </div>
        ))}

        {/* Typing indicator */}
        <AnimatePresence>
          {isProviderTyping && <TypingBubble key="typing" />}
        </AnimatePresence>

        {/* Awaiting banner */}
        {(thread.status === 'pending' || thread.status === 'overdue') && !isProviderTyping && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-2 px-3 py-2 rounded-xl mt-2"
            style={{ background: '#f59e0b08', border: '1px dashed #f59e0b40' }}
          >
            <Clock className="w-3.5 h-3.5 text-[#f59e0b] shrink-0" />
            <span className="text-[10px] text-[#f59e0b]">
              Awaiting provider response · {thread.daysOpen} day{thread.daysOpen !== 1 ? 's' : ''} open
            </span>
          </motion.div>
        )}
      </div>

      {/* Composer */}
      <div className="shrink-0 border-t border-[var(--border)]">
        <Composer
          value={composerText}
          onChange={onComposerChange}
          onSend={onSend}
          isSending={isSending}
          threadStatus={thread.status}
          onApplyChip={onApplyChip}
        />
      </div>
    </div>
  )
}
