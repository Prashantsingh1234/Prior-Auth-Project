import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { HeatmapCell, PolicyNode } from '../hooks/useReasoningData'

// ─── Config ───────────────────────────────────────────────────────────────────

const EVIDENCE_TYPES = [
  { id: 'clinical_note', label: 'Clinical' },
  { id: 'imaging',       label: 'Imaging' },
  { id: 'functional',    label: 'Functional' },
  { id: 'lab_value',     label: 'Lab' },
  { id: 'medication',    label: 'Medication' },
]

const STATUS_COLOR: Record<string, string> = {
  MET:            '#10b981',
  NOT_MET:        '#ef4444',
  INSUFFICIENT:   '#f59e0b',
  NOT_APPLICABLE: '#6b7280',
}

function confidenceToColor(conf: number): string {
  if (conf >= 0.85) return `rgba(16,185,129,${0.2 + conf * 0.6})`
  if (conf >= 0.6)  return `rgba(99,102,241,${0.15 + conf * 0.5})`
  if (conf >= 0.3)  return `rgba(245,158,11,${0.15 + conf * 0.45})`
  return `rgba(107,114,128,${0.05 + conf * 0.3})`
}

function confidenceToText(conf: number): string {
  if (conf >= 0.85) return '#10b981'
  if (conf >= 0.6)  return '#818cf8'
  if (conf >= 0.3)  return '#f59e0b'
  return '#6b7280'
}

// ─── Tooltip ─────────────────────────────────────────────────────────────────

interface TooltipData {
  cell: HeatmapCell
  policy: PolicyNode
  evidenceLabel: string
  x: number
  y: number
}

// ─── Cell ─────────────────────────────────────────────────────────────────────

interface CellProps {
  cell:      HeatmapCell
  policy:    PolicyNode
  evidLabel: string
  onHover:   (data: TooltipData | null, e?: React.MouseEvent) => void
}

function HeatCell({ cell, policy, evidLabel, onHover }: CellProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
      whileHover={{ scale: 1.08, zIndex: 10 }}
      onMouseEnter={(e) => onHover({ cell, policy, evidenceLabel: evidLabel, x: e.clientX, y: e.clientY }, e)}
      onMouseLeave={() => onHover(null)}
      className="rounded-md flex items-center justify-center cursor-default relative"
      style={{
        background: confidenceToColor(cell.confidence),
        border: cell.confidence > 0.5 ? `1px solid ${confidenceToText(cell.confidence)}30` : '1px solid var(--border)',
        aspectRatio: '1',
      }}
    >
      {cell.confidence > 0.15 && (
        <span
          className="text-[9px] font-bold tabular-nums font-mono"
          style={{ color: confidenceToText(cell.confidence) }}
        >
          {(cell.confidence * 100).toFixed(0)}
        </span>
      )}
    </motion.div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  heatmap:     HeatmapCell[]
  policyNodes: PolicyNode[]
}

export function ConfidenceHeatmap({ heatmap, policyNodes }: Props) {
  const [tooltip, setTooltip] = useState<TooltipData | null>(null)

  function getCell(criterionId: string, evidenceType: string): HeatmapCell {
    return (
      heatmap.find((c) => c.criterionId === criterionId && c.evidenceType === evidenceType) ??
      { criterionId, evidenceType, confidence: 0, count: 0 }
    )
  }

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      {/* Header */}
      <div
        className="px-4 py-3 border-b border-[var(--border)] flex items-center justify-between"
        style={{ background: 'var(--elevated)' }}
      >
        <span className="text-sm font-semibold text-[var(--text-1)]">Confidence Heatmap</span>
        <div className="flex items-center gap-1.5">
          <span className="text-[9px] text-[var(--text-4)]">Low</span>
          <div className="flex gap-0.5">
            {[0.1, 0.3, 0.55, 0.75, 0.92].map((v) => (
              <div
                key={v}
                className="w-4 h-3 rounded-sm"
                style={{ background: confidenceToColor(v) }}
              />
            ))}
          </div>
          <span className="text-[9px] text-[var(--text-4)]">High</span>
        </div>
      </div>

      <div className="p-4">
        {/* Column headers — evidence types */}
        <div className="flex gap-1 mb-2 ml-24">
          {EVIDENCE_TYPES.map((et) => (
            <div key={et.id} className="flex-1 text-center">
              <span className="text-[9px] font-semibold text-[var(--text-4)] uppercase tracking-wide">
                {et.label}
              </span>
            </div>
          ))}
        </div>

        {/* Rows — criteria */}
        <div className="space-y-1.5">
          {policyNodes.map((policy) => {
            const color = STATUS_COLOR[policy.status] ?? '#6b7280'
            return (
              <div key={policy.id} className="flex items-center gap-1">
                {/* Row label */}
                <div className="w-24 shrink-0 pr-2 flex items-center gap-1.5">
                  <div className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: color }} />
                  <span className="text-[10px] font-medium text-[var(--text-2)] truncate leading-tight">
                    {policy.label}
                  </span>
                </div>
                {/* Cells */}
                <div className="flex-1 grid gap-1" style={{ gridTemplateColumns: `repeat(${EVIDENCE_TYPES.length}, 1fr)` }}>
                  {EVIDENCE_TYPES.map((et) => {
                    const cell = getCell(policy.criterionId, et.id)
                    return (
                      <HeatCell
                        key={et.id}
                        cell={cell}
                        policy={policy}
                        evidLabel={et.label}
                        onHover={setTooltip}
                      />
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>

        {/* Scale footnote */}
        <div className="mt-3 flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-[var(--border)]" />
          <span className="text-[9px] text-[var(--text-4)]">
            Cell value = AI confidence that evidence type supports the criterion (0–100)
          </span>
        </div>
      </div>

      {/* Tooltip */}
      <AnimatePresence>
        {tooltip && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ duration: 0.15 }}
            className="fixed z-50 pointer-events-none rounded-xl px-3 py-2 shadow-xl"
            style={{
              left: tooltip.x + 12,
              top:  tooltip.y - 40,
              background: 'var(--elevated)',
              border: '1px solid var(--border)',
              minWidth: 160,
            }}
          >
            <p className="text-[11px] font-semibold text-[var(--text-1)]">{tooltip.policy.label}</p>
            <p className="text-[10px] text-[var(--text-3)] mt-0.5">{tooltip.evidenceLabel} evidence</p>
            <div className="flex items-center justify-between mt-1.5 gap-3">
              <span className="text-[10px] text-[var(--text-4)]">Confidence</span>
              <span
                className="text-[11px] font-bold font-mono tabular-nums"
                style={{ color: confidenceToText(tooltip.cell.confidence) }}
              >
                {(tooltip.cell.confidence * 100).toFixed(1)}%
              </span>
            </div>
            {tooltip.cell.count > 0 && (
              <div className="flex items-center justify-between gap-3">
                <span className="text-[10px] text-[var(--text-4)]">Evidence items</span>
                <span className="text-[11px] font-bold font-mono text-[var(--text-2)]">{tooltip.cell.count}</span>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
