import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronRight, CheckCircle2, XCircle, MinusCircle, FileText, Link2, Stethoscope } from 'lucide-react'
import type { PolicyNode, EvidenceNode, EvidenceMapping } from '../hooks/useReasoningData'

// ─── Types ────────────────────────────────────────────────────────────────────

type NodeType = 'root' | 'criterion' | 'evidence' | 'policy_text'

interface TreeNode {
  id:       string
  type:     NodeType
  label:    string
  sublabel?: string
  status?:  string
  confidence?: number
  children?: TreeNode[]
}

// ─── Config ───────────────────────────────────────────────────────────────────

const STATUS_CFG: Record<string, { color: string; Icon: React.ElementType }> = {
  MET:            { color: '#10b981', Icon: CheckCircle2 },
  NOT_MET:        { color: '#ef4444', Icon: XCircle },
  INSUFFICIENT:   { color: '#f59e0b', Icon: MinusCircle },
  NOT_APPLICABLE: { color: '#6b7280', Icon: MinusCircle },
}

const NODE_TYPE_CFG: Record<NodeType, { color: string; Icon: React.ElementType }> = {
  root:        { color: '#10b981', Icon: CheckCircle2 },
  criterion:   { color: '#6366f1', Icon: Stethoscope },
  evidence:    { color: '#0ea5e9', Icon: FileText },
  policy_text: { color: '#a855f7', Icon: Link2 },
}

// ─── Build tree ───────────────────────────────────────────────────────────────

function buildTree(policyNodes: PolicyNode[], evidenceNodes: EvidenceNode[], mappings: EvidenceMapping[]): TreeNode {
  const criterionChildren: TreeNode[] = policyNodes.map((p) => {
    const linkedEvidenceIds = mappings
      .filter((m) => m.policyId === p.id)
      .map((m) => m.evidenceId)

    const evidenceChildren: TreeNode[] = evidenceNodes
      .filter((e) => linkedEvidenceIds.includes(e.id))
      .map((e) => ({
        id:       `e-${e.id}`,
        type:     'evidence' as NodeType,
        label:    e.label,
        sublabel: e.value,
        confidence: e.confidence,
      }))

    const policyTextChild: TreeNode = {
      id:       `pt-${p.id}`,
      type:     'policy_text',
      label:    'Policy Requirement',
      sublabel: p.requirement,
    }

    return {
      id:         `c-${p.id}`,
      type:       'criterion',
      label:      p.label,
      sublabel:   `weight ${p.weight.toFixed(2)}`,
      status:     p.status,
      confidence: p.confidence,
      children:   [policyTextChild, ...evidenceChildren],
    }
  })

  return {
    id:       'root',
    type:     'root',
    label:    'APPROVED — TKA (CPT 27447)',
    sublabel: '5/5 criteria met · confidence 94.1%',
    confidence: 0.941,
    children: criterionChildren,
  }
}

// ─── Tree node ────────────────────────────────────────────────────────────────

interface NodeProps {
  node:       TreeNode
  depth:      number
  expanded:   Set<string>
  onToggle:   (id: string) => void
}

function TreeNodeRow({ node, depth, expanded, onToggle }: NodeProps) {
  const isExpanded  = expanded.has(node.id)
  const hasChildren = node.children && node.children.length > 0

  const typeCfg   = NODE_TYPE_CFG[node.type]
  const statusCfg = node.status ? STATUS_CFG[node.status] : null
  const color     = statusCfg?.color ?? typeCfg.color
  const Icon      = statusCfg?.Icon  ?? typeCfg.Icon

  return (
    <div>
      <motion.div
        initial={{ opacity: 0, x: -8 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.25, delay: depth * 0.04 }}
        className="flex items-start gap-1.5 py-1 rounded-lg px-2 cursor-pointer hover:bg-[var(--elevated)] transition-colors group"
        style={{ paddingLeft: depth === 0 ? 8 : depth * 16 + 8 }}
        onClick={() => hasChildren && onToggle(node.id)}
      >
        {/* Expand toggle */}
        <div className="w-4 h-4 flex items-center justify-center mt-0.5 shrink-0">
          {hasChildren ? (
            <motion.div
              animate={{ rotate: isExpanded ? 90 : 0 }}
              transition={{ duration: 0.15 }}
            >
              <ChevronRight className="w-3.5 h-3.5 text-[var(--text-4)]" />
            </motion.div>
          ) : (
            <div className="w-1.5 h-1.5 rounded-full" style={{ background: color, opacity: 0.5 }} />
          )}
        </div>

        {/* Icon */}
        <div
          className="w-5 h-5 rounded-md flex items-center justify-center shrink-0 mt-0.5"
          style={{ background: `${color}20` }}
        >
          <Icon style={{ color, width: 11, height: 11 }} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={`leading-tight ${depth === 0 ? 'text-sm font-bold' : depth === 1 ? 'text-xs font-semibold' : 'text-[11px] font-medium'}`}
              style={{ color: depth === 0 ? color : 'var(--text-1)' }}
            >
              {node.label}
            </span>
            {node.confidence !== undefined && depth <= 1 && (
              <span
                className="text-[9px] font-mono tabular-nums px-1.5 py-0.5 rounded-md"
                style={{
                  background: `${color}15`,
                  color,
                }}
              >
                {(node.confidence * 100).toFixed(0)}%
              </span>
            )}
            {node.status && (
              <span
                className="text-[9px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded-md"
                style={{ background: `${color}20`, color }}
              >
                {node.status.replace('_', ' ')}
              </span>
            )}
          </div>
          {node.sublabel && (
            <p className="text-[10px] text-[var(--text-4)] mt-0.5 leading-snug truncate">
              {node.sublabel}
            </p>
          )}
        </div>
      </motion.div>

      {/* Children */}
      <AnimatePresence initial={false}>
        {hasChildren && isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            {/* Connector line */}
            <div
              className="relative"
              style={{ marginLeft: depth * 16 + 24 }}
            >
              <div
                className="absolute left-2 top-0 bottom-0 w-px"
                style={{ background: `${color}30` }}
              />
              <div className="pl-5">
                {node.children!.map((child) => (
                  <TreeNodeRow
                    key={child.id}
                    node={child}
                    depth={depth + 1}
                    expanded={expanded}
                    onToggle={onToggle}
                  />
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  policyNodes:   PolicyNode[]
  evidenceNodes: EvidenceNode[]
  mappings:      EvidenceMapping[]
}

export function RationaleTree({ policyNodes, evidenceNodes, mappings }: Props) {
  const root = buildTree(policyNodes, evidenceNodes, mappings)

  const allIds = [root.id, ...(root.children ?? []).map((c) => c.id)]
  const [expanded, setExpanded] = useState<Set<string>>(new Set(allIds))

  function toggleNode(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function expandAll()   { setExpanded(new Set(allIds)) }
  function collapseAll() { setExpanded(new Set([root.id])) }

  return (
    <div
      className="rounded-2xl overflow-hidden flex flex-col h-full"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      {/* Header */}
      <div
        className="px-4 py-3 border-b border-[var(--border)] flex items-center justify-between shrink-0"
        style={{ background: 'var(--elevated)' }}
      >
        <span className="text-sm font-semibold text-[var(--text-1)]">Rationale Tree</span>
        <div className="flex items-center gap-2">
          <button
            onClick={expandAll}
            className="text-[10px] text-[var(--text-4)] hover:text-[var(--text-2)] transition-colors"
          >
            Expand all
          </button>
          <span className="text-[var(--border)]">·</span>
          <button
            onClick={collapseAll}
            className="text-[10px] text-[var(--text-4)] hover:text-[var(--text-2)] transition-colors"
          >
            Collapse
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        <TreeNodeRow
          node={root}
          depth={0}
          expanded={expanded}
          onToggle={toggleNode}
        />
      </div>
    </div>
  )
}
