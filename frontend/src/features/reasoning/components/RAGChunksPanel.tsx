import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FileText, ChevronDown, ChevronRight, Hash } from 'lucide-react'
import type { RetrievedChunk } from '../hooks/useReasoningData'

// ─── Similarity bar ───────────────────────────────────────────────────────────

function SimBar({ sim }: { sim: number }) {
  const color = sim >= 0.9 ? '#10b981' : sim >= 0.8 ? '#6366f1' : sim >= 0.72 ? '#f59e0b' : '#6b7280'
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-20 h-1 rounded-full bg-[var(--border)] overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          initial={{ width: 0 }}
          animate={{ width: `${sim * 100}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          style={{ background: color }}
        />
      </div>
      <span className="text-[9px] font-mono tabular-nums" style={{ color }}>
        {sim.toFixed(3)}
      </span>
    </div>
  )
}

// ─── Chunk card ───────────────────────────────────────────────────────────────

interface ChunkCardProps {
  chunk:     RetrievedChunk
  isExpanded: boolean
  onToggle:  (id: string) => void
  index:     number
}

function ChunkCard({ chunk, isExpanded, onToggle, index }: ChunkCardProps) {
  const usedColor = '#6366f1'

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.25 }}
      className="rounded-xl overflow-hidden"
      style={{ border: '1px solid var(--border)' }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-[var(--elevated)] transition-colors"
        style={{ background: 'var(--surface)' }}
        onClick={() => onToggle(chunk.id)}
      >
        <div className="flex items-center gap-2 min-w-0">
          <FileText className="w-3.5 h-3.5 text-[var(--text-4)] shrink-0" />
          <div className="min-w-0">
            <p className="text-[11px] font-semibold text-[var(--text-1)] truncate">{chunk.sourceDoc}</p>
            <p className="text-[9px] text-[var(--text-4)]">p.{chunk.page} · {chunk.id}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0 ml-2">
          <SimBar sim={chunk.similarity} />
          {isExpanded ? (
            <ChevronDown className="w-3 h-3 text-[var(--text-4)]" />
          ) : (
            <ChevronRight className="w-3 h-3 text-[var(--text-4)]" />
          )}
        </div>
      </div>

      {/* Expanded content */}
      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 'auto' }}
            exit={{ height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div
              className="px-3 pb-3 pt-2 border-t border-[var(--border)] space-y-2"
              style={{ background: 'var(--elevated)' }}
            >
              {/* Quote */}
              <blockquote
                className="text-[11px] text-[var(--text-2)] leading-relaxed pl-2 italic"
                style={{ borderLeft: '2px solid var(--border)' }}
              >
                "{chunk.text}"
              </blockquote>

              {/* Used in */}
              {chunk.usedIn.length > 0 && (
                <div className="flex items-center gap-1.5 flex-wrap">
                  <Hash className="w-3 h-3 text-[var(--text-4)]" />
                  <span className="text-[9px] text-[var(--text-4)]">Used in:</span>
                  {chunk.usedIn.map((cid) => (
                    <span
                      key={cid}
                      className="text-[9px] font-mono px-1.5 py-0.5 rounded-md"
                      style={{ background: `${usedColor}15`, color: usedColor }}
                    >
                      {cid}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  chunks: RetrievedChunk[]
}

export function RAGChunksPanel({ chunks }: Props) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())
  const [sortBy, setSortBy] = useState<'similarity' | 'page'>('similarity')

  function toggleChunk(id: string) {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const sorted = [...chunks].sort((a, b) =>
    sortBy === 'similarity' ? b.similarity - a.similarity : a.page - b.page
  )

  const avgSim = chunks.reduce((s, c) => s + c.similarity, 0) / chunks.length

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
        <div>
          <span className="text-sm font-semibold text-[var(--text-1)]">Retrieved Chunks</span>
          <span className="text-[10px] text-[var(--text-4)] ml-2">
            {chunks.length} chunks · avg sim {avgSim.toFixed(3)}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {(['similarity', 'page'] as const).map((opt) => (
            <button
              key={opt}
              onClick={() => setSortBy(opt)}
              className="text-[9px] font-semibold px-2 py-0.5 rounded-md transition-all capitalize"
              style={{
                background: sortBy === opt ? 'var(--border)' : 'transparent',
                color:      sortBy === opt ? 'var(--text-1)' : 'var(--text-4)',
              }}
            >
              {opt}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
        {sorted.map((chunk, i) => (
          <ChunkCard
            key={chunk.id}
            chunk={chunk}
            isExpanded={expandedIds.has(chunk.id)}
            onToggle={toggleChunk}
            index={i}
          />
        ))}
      </div>
    </div>
  )
}
