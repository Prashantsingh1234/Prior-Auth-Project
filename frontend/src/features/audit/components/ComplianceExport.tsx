import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Download, FileText, FileJson, File, Check,
  Loader2, Shield, Lock, AlertTriangle, ChevronDown,
} from 'lucide-react'

type ExportFormat = 'csv' | 'json' | 'pdf' | 'hl7'

interface FormatConfig {
  id:          ExportFormat
  label:       string
  desc:        string
  icon:        React.ElementType
  color:       string
  compliance?: string
}

const FORMATS: FormatConfig[] = [
  { id: 'csv',  label: 'CSV',      desc: 'Flat file for spreadsheet analysis', icon: FileText, color: '#10b981', compliance: 'HIPAA §164.312' },
  { id: 'json', label: 'JSON',     desc: 'Structured export with full trace data', icon: FileJson, color: '#6366f1', compliance: 'HL7 FHIR R4' },
  { id: 'pdf',  label: 'PDF',      desc: 'Signed audit report for regulators', icon: File, color: '#f59e0b', compliance: 'CMS §482.24' },
  { id: 'hl7',  label: 'HL7 v2',  desc: 'Clinical messaging standard export', icon: FileText, color: '#0ea5e9', compliance: 'HL7 v2.8' },
]

const FIELD_GROUPS = [
  {
    label: 'Core Fields', fields: [
      { id: 'event_id',    label: 'Event ID',        default: true },
      { id: 'case_ref',    label: 'Case Reference',  default: true },
      { id: 'event_type',  label: 'Event Type',      default: true },
      { id: 'description', label: 'Description',     default: true },
      { id: 'occurred_at', label: 'Timestamp',       default: true },
      { id: 'category',    label: 'Category',        default: true },
    ],
  },
  {
    label: 'Actor', fields: [
      { id: 'actor_name', label: 'Actor Name',  default: true },
      { id: 'actor_role', label: 'Actor Role',  default: true },
      { id: 'actor_id',   label: 'Actor ID',    default: false },
      { id: 'ip_address', label: 'IP Address',  default: false },
      { id: 'user_agent', label: 'User Agent',  default: false },
    ],
  },
  {
    label: 'Integrity', fields: [
      { id: 'hash',      label: 'Integrity Hash', default: true },
      { id: 'immutable', label: 'Immutable Flag', default: true },
    ],
  },
  {
    label: 'AI / Trace', fields: [
      { id: 'ai_model',       label: 'AI Model',         default: false },
      { id: 'ai_confidence',  label: 'AI Confidence',    default: false },
      { id: 'ai_rec',         label: 'AI Recommendation', default: false },
      { id: 'grounding_score', label: 'Grounding Score', default: false },
      { id: 'input_tokens',   label: 'Input Tokens',     default: false },
      { id: 'output_tokens',  label: 'Output Tokens',    default: false },
      { id: 'override_flag',  label: 'Override Flag',    default: false },
    ],
  },
]

const DATE_PRESETS = [
  { label: 'Today',        days: 0 },
  { label: 'Last 7 days',  days: 7 },
  { label: 'Last 30 days', days: 30 },
  { label: 'Last 90 days', days: 90 },
  { label: 'Q4 2024',      days: 92 },
  { label: 'All time',     days: -1 },
]

type ExportState = 'idle' | 'building' | 'signing' | 'done'

interface ComplianceExportProps {
  totalEntries: number
  onClose: () => void
}

export function ComplianceExport({ totalEntries, onClose }: ComplianceExportProps) {
  const [format, setFormat]       = useState<ExportFormat>('csv')
  const [preset, setPreset]       = useState('Last 30 days')
  const [selectedFields, setFields] = useState<Set<string>>(
    new Set(FIELD_GROUPS.flatMap((g) => g.fields.filter((f) => f.default).map((f) => f.id))),
  )
  const [includeTraces, setIncludeTraces] = useState(false)
  const [includeRedacted, setRedacted]    = useState(true)
  const [exportState, setExportState]     = useState<ExportState>('idle')
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set(['Core Fields']))

  function toggleField(id: string) {
    setFields((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function toggleGroup(label: string) {
    setExpandedGroups((s) => {
      const n = new Set(s)
      n.has(label) ? n.delete(label) : n.add(label)
      return n
    })
  }

  function selectAll(groupLabel: string) {
    const group = FIELD_GROUPS.find((g) => g.label === groupLabel)
    if (!group) return
    setFields((prev) => {
      const next = new Set(prev)
      group.fields.forEach((f) => next.add(f.id))
      return next
    })
  }

  async function handleExport() {
    setExportState('building')
    await new Promise((r) => setTimeout(r, 1200))
    setExportState('signing')
    await new Promise((r) => setTimeout(r, 800))
    setExportState('done')
    await new Promise((r) => setTimeout(r, 1400))
    setExportState('idle')
  }

  const fmtCfg  = FORMATS.find((f) => f.id === format)!
  const fieldCount = selectedFields.size
  const estimatedRows = preset === 'All time' ? totalEntries : Math.ceil(totalEntries * (DATE_PRESETS.find((d) => d.label === preset)?.days ?? 30) / 90)

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="shrink-0 px-5 py-4 border-b border-[var(--border)]" style={{ background: 'var(--elevated)' }}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center" style={{ background: '#10b98115', border: '1px solid #10b98130' }}>
            <Download className="w-4 h-4 text-emerald-400" />
          </div>
          <div>
            <p className="text-sm font-bold text-[var(--text-1)]">Compliance Export</p>
            <p className="text-[10px] text-[var(--text-4)]">HIPAA-compliant · Digitally signed · Non-repudiable audit trail</p>
          </div>
          <button onClick={onClose} className="ml-auto text-[var(--text-4)] hover:text-[var(--text-2)] text-xs px-2 py-1 rounded transition-colors" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
            Close
          </button>
        </div>

        {/* Compliance badges */}
        <div className="flex items-center gap-2 mt-3 flex-wrap">
          {['HIPAA §164.312', 'SOC 2 Type II', 'CMS §482.24', '21 CFR Part 11'].map((b) => (
            <span key={b} className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[8px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Shield className="w-2 h-2" />{b}
            </span>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-5">

        {/* Format picker */}
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wide text-[var(--text-3)] mb-2">Export Format</p>
          <div className="grid grid-cols-2 gap-2">
            {FORMATS.map((f) => (
              <motion.button
                key={f.id}
                whileTap={{ scale: 0.98 }}
                onClick={() => setFormat(f.id)}
                className="flex items-start gap-2.5 p-3 rounded-xl text-left transition-all"
                style={{
                  background: format === f.id ? `${f.color}12` : 'var(--elevated)',
                  border:     `1px solid ${format === f.id ? f.color + '50' : 'var(--border)'}`,
                }}
              >
                <f.icon className="w-4 h-4 shrink-0 mt-0.5" style={{ color: f.color }} />
                <div>
                  <p className="text-[10px] font-bold" style={{ color: format === f.id ? f.color : 'var(--text-1)' }}>{f.label}</p>
                  <p className="text-[8px] text-[var(--text-4)] mt-0.5">{f.desc}</p>
                  {f.compliance && (
                    <span className="mt-1 inline-flex items-center gap-0.5 text-[7px] font-mono" style={{ color: f.color }}>
                      <Lock className="w-2 h-2" />{f.compliance}
                    </span>
                  )}
                </div>
                {format === f.id && <Check className="w-3 h-3 ml-auto shrink-0" style={{ color: f.color }} />}
              </motion.button>
            ))}
          </div>
        </div>

        {/* Date range */}
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wide text-[var(--text-3)] mb-2">Date Range</p>
          <div className="flex flex-wrap gap-1.5">
            {DATE_PRESETS.map((p) => (
              <button
                key={p.label}
                onClick={() => setPreset(p.label)}
                className="px-2.5 py-1 rounded-lg text-[9px] font-semibold transition-all"
                style={{
                  background: preset === p.label ? '#6366f1' : 'var(--elevated)',
                  color:      preset === p.label ? 'white' : 'var(--text-3)',
                  border:     `1px solid ${preset === p.label ? '#6366f1' : 'var(--border)'}`,
                }}
              >{p.label}</button>
            ))}
          </div>
        </div>

        {/* Field selector */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-[10px] font-bold uppercase tracking-wide text-[var(--text-3)]">Fields ({fieldCount} selected)</p>
          </div>
          <div className="space-y-1.5 rounded-xl overflow-hidden" style={{ border: '1px solid var(--border)' }}>
            {FIELD_GROUPS.map((group) => {
              const expanded   = expandedGroups.has(group.label)
              const groupCount = group.fields.filter((f) => selectedFields.has(f.id)).length
              return (
                <div key={group.label} style={{ borderBottom: '1px solid var(--border)' }}>
                  <button
                    onClick={() => toggleGroup(group.label)}
                    className="w-full flex items-center justify-between px-3 py-2 hover:bg-[var(--elevated)] transition-colors"
                  >
                    <span className="text-[9px] font-semibold text-[var(--text-2)]">{group.label}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-[8px] text-[var(--text-4)]">{groupCount}/{group.fields.length}</span>
                      <button
                        onClick={(e) => { e.stopPropagation(); selectAll(group.label) }}
                        className="text-[7px] px-1.5 py-0.5 rounded text-[#6366f1] hover:bg-[#6366f115] transition-colors"
                      >All</button>
                      <ChevronDown className="w-3 h-3 text-[var(--text-4)] transition-transform" style={{ transform: expanded ? 'rotate(180deg)' : 'none' }} />
                    </div>
                  </button>
                  <AnimatePresence>
                    {expanded && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden"
                      >
                        <div className="px-3 pb-2 flex flex-wrap gap-1.5">
                          {group.fields.map((field) => {
                            const active = selectedFields.has(field.id)
                            return (
                              <button
                                key={field.id}
                                onClick={() => toggleField(field.id)}
                                className="flex items-center gap-1 px-2 py-0.5 rounded-lg text-[8px] font-medium transition-all"
                                style={{
                                  background: active ? '#6366f115' : 'var(--surface)',
                                  color:      active ? '#6366f1' : 'var(--text-4)',
                                  border:     `1px solid ${active ? '#6366f140' : 'var(--border)'}`,
                                }}
                              >
                                {active && <Check className="w-2 h-2" />}
                                {field.label}
                              </button>
                            )
                          })}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )
            })}
          </div>
        </div>

        {/* Options */}
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wide text-[var(--text-3)] mb-2">Options</p>
          <div className="space-y-2">
            {[
              { label: 'Include full AI trace data', desc: 'Prompt/completion text, retrieval chunks, token counts', value: includeTraces, onChange: setIncludeTraces },
              { label: 'Apply PHI redaction', desc: 'Mask patient identifiers per HIPAA Safe Harbor', value: includeRedacted, onChange: setRedacted },
            ].map(({ label, desc, value, onChange }) => (
              <label key={label} className="flex items-start gap-3 cursor-pointer p-2.5 rounded-xl hover:bg-[var(--elevated)] transition-colors" style={{ border: '1px solid var(--border)' }}>
                <div
                  className="w-4 h-4 rounded flex items-center justify-center shrink-0 mt-0.5 transition-all"
                  style={{ background: value ? '#6366f1' : 'var(--surface)', border: `1px solid ${value ? '#6366f1' : 'var(--border)'}` }}
                  onClick={() => onChange(!value)}
                >
                  {value && <Check className="w-2.5 h-2.5 text-white" />}
                </div>
                <div>
                  <p className="text-[9px] font-semibold text-[var(--text-1)]">{label}</p>
                  <p className="text-[8px] text-[var(--text-4)]">{desc}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Export summary */}
        <div className="rounded-xl p-4" style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
          <p className="text-[9px] font-bold uppercase tracking-wide text-[var(--text-3)] mb-2.5">Export Summary</p>
          <div className="grid grid-cols-3 gap-3 mb-3">
            {[
              { label: 'Format', value: fmtCfg.label },
              { label: 'Records', value: `~${Math.max(1, estimatedRows)}` },
              { label: 'Fields', value: `${fieldCount}` },
            ].map((s) => (
              <div key={s.label} className="text-center">
                <p className="text-[8px] text-[var(--text-4)]">{s.label}</p>
                <p className="text-sm font-bold font-mono text-[var(--text-1)]">{s.value}</p>
              </div>
            ))}
          </div>
          <div className="flex items-center gap-1.5 text-[8px] text-emerald-400">
            <Lock className="w-2.5 h-2.5" />
            This export will be digitally signed and logged as an immutable compliance event
          </div>
        </div>
      </div>

      {/* Export button */}
      <div className="shrink-0 px-5 py-4 border-t border-[var(--border)]" style={{ background: 'var(--elevated)' }}>
        <AnimatePresence mode="wait">
          {exportState === 'idle' && (
            <motion.button
              key="idle"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleExport}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-bold text-white transition-all"
              style={{ background: 'linear-gradient(135deg, #10b981, #059669)' }}
            >
              <Download className="w-4 h-4" />
              Export {fmtCfg.label} — {preset}
            </motion.button>
          )}
          {exportState === 'building' && (
            <motion.div key="building" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold"
              style={{ background: '#6366f115', border: '1px solid #6366f140', color: '#6366f1' }}>
              <Loader2 className="w-4 h-4 animate-spin" />
              Building export…
            </motion.div>
          )}
          {exportState === 'signing' && (
            <motion.div key="signing" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold"
              style={{ background: '#f59e0b15', border: '1px solid #f59e0b40', color: '#f59e0b' }}>
              <Lock className="w-4 h-4 animate-pulse" />
              Applying digital signature…
            </motion.div>
          )}
          {exportState === 'done' && (
            <motion.div key="done" initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-bold"
              style={{ background: '#10b98115', border: '1px solid #10b98140', color: '#10b981' }}>
              <Check className="w-4 h-4" />
              Export ready — audit event logged
            </motion.div>
          )}
        </AnimatePresence>

        {exportState === 'idle' && (
          <div className="flex items-center justify-center gap-1.5 mt-2 text-[8px] text-[var(--text-4)]">
            <AlertTriangle className="w-2.5 h-2.5" />
            Export activity will be recorded in the audit log
          </div>
        )}
      </div>
    </div>
  )
}
