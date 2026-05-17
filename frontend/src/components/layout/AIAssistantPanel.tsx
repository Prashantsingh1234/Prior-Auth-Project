import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Brain, Send, Sparkles, ChevronRight, RotateCcw, Copy } from 'lucide-react'
import { useUIStore } from '@/store/uiStore'
import { useAuthStore } from '@/store'
import { useFocusTrap } from '@/hooks/useFocusTrap'
import { cn } from '@/lib/utils'

// ─── Types ────────────────────────────────────────────────────────────────────

interface Message {
  id:        string
  role:      'user' | 'assistant'
  content:   string
  timestamp: Date
  thinking?: boolean
}

const QUICK_PROMPTS = [
  'Summarize pending cases',
  "What's the AI accuracy today?",
  'Cases with low confidence',
  'Review policy conflicts',
  'Explain recent denials',
  'Unusual patterns in queue?',
]

const MOCK_RESPONSES: Record<string, string> = {
  default: `Based on the current queue, I'm analyzing 324 pending cases. Here's a quick summary:

**High priority (Emergent):** 12 cases requiring immediate attention
**AI confidence distribution:**
- High (≥90%): 187 cases → ready for quick approval
- Medium (70-89%): 94 cases → need reviewer attention
- Low (<70%): 43 cases → escalated for manual review

**Recommendation:** Focus on the 43 low-confidence cases first — they represent the highest clinical risk.

Would you like me to generate a detailed breakdown?`,

  'Summarize pending cases': `**Pending Queue Summary** (as of now)\n\nTotal pending: **324 cases**\n\n| Priority | Count | Avg Wait |\n|----------|-------|----------|\n| Emergent | 12    | 0.8h     |\n| Urgent   | 67    | 4.2h     |\n| Routine  | 245   | 18.5h    |\n\n**AI has pre-analyzed 97.8%** of pending cases with recommendations ready.\n\nTop pending by specialty:\n1. Oncology — 48 cases\n2. Orthopedics — 41 cases\n3. Cardiology — 38 cases`,

  "What's the AI accuracy today?": `**AI Performance — Today**\n\nOverall accuracy: **94.2%** ↑ +1.3% vs yesterday\n\nBreakdown by decision type:\n- Approve: 96.1% accuracy\n- Deny: 91.8% accuracy\n- Pend: 88.3% accuracy\n- Escalate: 94.7% accuracy\n\nFalse positive rate: 3.2%\nFalse negative rate: 2.6%\n\n**Note:** Accuracy measured against final reviewer decisions on 847 completed cases today.`,

  'Cases with low confidence': `**Low Confidence Cases** (score < 70%)\n\n43 cases flagged for priority human review:\n\n⚠️ **PA-2024-1201** — 58.3% confidence\nMRI Lower Back, John D., missing prior treatment documentation\n\n⚠️ **PA-2024-1198** — 62.1% confidence\nSpinal Surgery, Maria R., policy criteria ambiguous\n\n⚠️ **PA-2024-1195** — 64.7% confidence\nCancer immunotherapy, incomplete clinical notes\n\nShall I assign these to available reviewers?`,
}

function getResponse(content: string): string {
  return MOCK_RESPONSES[content] ?? MOCK_RESPONSES['default']
}

// ─── Thinking dots ────────────────────────────────────────────────────────────

function ThinkingDots() {
  return (
    <div className="flex items-center gap-1 px-1 py-1" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-violet-400"
          animate={{ opacity: [0.3, 1, 0.3], y: [0, -3, 0] }}
          transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.15 }}
        />
      ))}
    </div>
  )
}

// ─── Message bubble ───────────────────────────────────────────────────────────

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user'
  const [copied, setCopied] = useState(false)

  function copyText() {
    navigator.clipboard.writeText(msg.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={cn('flex gap-2.5 group', isUser && 'flex-row-reverse')}
    >
      {/* Avatar */}
      <div
        aria-hidden="true"
        className={cn(
          'w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5',
          isUser
            ? 'bg-gradient-to-br from-cyan-500 to-blue-600'
            : 'bg-gradient-to-br from-violet-500 to-purple-600',
        )}
      >
        {isUser
          ? <span className="text-[10px] text-white font-bold">U</span>
          : <Brain className="w-3 h-3 text-white" />
        }
      </div>

      {/* Content */}
      <div className={cn('flex-1 max-w-[85%]', isUser && 'flex flex-col items-end')}>
        {msg.thinking ? (
          <div
            className="px-3 py-2 rounded-2xl"
            style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
          >
            <ThinkingDots />
            <span className="sr-only">AI is thinking…</span>
          </div>
        ) : (
          <div
            className={cn(
              'relative px-3 py-2.5 rounded-2xl text-sm leading-relaxed',
              isUser ? 'text-white' : 'text-[var(--text-1)]',
            )}
            style={
              isUser
                ? { background: 'linear-gradient(135deg, rgba(14,165,233,0.9), rgba(59,130,246,0.9))' }
                : { background: 'var(--elevated)', border: '1px solid var(--border)' }
            }
          >
            {msg.content.split('\n').map((line, i) => {
              if (line.startsWith('**') && line.endsWith('**')) {
                return <p key={i} className="font-bold mb-1">{line.slice(2, -2)}</p>
              }
              if (line.startsWith('- ') || line.startsWith('⚠️ ') || line.startsWith('1. ') || line.startsWith('2. ') || line.startsWith('3. ')) {
                return <p key={i} className="mb-0.5">{line}</p>
              }
              return <p key={i} className={line ? 'mb-1' : 'mb-2'}>{line}</p>
            })}

            {!isUser && (
              <button
                onClick={copyText}
                aria-label={copied ? 'Copied!' : 'Copy message'}
                className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity p-1 rounded hover:bg-[var(--border)]"
              >
                <Copy className="w-3 h-3 text-[var(--text-3)]" aria-hidden="true" />
              </button>
            )}
          </div>
        )}
        <span className="text-[10px] text-[var(--text-4)] mt-1 px-1" aria-label={`Sent at ${msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}>
          {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          {copied && <span className="ml-2 text-cyan-400" aria-live="polite">Copied!</span>}
        </span>
      </div>
    </motion.div>
  )
}

// ─── Main panel ───────────────────────────────────────────────────────────────

export function AIAssistantPanel() {
  const { aiPanelOpen, setAIPanelOpen } = useUIStore()
  const user = useAuthStore((s) => s.user)

  const [messages, setMessages] = useState<Message[]>([
    {
      id:        'welcome',
      role:      'assistant',
      content:   `Hi ${user?.name?.split(' ')[0] ?? 'there'}! I'm your PA Review AI Assistant. I can help you:\n\n- Analyze pending cases and identify priorities\n- Explain AI decisions and confidence scores\n- Surface policy conflicts and edge cases\n- Generate queue summaries and reports\n\nWhat would you like to know?`,
      timestamp: new Date(),
    },
  ])
  const [input, setInput]           = useState('')
  const [isThinking, setIsThinking] = useState(false)
  const bottomRef                   = useRef<HTMLDivElement>(null)
  const inputRef                    = useRef<HTMLTextAreaElement>(null)
  const panelRef                    = useRef<HTMLDivElement>(null)

  useFocusTrap(panelRef, aiPanelOpen)

  useEffect(() => {
    if (aiPanelOpen) {
      setTimeout(() => inputRef.current?.focus(), 200)
    }
  }, [aiPanelOpen])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function sendMessage(content: string) {
    if (!content.trim() || isThinking) return

    const userMsg: Message    = { id: crypto.randomUUID(), role: 'user',      content,   timestamp: new Date() }
    const thinkingMsg: Message = { id: 'thinking',         role: 'assistant', content: '', timestamp: new Date(), thinking: true }

    setMessages((m) => [...m, userMsg, thinkingMsg])
    setInput('')
    setIsThinking(true)

    await new Promise((r) => setTimeout(r, 1200 + Math.random() * 800))

    const response = getResponse(content)
    setMessages((m) => [
      ...m.filter((x) => x.id !== 'thinking'),
      { id: crypto.randomUUID(), role: 'assistant', content: response, timestamp: new Date() },
    ])
    setIsThinking(false)
  }

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  return (
    <AnimatePresence>
      {aiPanelOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.25 }}
            exit={{ opacity: 0 }}
            onClick={() => setAIPanelOpen(false)}
            className="fixed inset-0 z-[38] bg-black"
            aria-hidden="true"
          />

          {/* Panel */}
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="ai-panel-title"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 380, damping: 38 }}
            className="fixed right-0 top-0 h-full w-96 z-[39] flex flex-col shadow-card-xl"
            style={{ background: 'var(--surface)', borderLeft: '1px solid var(--border)' }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-4 h-14 border-b border-[var(--border)] flex-shrink-0"
              style={{ background: 'linear-gradient(90deg, rgba(139,92,246,0.08), transparent)' }}
            >
              <div className="flex items-center gap-2.5">
                <motion.div
                  className="w-7 h-7 rounded-lg flex items-center justify-center"
                  style={{ background: 'rgba(139,92,246,0.2)', border: '1px solid rgba(139,92,246,0.3)' }}
                  animate={{ boxShadow: ['0 0 0 0 rgba(139,92,246,0)', '0 0 12px 2px rgba(139,92,246,0.3)', '0 0 0 0 rgba(139,92,246,0)'] }}
                  transition={{ duration: 2.5, repeat: Infinity }}
                  aria-hidden="true"
                >
                  <Brain className="w-3.5 h-3.5 text-violet-400" />
                </motion.div>
                <div>
                  <p id="ai-panel-title" className="text-sm font-semibold text-[var(--text-1)]">AI Assistant</p>
                  <div className="flex items-center gap-1.5">
                    <motion.div className="w-1.5 h-1.5 rounded-full bg-emerald-400" animate={{ opacity: [1, 0.4, 1] }} transition={{ duration: 1.5, repeat: Infinity }} aria-hidden="true" />
                    <span className="text-[10px] text-[var(--text-4)]">claude-sonnet-4-6 · Online</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setMessages([messages[0]])}
                  aria-label="Clear conversation"
                  className="p-1.5 rounded-lg text-[var(--text-3)] hover:text-[var(--text-2)] hover:bg-[var(--elevated)] transition-colors"
                >
                  <RotateCcw className="w-3.5 h-3.5" aria-hidden="true" />
                </button>
                <button
                  onClick={() => setAIPanelOpen(false)}
                  aria-label="Close AI Assistant"
                  className="p-1.5 rounded-lg text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-[var(--elevated)] transition-colors"
                >
                  <X className="w-4 h-4" aria-hidden="true" />
                </button>
              </div>
            </div>

            {/* Messages — role="log" announces new messages to screen readers */}
            <div
              role="log"
              aria-label="Conversation"
              aria-live="polite"
              aria-relevant="additions"
              className="flex-1 overflow-y-auto p-4 space-y-4"
            >
              <AnimatePresence initial={false}>
                {messages.map((msg) => (
                  <MessageBubble key={msg.id} msg={msg} />
                ))}
              </AnimatePresence>
              <div ref={bottomRef} aria-hidden="true" />
            </div>

            {/* Quick prompts */}
            <div className="px-4 pb-3 flex-shrink-0">
              <div className="flex items-center gap-2 mb-2" aria-hidden="true">
                <Sparkles className="w-3 h-3 text-[var(--text-4)]" />
                <span className="text-[10px] text-[var(--text-4)] uppercase tracking-widest">Quick prompts</span>
              </div>
              <div className="flex flex-wrap gap-1.5" role="group" aria-label="Quick prompt suggestions">
                {QUICK_PROMPTS.map((p) => (
                  <button
                    key={p}
                    onClick={() => sendMessage(p)}
                    disabled={isThinking}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs text-[var(--text-2)] border border-[var(--border)] hover:border-violet-500/40 hover:text-violet-400 hover:bg-violet-500/5 transition-all disabled:opacity-40"
                  >
                    <ChevronRight className="w-2.5 h-2.5 opacity-50" aria-hidden="true" />
                    {p}
                  </button>
                ))}
              </div>
            </div>

            {/* Input */}
            <div className="px-4 pb-4 flex-shrink-0 border-t border-[var(--border)] pt-3">
              <div
                className="flex items-end gap-2 rounded-xl px-3 py-2"
                style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
              >
                <label htmlFor="ai-input" className="sr-only">Ask AI Assistant</label>
                <textarea
                  ref={inputRef}
                  id="ai-input"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKey}
                  placeholder="Ask about cases, policies, metrics…"
                  rows={1}
                  disabled={isThinking}
                  aria-label="Message the AI Assistant"
                  aria-describedby="ai-input-hint"
                  className="flex-1 bg-transparent text-sm text-[var(--text-1)] placeholder:text-[var(--text-4)] outline-none resize-none max-h-28 overflow-y-auto leading-relaxed"
                  style={{ minHeight: 24 }}
                />
                <motion.button
                  onClick={() => sendMessage(input)}
                  disabled={!input.trim() || isThinking}
                  aria-label="Send message"
                  aria-busy={isThinking}
                  whileHover={!isThinking ? { scale: 1.05 } : {}}
                  whileTap={{ scale: 0.95 }}
                  className={cn(
                    'w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 transition-all',
                    input.trim() && !isThinking
                      ? 'bg-violet-600 text-white shadow-[0_0_10px_rgba(139,92,246,0.4)]'
                      : 'bg-[var(--border)] text-[var(--text-4)]',
                  )}
                >
                  <Send className="w-3.5 h-3.5" aria-hidden="true" />
                </motion.button>
              </div>
              <p id="ai-input-hint" className="text-[10px] text-[var(--text-4)] text-center mt-2">
                Enter to send · Shift+Enter for new line
              </p>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
