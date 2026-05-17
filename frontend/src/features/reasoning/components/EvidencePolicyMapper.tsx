import { useRef, useState, useLayoutEffect } from 'react'
import { motion } from 'framer-motion'
import type { EvidenceNode, PolicyNode, EvidenceMapping } from '../hooks/useReasoningData'

// ─── Config ───────────────────────────────────────────────────────────────────

const EVIDENCE_TYPE_CFG: Record<string, { color: string; label: string }> = {
  clinical_note: { color: '#0ea5e9', label: 'Clinical' },
  imaging:       { color: '#8b5cf6', label: 'Imaging' },
  functional:    { color: '#a855f7', label: 'Functional' },
  lab_value:     { color: '#10b981', label: 'Lab' },
  medication:    { color: '#f59e0b', label: 'Medication' },
  diagnosis:     { color: '#6366f1', label: 'Diagnosis' },
}

const STATUS_COLOR: Record<string, string> = {
  MET:            '#10b981',
  NOT_MET:        '#ef4444',
  INSUFFICIENT:   '#f59e0b',
  NOT_APPLICABLE: '#6b7280',
}

// ─── Curve layer ──────────────────────────────────────────────────────────────

interface CurveProps {
  x1: number; y1: number
  x2: number; y2: number
  strength: number
  type: 'supports' | 'conflicts' | 'partial'
  isActive:    boolean
  isHighlight: boolean
  color: string
}

function MappingCurve({ x1, y1, x2, y2, type, isActive, isHighlight, color }: CurveProps) {
  const cx1 = x1 + (x2 - x1) * 0.45
  const cy1 = y1
  const cx2 = x1 + (x2 - x1) * 0.55
  const cy2 = y2
  const d   = `M ${x1} ${y1} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${x2} ${y2}`

  const strokeColor = type === 'conflicts' ? '#ef4444' : type === 'partial' ? '#f59e0b' : color
  const opacity     = isHighlight ? 1 : isActive ? 0.55 : 0.18

  return (
    <motion.path
      d={d}
      fill="none"
      strokeWidth={isHighlight ? 2.5 : isActive ? 1.5 : 1}
      stroke={strokeColor}
      opacity={opacity}
      strokeDasharray={type === 'partial' ? '4 3' : undefined}
      initial={{ pathLength: 0 }}
      animate={{ pathLength: 1 }}
      transition={{ duration: 0.8, ease: 'easeOut', delay: 0.2 }}
    />
  )
}

// ─── Node cards ───────────────────────────────────────────────────────────────

function EvidenceCard({
  node, isActive, isHovered, onHover, onClick,
}: {
  node: EvidenceNode
  isActive:  boolean
  isHovered: boolean
  onHover:   (id: string | null) => void
  onClick:   (id: string | null) => void
}) {
  const cfg = EVIDENCE_TYPE_CFG[node.type] ?? { color: '#6b7280', label: node.type }
  return (
    <motion.div
      whileHover={{ x: 3, scale: 1.01 }}
      onMouseEnter={() => onHover(node.id)}
      onMouseLeave={() => onHover(null)}
      onClick={() => onClick(isActive ? null : node.id)}
      className="rounded-xl px-3 py-2 cursor-pointer transition-all select-none"
      style={{
        background:  isActive || isHovered ? `${cfg.color}12` : 'var(--elevated)',
        border:      `1px solid ${isActive ? cfg.color : isHovered ? `${cfg.color}60` : 'var(--border)'}`,
        boxShadow:   isActive ? `0 0 10px ${cfg.color}30` : 'none',
      }}
      animate={{ opacity: isActive || isHovered ? 1 : 0.75 }}
    >
      <div className="flex items-center justify-between mb-0.5">
        <span className="text-[9px] font-bold uppercase tracking-wider" style={{ color: cfg.color }}>
          {cfg.label}
        </span>
        <span
          className="text-[9px] font-mono tabular-nums px-1 rounded"
          style={{ background: `${cfg.color}20`, color: cfg.color }}
        >
          {(node.confidence * 100).toFixed(0)}%
        </span>
      </div>
      <p className="text-[11px] font-semibold text-[var(--text-1)] leading-tight">{node.label}</p>
      <p className="text-[10px] text-[var(--text-4)] mt-0.5 font-mono">{node.value}</p>
    </motion.div>
  )
}

function PolicyCard({
  node, isActive, isHovered, onHover, onClick,
}: {
  node: PolicyNode
  isActive:  boolean
  isHovered: boolean
  onHover:   (id: string | null) => void
  onClick:   (id: string | null) => void
}) {
  const color = STATUS_COLOR[node.status] ?? '#6b7280'
  return (
    <motion.div
      whileHover={{ x: -3, scale: 1.01 }}
      onMouseEnter={() => onHover(node.id)}
      onMouseLeave={() => onHover(null)}
      onClick={() => onClick(isActive ? null : node.id)}
      className="rounded-xl px-3 py-2 cursor-pointer transition-all select-none"
      style={{
        background:  isActive || isHovered ? `${color}12` : 'var(--elevated)',
        border:      `1px solid ${isActive ? color : isHovered ? `${color}60` : 'var(--border)'}`,
        boxShadow:   isActive ? `0 0 10px ${color}30` : 'none',
      }}
      animate={{ opacity: isActive || isHovered ? 1 : 0.75 }}
    >
      <div className="flex items-center justify-between mb-0.5">
        <span
          className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-md"
          style={{ background: `${color}20`, color }}
        >
          {node.status.replace('_', ' ')}
        </span>
        <span className="text-[9px] font-mono text-[var(--text-4)]">
          w={node.weight.toFixed(2)}
        </span>
      </div>
      <p className="text-[11px] font-semibold text-[var(--text-1)] leading-tight">{node.label}</p>
      <p className="text-[10px] text-[var(--text-4)] mt-0.5 leading-snug">{node.requirement}</p>
    </motion.div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  evidenceNodes:    EvidenceNode[]
  policyNodes:      PolicyNode[]
  mappings:         EvidenceMapping[]
  activeEvidenceId: string | null
  activePolicyId:   string | null
  onEvidenceClick:  (id: string | null) => void
  onPolicyClick:    (id: string | null) => void
}

interface NodePos { id: string; x: number; y: number }

export function EvidencePolicyMapper({
  evidenceNodes, policyNodes, mappings,
  activeEvidenceId, activePolicyId,
  onEvidenceClick, onPolicyClick,
}: Props) {
  const svgRef       = useRef<SVGSVGElement>(null)
  const leftColRef   = useRef<HTMLDivElement>(null)
  const rightColRef  = useRef<HTMLDivElement>(null)
  const [positions, setPositions] = useState<{ evidence: NodePos[]; policy: NodePos[] }>({ evidence: [], policy: [] })
  const [hoveredEvidenceId, setHoveredEvidenceId] = useState<string | null>(null)
  const [hoveredPolicyId,   setHoveredPolicyId]   = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    function measure() {
      if (!containerRef.current) return
      const containerRect = containerRef.current.getBoundingClientRect()

      const ePos: NodePos[] = []
      evidenceNodes.forEach((n) => {
        const el = containerRef.current!.querySelector(`[data-evidence="${n.id}"]`)
        if (el) {
          const r = el.getBoundingClientRect()
          ePos.push({ id: n.id, x: r.right - containerRect.left, y: r.top + r.height / 2 - containerRect.top })
        }
      })

      const pPos: NodePos[] = []
      policyNodes.forEach((n) => {
        const el = containerRef.current!.querySelector(`[data-policy="${n.id}"]`)
        if (el) {
          const r = el.getBoundingClientRect()
          pPos.push({ id: n.id, x: r.left - containerRect.left, y: r.top + r.height / 2 - containerRect.top })
        }
      })

      setPositions({ evidence: ePos, policy: pPos })
    }

    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [evidenceNodes, policyNodes])

  const containerHeight = containerRef.current?.clientHeight ?? 400

  const relevantMappings = mappings.filter((m) => {
    if (activeEvidenceId && activePolicyId) {
      return m.evidenceId === activeEvidenceId && m.policyId === activePolicyId
    }
    if (activeEvidenceId) return m.evidenceId === activeEvidenceId
    if (activePolicyId)   return m.policyId === activePolicyId
    if (hoveredEvidenceId) return m.evidenceId === hoveredEvidenceId
    if (hoveredPolicyId)   return m.policyId === hoveredPolicyId
    return true
  })

  return (
    <div
      className="rounded-2xl overflow-hidden flex flex-col"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      {/* Header */}
      <div
        className="px-4 py-3 border-b border-[var(--border)] flex items-center justify-between shrink-0"
        style={{ background: 'var(--elevated)' }}
      >
        <span className="text-sm font-semibold text-[var(--text-1)]">Evidence → Policy Mapping</span>
        <div className="flex items-center gap-2">
          {[
            { color: '#10b981', label: 'Supports' },
            { color: '#f59e0b', label: 'Partial' },
            { color: '#ef4444', label: 'Conflicts' },
          ].map((l) => (
            <div key={l.label} className="flex items-center gap-1">
              <div className="w-4 h-px" style={{ background: l.color }} />
              <span className="text-[9px] text-[var(--text-4)]">{l.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Map */}
      <div ref={containerRef} className="relative flex-1 p-4" style={{ minHeight: 320 }}>
        {/* SVG curves overlay */}
        <svg
          ref={svgRef}
          className="absolute inset-0 w-full h-full pointer-events-none"
          style={{ zIndex: 1 }}
          viewBox={`0 0 ${containerRef.current?.clientWidth ?? 600} ${containerHeight}`}
          preserveAspectRatio="none"
        >
          {mappings.map((m) => {
            const ePos = positions.evidence.find((p) => p.id === m.evidenceId)
            const pPos = positions.policy.find((p) => p.id === m.policyId)
            if (!ePos || !pPos) return null
            const cfg = EVIDENCE_TYPE_CFG[evidenceNodes.find((e) => e.id === m.evidenceId)?.type ?? ''] ?? { color: '#6b7280' }
            const isHighlight = relevantMappings.includes(m)
            const isActive = !!(activeEvidenceId || activePolicyId || hoveredEvidenceId || hoveredPolicyId)
            return (
              <MappingCurve
                key={`${m.evidenceId}-${m.policyId}`}
                x1={ePos.x} y1={ePos.y}
                x2={pPos.x} y2={pPos.y}
                strength={m.strength}
                type={m.type}
                isActive={isActive}
                isHighlight={isHighlight}
                color={cfg.color}
              />
            )
          })}
        </svg>

        {/* Columns */}
        <div className="relative flex gap-0 h-full" style={{ zIndex: 2 }}>
          {/* Evidence column */}
          <div ref={leftColRef} className="flex-1 flex flex-col gap-2">
            <p className="text-[9px] font-bold uppercase tracking-widest text-[var(--text-4)] mb-1">
              Patient Evidence
            </p>
            {evidenceNodes.map((n) => (
              <div key={n.id} data-evidence={n.id}>
                <EvidenceCard
                  node={n}
                  isActive={activeEvidenceId === n.id}
                  isHovered={hoveredEvidenceId === n.id}
                  onHover={setHoveredEvidenceId}
                  onClick={onEvidenceClick}
                />
              </div>
            ))}
          </div>

          {/* Gap for curves */}
          <div style={{ width: 80, flexShrink: 0 }} />

          {/* Policy column */}
          <div ref={rightColRef} className="flex-1 flex flex-col gap-2">
            <p className="text-[9px] font-bold uppercase tracking-widest text-[var(--text-4)] mb-1 text-right">
              Policy Criteria
            </p>
            {policyNodes.map((n) => (
              <div key={n.id} data-policy={n.id}>
                <PolicyCard
                  node={n}
                  isActive={activePolicyId === n.id}
                  isHovered={hoveredPolicyId === n.id}
                  onHover={setHoveredPolicyId}
                  onClick={onPolicyClick}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
