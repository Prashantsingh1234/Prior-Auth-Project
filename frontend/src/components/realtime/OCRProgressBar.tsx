import { motion, AnimatePresence } from 'framer-motion'
import { FileText, CheckCircle2, XCircle, Loader2, Eye, Upload, Cpu } from 'lucide-react'
import type { OCRProgressPayload } from '@/services/realtime.service'

// ─── Stage config ─────────────────────────────────────────────────────────────

const STAGE_CFG = {
  uploading:   { icon: Upload,      color: '#0ea5e9', label: 'Uploading'   },
  queued:      { icon: Loader2,     color: '#6b7280', label: 'Queued'      },
  extracting:  { icon: Eye,         color: '#8b5cf6', label: 'Extracting'  },
  validating:  { icon: Cpu,         color: '#f59e0b', label: 'Validating'  },
  complete:    { icon: CheckCircle2, color: '#10b981', label: 'Complete'   },
  failed:      { icon: XCircle,     color: '#ef4444', label: 'Failed'      },
}

// ─── Single document progress ─────────────────────────────────────────────────

interface OCRDocProgressProps {
  doc: OCRProgressPayload
}

export function OCRDocProgress({ doc }: OCRDocProgressProps) {
  const cfg  = STAGE_CFG[doc.stage]
  const Icon = cfg.icon
  const pct  = doc.stage === 'complete' ? 100 : doc.stage === 'failed' ? 100 : doc.progress

  return (
    <div className="rounded-xl p-3" style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
      <div className="flex items-center gap-2 mb-2">
        <div className="w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0"
             style={{ background: `${cfg.color}15` }}>
          <motion.div
            animate={doc.stage === 'extracting' ? { rotate: 360 } : {}}
            transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
          >
            <Icon className="w-3 h-3" style={{ color: cfg.color }} />
          </motion.div>
        </div>

        <div className="flex-1 min-w-0">
          <p className="text-[10px] font-medium text-[var(--text-2)] truncate">{doc.filename}</p>
          <div className="flex items-center gap-2">
            <span className="text-[8px] font-bold uppercase tracking-wide" style={{ color: cfg.color }}>
              {cfg.label}
            </span>
            {doc.totalPages > 0 && (
              <span className="text-[8px] text-[var(--text-4)]">
                {doc.pagesDone}/{doc.totalPages} pages
              </span>
            )}
            {doc.confidence !== undefined && doc.stage === 'complete' && (
              <span className="text-[8px] text-emerald-400 ml-auto">
                {(doc.confidence * 100).toFixed(0)}% conf.
              </span>
            )}
          </div>
        </div>

        <span className="text-[9px] font-mono text-[var(--text-3)] shrink-0">
          {pct}%
        </span>
      </div>

      {/* Progress track */}
      <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--surface)' }}>
        <motion.div
          className="h-full rounded-full"
          style={{ background: doc.stage === 'failed' ? '#ef4444' : `linear-gradient(90deg, ${cfg.color}80, ${cfg.color})` }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ ease: 'easeOut', duration: 0.4 }}
        />
      </div>

      {doc.error && (
        <p className="mt-1.5 text-[9px] text-red-400">{doc.error}</p>
      )}
    </div>
  )
}

// ─── Multi-document OCR panel ─────────────────────────────────────────────────

interface OCRProgressPanelProps {
  documents: OCRProgressPayload[]
  title?:    string
}

export function OCRProgressPanel({ documents, title = 'Document Processing' }: OCRProgressPanelProps) {
  const active = documents.filter((d) => d.stage !== 'complete')
  const done   = documents.filter((d) => d.stage === 'complete')
  const failed = documents.filter((d) => d.stage === 'failed')

  if (documents.length === 0) return null

  return (
    <div className="rounded-xl overflow-hidden" style={{ border: '1px solid var(--border)' }}>
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2" style={{ background: 'var(--elevated)' }}>
        <FileText className="w-3.5 h-3.5 text-[var(--text-3)]" />
        <span className="text-[10px] font-semibold text-[var(--text-2)]">{title}</span>
        <div className="flex items-center gap-1.5 ml-auto">
          {active.length > 0 && (
            <span className="text-[8px] px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-400">
              {active.length} processing
            </span>
          )}
          {done.length > 0 && (
            <span className="text-[8px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400">
              {done.length} done
            </span>
          )}
          {failed.length > 0 && (
            <span className="text-[8px] px-2 py-0.5 rounded-full bg-red-500/15 text-red-400">
              {failed.length} failed
            </span>
          )}
        </div>
      </div>

      {/* Document list */}
      <div className="p-2 space-y-2" style={{ background: 'var(--surface)' }}>
        <AnimatePresence>
          {documents.map((doc) => (
            <motion.div
              key={doc.documentId}
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, height: 0 }}
            >
              <OCRDocProgress doc={doc} />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  )
}
