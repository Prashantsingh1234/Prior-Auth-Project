import { motion } from 'framer-motion'
import {
  ScanLine, Tag, LayoutTemplate, FileText,
  Globe, BookOpen, Eye, EyeOff,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type {
  OCRMetrics, ClassificationResult, LayoutElement, LayoutElementType,
} from '../hooks/useDocumentIntelligence'

// ─── Layout element colors ────────────────────────────────────────────────────

const LAYOUT_CFG: Record<LayoutElementType, { color: string; border: string; bg: string; label: string }> = {
  header:      { color: '#0ea5e9', border: 'rgba(14,165,233,0.6)',  bg: 'rgba(14,165,233,0.12)',  label: 'Header'      },
  field_block: { color: '#8b5cf6', border: 'rgba(139,92,246,0.6)', bg: 'rgba(139,92,246,0.12)', label: 'Fields'      },
  table:       { color: '#10b981', border: 'rgba(16,185,129,0.6)', bg: 'rgba(16,185,129,0.12)', label: 'Table'       },
  paragraph:   { color: '#f59e0b', border: 'rgba(245,158,11,0.6)', bg: 'rgba(245,158,11,0.12)', label: 'Paragraph'   },
  signature:   { color: '#ef4444', border: 'rgba(239,68,68,0.6)',  bg: 'rgba(239,68,68,0.12)',  label: 'Signature'   },
  logo:        { color: '#6b7280', border: 'rgba(107,114,128,0.6)',bg: 'rgba(107,114,128,0.1)', label: 'Logo'        },
  footer:      { color: '#6b7280', border: 'rgba(107,114,128,0.5)',bg: 'rgba(107,114,128,0.08)',label: 'Footer'      },
}

// ─── Confidence ring ──────────────────────────────────────────────────────────

function ConfRing({ value, size = 52, label }: { value: number; size?: number; label: string }) {
  const r   = (size - 6) / 2
  const c   = 2 * Math.PI * r
  const pct = value
  const color = pct >= 0.9 ? '#10b981' : pct >= 0.75 ? '#f59e0b' : '#ef4444'

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
          <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--border)" strokeWidth={5} />
          <motion.circle
            cx={size/2} cy={size/2} r={r}
            fill="none"
            stroke={color}
            strokeWidth={5}
            strokeLinecap="round"
            strokeDasharray={c}
            initial={{ strokeDashoffset: c }}
            animate={{ strokeDashoffset: c - c * pct }}
            transition={{ duration: 0.9, ease: 'easeOut', delay: 0.2 }}
            style={{ filter: `drop-shadow(0 0 3px ${color}88)` }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-[10px] font-bold tabular-nums" style={{ color }}>
            {Math.round(pct * 100)}%
          </span>
        </div>
      </div>
      <span className="text-[9px] text-[var(--text-4)] text-center leading-tight">{label}</span>
    </div>
  )
}

// ─── Page confidence bar ──────────────────────────────────────────────────────

function PageConfBar({ page, confidence, delay }: { page: number; confidence: number; delay: number }) {
  const color = confidence >= 0.95 ? '#10b981' : confidence >= 0.85 ? '#f59e0b' : '#ef4444'
  return (
    <div className="flex items-center gap-2">
      <span className="text-[9px] text-[var(--text-4)] w-12 flex-shrink-0">Page {page}</span>
      <div className="flex-1 h-1.5 rounded-full bg-[var(--border)] overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ background: color }}
          initial={{ width: 0 }}
          animate={{ width: `${confidence * 100}%` }}
          transition={{ duration: 0.6, delay, ease: 'easeOut' }}
        />
      </div>
      <span className="text-[9px] font-mono tabular-nums w-8 text-right" style={{ color }}>
        {Math.round(confidence * 100)}%
      </span>
    </div>
  )
}

// ─── OCR Metrics panel ────────────────────────────────────────────────────────

function OCRPanel({ ocr }: { ocr: OCRMetrics }) {
  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--border)]">
        <ScanLine className="w-4 h-4 text-cyan-400" />
        <span className="text-sm font-semibold text-[var(--text-1)]">OCR Engine</span>
        <span
          className="ml-auto text-[9px] font-medium px-2 py-0.5 rounded-full"
          style={{ background: 'rgba(16,185,129,0.12)', color: '#10b981' }}
        >
          {Math.round(ocr.overallConfidence * 100)}% confidence
        </span>
      </div>

      <div className="p-4 space-y-4">
        {/* Rings row */}
        <div className="flex items-end justify-around">
          <ConfRing value={ocr.overallConfidence} label="Overall" />
          <ConfRing value={1 - (ocr.lowConfidenceWords / ocr.wordCount)} label="Word Quality" />
          <ConfRing value={ocr.noiseLevel === 'low' ? 0.94 : ocr.noiseLevel === 'medium' ? 0.72 : 0.45} label="Image Quality" />
        </div>

        {/* Per-page bars */}
        <div className="space-y-1.5">
          <p className="text-[9px] text-[var(--text-4)] uppercase tracking-wider font-medium">Per-page Confidence</p>
          {ocr.pageConfidences.map((conf, i) => (
            <PageConfBar key={i} page={i + 1} confidence={conf} delay={i * 0.1} />
          ))}
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 gap-x-4 gap-y-2 pt-1 border-t border-[var(--border)]">
          {[
            { label: 'Words Extracted', value: ocr.wordCount.toLocaleString() },
            { label: 'Low Conf. Words',  value: ocr.lowConfidenceWords.toString() },
            { label: 'Resolution',       value: `${ocr.resolution} DPI` },
            { label: 'Skew Angle',       value: `${ocr.skewAngle}°` },
            { label: 'Color Mode',       value: ocr.colorMode },
            { label: 'Process Time',     value: `${(ocr.processingMs / 1000).toFixed(2)}s` },
          ].map(({ label, value }) => (
            <div key={label}>
              <p className="text-[8px] text-[var(--text-4)] uppercase tracking-wider">{label}</p>
              <p className="text-[11px] font-medium text-[var(--text-1)] font-mono">{value}</p>
            </div>
          ))}
        </div>

        {/* Engine badge */}
        <div
          className="flex items-center gap-2 px-3 py-2 rounded-xl"
          style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
        >
          <ScanLine className="w-3.5 h-3.5 text-[var(--text-4)]" />
          <span className="text-[10px] text-[var(--text-3)] font-mono">{ocr.engineUsed}</span>
        </div>
      </div>
    </div>
  )
}

// ─── Classification panel ─────────────────────────────────────────────────────

function ClassificationPanel({ cls }: { cls: ClassificationResult }) {
  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--border)]">
        <Tag className="w-4 h-4 text-violet-400" />
        <span className="text-sm font-semibold text-[var(--text-1)]">Document Classification</span>
      </div>

      <div className="p-4 space-y-4">
        {/* Primary classification */}
        <div>
          <div
            className="flex items-center justify-between px-3 py-2.5 rounded-xl mb-2"
            style={{ background: 'rgba(139,92,246,0.12)', border: '1px solid rgba(139,92,246,0.3)' }}
          >
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-violet-400" />
              <span className="text-sm font-bold text-violet-300">{cls.primaryLabel}</span>
            </div>
            <span className="text-sm font-bold tabular-nums text-violet-400">
              {Math.round(cls.confidence * 100)}%
            </span>
          </div>

          {/* Alternatives */}
          {cls.alternatives.map((alt) => (
            <div key={alt.type} className="flex items-center gap-2 py-1.5 px-2">
              <div className="flex-1 text-[10px] text-[var(--text-4)]">{alt.label}</div>
              <div className="w-20 h-1 rounded-full bg-[var(--border)] overflow-hidden">
                <div className="h-full rounded-full bg-[var(--text-4)]" style={{ width: `${alt.confidence * 100}%` }} />
              </div>
              <span className="text-[9px] font-mono text-[var(--text-4)] w-8 text-right">
                {(alt.confidence * 100).toFixed(1)}%
              </span>
            </div>
          ))}
        </div>

        {/* Detected sections */}
        <div>
          <p className="text-[9px] text-[var(--text-4)] uppercase tracking-wider font-medium mb-2">
            <BookOpen className="w-3 h-3 inline mr-1" />
            Detected Sections ({cls.detectedSections.length})
          </p>
          <div className="flex flex-wrap gap-1.5">
            {cls.detectedSections.map((s) => (
              <span
                key={s}
                className="text-[9px] font-medium px-2 py-0.5 rounded-full"
                style={{ background: 'rgba(139,92,246,0.1)', color: '#a78bfa', border: '1px solid rgba(139,92,246,0.2)' }}
              >
                {s}
              </span>
            ))}
          </div>
        </div>

        {/* Doc stats */}
        <div className="grid grid-cols-3 gap-2 pt-1 border-t border-[var(--border)]">
          {[
            { label: 'Pages',     value: cls.pageCount },
            { label: 'Words',     value: cls.wordCount.toLocaleString() },
            { label: 'Language',  value: 'en-US' },
          ].map(({ label, value }) => (
            <div key={label} className="text-center">
              <p className="text-xs font-bold text-[var(--text-1)]">{value}</p>
              <p className="text-[9px] text-[var(--text-4)]">{label}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Layout detection panel ───────────────────────────────────────────────────

function LayoutPanel({
  elements, showOverlay, onToggle,
}: { elements: LayoutElement[]; showOverlay: boolean; onToggle: () => void }) {
  const page0 = elements.filter((e) => e.pageIndex === 0)

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--border)]">
        <LayoutTemplate className="w-4 h-4 text-cyan-400" />
        <span className="text-sm font-semibold text-[var(--text-1)]">Layout Detection</span>
        <button
          onClick={onToggle}
          className={cn(
            'ml-auto flex items-center gap-1.5 px-2 py-1 rounded-lg text-[10px] font-medium border transition-all',
            showOverlay
              ? 'bg-cyan-500/10 border-cyan-500/30 text-cyan-400'
              : 'border-[var(--border)] text-[var(--text-4)] hover:bg-[var(--elevated)]'
          )}
        >
          {showOverlay ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
          Overlay
        </button>
      </div>

      <div className="p-4 space-y-3">
        {/* Document canvas */}
        <div
          className="relative rounded-xl overflow-hidden"
          style={{ background: 'white', border: '1px solid rgba(0,0,0,0.1)', aspectRatio: '8.5/11' }}
        >
          {/* Document lines simulation */}
          <div className="absolute inset-0 p-3 space-y-1">
            {Array.from({ length: 18 }, (_, i) => (
              <div
                key={i}
                className="rounded-sm"
                style={{
                  height: 4,
                  width:  `${60 + ((i * 37) % 40)}%`,
                  background: 'rgba(0,0,0,0.08)',
                }}
              />
            ))}
          </div>

          {/* Layout bounding boxes */}
          {showOverlay && page0.map((el, i) => {
            const cfg = LAYOUT_CFG[el.type] ?? LAYOUT_CFG.paragraph
            return (
              <motion.div
                key={el.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.08 }}
                className="absolute rounded"
                style={{
                  left:   `${el.x}%`,
                  top:    `${el.y}%`,
                  width:  `${el.w}%`,
                  height: `${el.h}%`,
                  border: `1.5px solid ${cfg.border}`,
                  background: cfg.bg,
                }}
                title={`${cfg.label}: ${Math.round(el.confidence * 100)}%`}
              >
                <span
                  className="absolute -top-3 left-0 text-[6px] font-bold px-1 rounded whitespace-nowrap"
                  style={{ background: cfg.color, color: 'white' }}
                >
                  {cfg.label}
                </span>
              </motion.div>
            )
          })}
        </div>

        {/* Legend */}
        <div className="flex flex-wrap gap-x-3 gap-y-1.5">
          {(Object.entries(LAYOUT_CFG) as [LayoutElementType, typeof LAYOUT_CFG[LayoutElementType]][])
            .filter(([type]) => page0.some((e) => e.type === type))
            .map(([type, cfg]) => (
              <div key={type} className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-sm" style={{ background: cfg.color }} />
                <span className="text-[9px] text-[var(--text-4)]">{cfg.label}</span>
              </div>
            ))
          }
        </div>

        {/* Element count */}
        <p className="text-[9px] text-[var(--text-4)]">
          {elements.length} layout elements detected · {page0.length} on page 1
        </p>
      </div>
    </div>
  )
}

// ─── Extraction quality bar ───────────────────────────────────────────────────

interface QualityBarProps {
  label:      string
  value:      number
  color:      string
  delay?:     number
  sublabel?:  string
}

function QualityBar({ label, value, color, delay = 0, sublabel }: QualityBarProps) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-medium text-[var(--text-2)]">{label}</span>
        <span className="text-[10px] font-bold tabular-nums font-mono" style={{ color }}>
          {Math.round(value * 100)}%
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-[var(--border)] overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ background: color, boxShadow: `0 0 6px ${color}66` }}
          initial={{ width: 0 }}
          animate={{ width: `${value * 100}%` }}
          transition={{ duration: 0.7, delay, ease: 'easeOut' }}
        />
      </div>
      {sublabel && <p className="text-[8px] text-[var(--text-4)]">{sublabel}</p>}
    </div>
  )
}

// ─── Extraction quality overview ──────────────────────────────────────────────

function ExtractionQualityOverview({ cards }: { cards: { overallConfidence: number; completeness: number; foundFields: number; expectedFields: number }[] }) {
  if (cards.length === 0) return null
  const avgConf = cards.reduce((s, c) => s + c.overallConfidence, 0) / cards.length
  const avgComp = cards.reduce((s, c) => s + c.completeness, 0) / cards.length
  const totalFound    = cards.reduce((s, c) => s + c.foundFields, 0)
  const totalExpected = cards.reduce((s, c) => s + c.expectedFields, 0)

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--border)]">
        <Globe className="w-4 h-4 text-emerald-400" />
        <span className="text-sm font-semibold text-[var(--text-1)]">Extraction Quality</span>
        <span
          className="ml-auto text-[9px] font-bold px-2 py-0.5 rounded-full"
          style={{ background: 'rgba(16,185,129,0.12)', color: '#10b981' }}
        >
          {Math.round(avgConf * 100)}% avg
        </span>
      </div>
      <div className="p-4 space-y-3">
        <QualityBar label="AI Extraction Confidence" value={avgConf} color="#8b5cf6" delay={0}    sublabel={`Across all ${cards.length} entity types`} />
        <QualityBar label="Field Completeness"        value={avgComp} color="#0ea5e9" delay={0.1}  sublabel={`${totalFound}/${totalExpected} expected fields found`} />
        <QualityBar label="OCR Source Fidelity"       value={0.974}   color="#10b981" delay={0.2}  sublabel="Raw text extraction quality" />
        <QualityBar label="Entity Normalization"       value={0.938}   color="#f59e0b" delay={0.3}  sublabel="Value standardization accuracy" />
      </div>
    </div>
  )
}

// ─── Main export ──────────────────────────────────────────────────────────────

interface Props {
  ocr:            OCRMetrics | null
  classification: ClassificationResult | null
  layout:         LayoutElement[]
  showLayout:     boolean
  onToggleLayout: () => void
  cards:          { overallConfidence: number; completeness: number; foundFields: number; expectedFields: number }[]
}

export function DocumentQuality({ ocr, classification, layout, showLayout, onToggleLayout, cards }: Props) {
  if (!ocr && !classification && layout.length === 0) return null

  return (
    <div className="space-y-4">
      {cards.length > 0 && <ExtractionQualityOverview cards={cards} />}
      {ocr             && <OCRPanel ocr={ocr} />}
      {classification  && <ClassificationPanel cls={classification} />}
      {layout.length > 0 && (
        <LayoutPanel elements={layout} showOverlay={showLayout} onToggle={onToggleLayout} />
      )}
    </div>
  )
}
