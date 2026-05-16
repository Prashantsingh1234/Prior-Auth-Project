import { motion } from 'framer-motion'
import { MessageSquare, Bot, User, Clock, CheckCircle2, AlertCircle } from 'lucide-react'
import { formatRelative } from '@/lib/utils'
import { cn } from '@/lib/utils'

interface Clarification {
  id: string
  question: string
  askedAt: string
  askedBy: 'AI' | 'REVIEWER'
  response?: string
  respondedAt?: string
  status: 'PENDING' | 'ANSWERED'
}

const MOCK_CLARIFICATIONS: Clarification[] = [
  {
    id: 'cl1',
    question: 'Please provide documentation of pre-operative cardiac evaluation or cardiology clearance performed within the last 90 days.',
    askedAt: new Date(Date.now() - 7200000).toISOString(),
    askedBy: 'AI',
    response: 'Pre-op cardiac clearance from Dr. Emily Walsh (Cardiologist) was performed on 2024-01-12. Documentation attached as supplement to original submission.',
    respondedAt: new Date(Date.now() - 5400000).toISOString(),
    status: 'ANSWERED',
  },
  {
    id: 'cl2',
    question: 'Can you confirm that viscosupplementation was performed with a recognized agent (e.g., Synvisc, Hyalgan) per policy §4.2.3b?',
    askedAt: new Date(Date.now() - 3600000).toISOString(),
    askedBy: 'REVIEWER',
    status: 'PENDING',
  },
]

export function ClarificationResponses() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-[var(--text-1)]">Clarification Requests</h3>
        <span className="chip bg-amber-500/10 text-amber-400 border-amber-500/20">
          1 pending
        </span>
      </div>

      {MOCK_CLARIFICATIONS.length === 0 ? (
        <div className="text-center py-10 text-[var(--text-3)] text-sm">
          No clarification requests
        </div>
      ) : (
        <div className="space-y-4">
          {MOCK_CLARIFICATIONS.map((c, i) => (
            <motion.div
              key={c.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08 }}
              className="rounded-xl border border-[var(--border)] overflow-hidden"
            >
              {/* Question */}
              <div className="p-4 bg-[var(--elevated)]">
                <div className="flex items-start gap-3">
                  <div className={cn(
                    'w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0',
                    c.askedBy === 'AI' ? 'bg-violet-500/20' : 'bg-brand-500/20'
                  )}>
                    {c.askedBy === 'AI'
                      ? <Bot className="w-4 h-4 text-violet-400" />
                      : <User className="w-4 h-4 text-brand-400" />
                    }
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-semibold text-[var(--text-2)]">
                        {c.askedBy === 'AI' ? 'AI System' : 'Reviewer'}
                      </span>
                      <span className="text-xs text-[var(--text-3)]">{formatRelative(c.askedAt)}</span>
                    </div>
                    <p className="text-sm text-[var(--text-1)] leading-relaxed">{c.question}</p>
                  </div>
                </div>
              </div>

              {/* Response or pending indicator */}
              {c.status === 'ANSWERED' && c.response ? (
                <div className="p-4 border-t border-[var(--border)]">
                  <div className="flex items-start gap-3">
                    <div className="w-7 h-7 rounded-full bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-semibold text-emerald-400">Provider Response</span>
                        {c.respondedAt && (
                          <span className="text-xs text-[var(--text-3)]">{formatRelative(c.respondedAt)}</span>
                        )}
                      </div>
                      <p className="text-sm text-[var(--text-2)] leading-relaxed">{c.response}</p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="px-4 py-3 border-t border-[var(--border)] flex items-center gap-2 text-xs text-amber-400">
                  <Clock className="w-3.5 h-3.5" />
                  Awaiting provider response
                </div>
              )}
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}