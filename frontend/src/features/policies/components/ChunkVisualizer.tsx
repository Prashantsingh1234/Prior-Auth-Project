import { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Shield, BookOpen, FolderOpen, ClipboardList, ZoomIn } from 'lucide-react'
import type { PolicyChunk, ChunkType } from '../hooks/usePolicyManager'

// ─── Type config ──────────────────────────────────────────────────────────────

const TYPE_CFG: Record<ChunkType, { color: string; bg: string; label: string; icon: React.ElementType }> = {
  criterion:     { color: '#6366f1', bg: '#6366f115', label: 'Criterion',     icon: Shield },
  exclusion:     { color: '#ef4444', bg: '#ef444415', label: 'Exclusion',     icon: Shield },
  definition:    { color: '#0ea5e9', bg: '#0ea5e915', label: 'Definition',    icon: BookOpen },
  coverage:      { color: '#10b981', bg: '#10b98115', label: 'Coverage',      icon: FolderOpen },
  documentation: { color: '#f59e0b', bg: '#f59e0b15', label: 'Documentation', icon: ClipboardList },
}

// ─── Chunk card (list view) ───────────────────────────────────────────────────

interface ChunkCardProps {
  chunk:     PolicyChunk
  isActive:  boolean
  onSelect:  () => void
}

function ChunkCard({ chunk, isActive, onSelect }: ChunkCardProps) {
  const cfg = TYPE_CFG[chunk.type]
  return (
    <motion.button
      layout
      onClick={onSelect}
      whileHover={{ x: 2 }}
      className="w-full text-left rounded-xl p-3 transition-all cursor-pointer"
      style={{
        background: isActive ? cfg.bg : 'var(--elevated)',
        border:     `1px solid ${isActive ? cfg.color + '50' : 'var(--border)'}`,
      }}
    >
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-1.5">
          <cfg.icon className="w-3 h-3 shrink-0" style={{ color: cfg.color }} />
          <span className="text-[9px] font-bold uppercase tracking-wide" style={{ color: cfg.color }}>{cfg.label}</span>
          {chunk.criterionRef && (
            <span className="text-[8px] px-1 rounded" style={{ background: cfg.bg, color: cfg.color }}>{chunk.criterionRef}</span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[8px] font-mono text-[var(--text-4)]">{chunk.tokenCount}t</span>
          {chunk.retrievalScore !== undefined && (
            <span
              className="text-[8px] font-mono font-semibold px-1.5 py-0.5 rounded-full"
              style={{
                background: `${chunk.retrievalScore > 0.85 ? '#10b981' : chunk.retrievalScore > 0.72 ? '#6366f1' : '#f59e0b'}18`,
                color:       chunk.retrievalScore > 0.85 ? '#10b981' : chunk.retrievalScore > 0.72 ? '#6366f1' : '#f59e0b',
              }}
            >
              {(chunk.retrievalScore * 100).toFixed(0)}%
            </span>
          )}
        </div>
      </div>
      <p className="text-[9px] text-[var(--text-2)] leading-relaxed line-clamp-3">{chunk.text}</p>
      <div className="flex items-center gap-3 mt-2">
        <span className="text-[8px] text-[var(--text-4)]">{chunk.pageRef}</span>
        <span className="text-[8px] text-[var(--text-4)]">{chunk.sectionRef}</span>
      </div>
    </motion.button>
  )
}

// ─── Embedding scatter plot ───────────────────────────────────────────────────

interface EmbeddingPlotProps {
  chunks:    PolicyChunk[]
  activeId:  string | null
  onSelect:  (id: string) => void
}

function EmbeddingPlot({ chunks, activeId, onSelect }: EmbeddingPlotProps) {
  const [hovered, setHovered] = useState<string | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const W = 420; const H = 300; const PAD = 24

  // Draw relationship lines for active/hovered chunk
  const focal = hovered ?? activeId
  const focalChunk = chunks.find((c) => c.id === focal)

  return (
    <div className="relative">
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        {(Object.keys(TYPE_CFG) as ChunkType[]).map((t) => (
          <span key={t} className="flex items-center gap-1 text-[8px] text-[var(--text-4)]">
            <span className="w-2 h-2 rounded-full inline-block" style={{ background: TYPE_CFG[t].color }} />
            {TYPE_CFG[t].label}
          </span>
        ))}
      </div>
      <svg
        ref={svgRef}
        width="100%"
        viewBox={`0 0 ${W} ${H}`}
        className="rounded-xl overflow-hidden"
        style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
      >
        {/* Grid */}
        {[0.25, 0.5, 0.75].map((t) => (
          <g key={t}>
            <line x1={PAD} y1={PAD + t * (H - PAD * 2)} x2={W - PAD} y2={PAD + t * (H - PAD * 2)} stroke="var(--border)" strokeWidth={0.5} />
            <line x1={PAD + t * (W - PAD * 2)} y1={PAD} x2={PAD + t * (W - PAD * 2)} y2={H - PAD} stroke="var(--border)" strokeWidth={0.5} />
          </g>
        ))}

        {/* Relationship edges */}
        {focalChunk && Object.entries(focalChunk.similarityTo ?? {}).map(([otherId, sim]) => {
          const other = chunks.find((c) => c.id === otherId)
          if (!other || sim < 0.3) return null
          const x1 = PAD + focalChunk.embedding[0] * (W - PAD * 2)
          const y1 = PAD + (1 - focalChunk.embedding[1]) * (H - PAD * 2)
          const x2 = PAD + other.embedding[0] * (W - PAD * 2)
          const y2 = PAD + (1 - other.embedding[1]) * (H - PAD * 2)
          return (
            <line
              key={otherId}
              x1={x1} y1={y1} x2={x2} y2={y2}
              stroke={TYPE_CFG[focalChunk.type].color}
              strokeWidth={sim * 2}
              strokeOpacity={sim * 0.6}
              strokeDasharray={sim > 0.6 ? 'none' : '4 3'}
            />
          )
        })}

        {/* Points */}
        {chunks.map((chunk) => {
          const x = PAD + chunk.embedding[0] * (W - PAD * 2)
          const y = PAD + (1 - chunk.embedding[1]) * (H - PAD * 2)
          const cfg = TYPE_CFG[chunk.type]
          const isActive = chunk.id === activeId
          const isHov    = chunk.id === hovered
          const r = isActive || isHov ? 7 : 5
          return (
            <g key={chunk.id} className="cursor-pointer" onClick={() => onSelect(chunk.id)}
               onMouseEnter={() => setHovered(chunk.id)}
               onMouseLeave={() => setHovered(null)}>
              {(isActive || isHov) && (
                <circle cx={x} cy={y} r={r + 5} fill={cfg.color} fillOpacity={0.15} />
              )}
              <circle
                cx={x} cy={y} r={r}
                fill={cfg.color}
                fillOpacity={isActive || isHov ? 1 : 0.7}
                stroke={isActive ? 'white' : 'transparent'}
                strokeWidth={1.5}
              />
              {chunk.criterionRef && (
                <text x={x} y={y + 3} textAnchor="middle" fontSize={5} fill="white" fontWeight="bold">
                  {chunk.index + 1}
                </text>
              )}
            </g>
          )
        })}

        {/* Axis labels */}
        <text x={W / 2} y={H - 4} textAnchor="middle" fontSize={8} fill="var(--text-4)">Semantic Dimension 1 (PCA)</text>
        <text x={6} y={H / 2} textAnchor="middle" fontSize={8} fill="var(--text-4)" transform={`rotate(-90 6 ${H / 2})`}>Dim 2</text>
      </svg>

      {/* Tooltip on focal */}
      {focalChunk && (
        <div className="absolute top-8 right-2 max-w-[160px] p-2 rounded-lg text-[8px] pointer-events-none z-10"
             style={{ background: 'var(--elevated)', border: `1px solid ${TYPE_CFG[focalChunk.type].color}40` }}>
          <p className="font-bold" style={{ color: TYPE_CFG[focalChunk.type].color }}>{TYPE_CFG[focalChunk.type].label} #{focalChunk.index + 1}</p>
          <p className="text-[var(--text-3)] mt-0.5 leading-tight">{focalChunk.text.slice(0, 80)}…</p>
        </div>
      )}
    </div>
  )
}

// ─── Retrieval quality bar ────────────────────────────────────────────────────

function RetrievalQualityBar({ chunks }: { chunks: PolicyChunk[] }) {
  const bins = [
    { label: '≥90%', min: 0.90, color: '#10b981' },
    { label: '75–90%', min: 0.75, color: '#6366f1' },
    { label: '60–75%', min: 0.60, color: '#f59e0b' },
    { label: '<60%', min: 0, color: '#ef4444' },
  ]

  const counts = bins.map((b, i) => ({
    ...b,
    count: chunks.filter((c) =>
      c.retrievalScore !== undefined &&
      c.retrievalScore >= b.min &&
      (i === 0 || c.retrievalScore < bins[i - 1].min),
    ).length,
  }))

  const total = chunks.filter((c) => c.retrievalScore !== undefined).length

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <ZoomIn className="w-3 h-3 text-[var(--text-4)]" />
        <span className="text-[10px] font-bold text-[var(--text-3)] uppercase tracking-wide">Retrieval Quality Distribution</span>
      </div>
      <div className="w-full h-3 flex rounded-full overflow-hidden">
        {counts.map((b) => (
          <motion.div
            key={b.label}
            initial={{ width: 0 }}
            animate={{ width: total > 0 ? `${(b.count / total) * 100}%` : 0 }}
            transition={{ duration: 0.8, ease: 'easeOut' }}
            style={{ background: b.color }}
            title={`${b.label}: ${b.count} chunks`}
          />
        ))}
      </div>
      <div className="flex items-center gap-4 flex-wrap">
        {counts.map((b) => (
          <span key={b.label} className="flex items-center gap-1.5 text-[9px]">
            <span className="w-2 h-2 rounded-full inline-block" style={{ background: b.color }} />
            <span className="text-[var(--text-4)]">{b.label}</span>
            <span className="font-semibold font-mono text-[var(--text-2)]">{b.count}</span>
          </span>
        ))}
      </div>
    </div>
  )
}

// ─── Chunk type summary ───────────────────────────────────────────────────────

function ChunkTypeSummary({ chunks }: { chunks: PolicyChunk[] }) {
  const counts = (Object.keys(TYPE_CFG) as ChunkType[]).map((t) => ({
    type: t,
    count: chunks.filter((c) => c.type === t).length,
    cfg: TYPE_CFG[t],
  }))
  const total = chunks.length

  return (
    <div className="grid grid-cols-5 gap-2">
      {counts.map(({ type, count, cfg }) => (
        <div key={type} className="rounded-lg p-2 text-center"
             style={{ background: cfg.bg, border: `1px solid ${cfg.color}30` }}>
          <cfg.icon className="w-3 h-3 mx-auto mb-1" style={{ color: cfg.color }} />
          <p className="text-xs font-bold font-mono" style={{ color: cfg.color }}>{count}</p>
          <p className="text-[7px] text-[var(--text-4)] capitalize">{type}</p>
          <p className="text-[7px] font-semibold" style={{ color: cfg.color }}>{total > 0 ? ((count / total) * 100).toFixed(0) : 0}%</p>
        </div>
      ))}
    </div>
  )
}

// ─── Main visualizer ──────────────────────────────────────────────────────────

interface ChunkVisualizerProps {
  chunks: PolicyChunk[]
}

export function ChunkVisualizer({ chunks }: ChunkVisualizerProps) {
  const [activeId, setActiveId] = useState<string | null>(null)
  const [typeFilter, setTypeFilter] = useState<ChunkType | 'all'>('all')
  const [viewMode, setViewMode] = useState<'list' | 'embeddings'>('list')

  const filtered = typeFilter === 'all' ? chunks : chunks.filter((c) => c.type === typeFilter)
  const activeChunk = chunks.find((c) => c.id === activeId) ?? null

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Summary */}
      <ChunkTypeSummary chunks={chunks} />

      {/* Retrieval quality */}
      <div className="rounded-xl p-3" style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
        <RetrievalQualityBar chunks={chunks} />
      </div>

      {/* View toggle + type filter */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-1">
          {(['list', 'embeddings'] as const).map((m) => (
            <button
              key={m}
              onClick={() => setViewMode(m)}
              className="px-3 py-1 rounded-lg text-[9px] font-semibold capitalize transition-all"
              style={{
                background: viewMode === m ? '#6366f1' : 'var(--elevated)',
                color:      viewMode === m ? 'white' : 'var(--text-4)',
                border:     `1px solid ${viewMode === m ? '#6366f1' : 'var(--border)'}`,
              }}
            >
              {m === 'embeddings' ? 'Embedding Space' : 'Chunk List'}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1 flex-wrap">
          <button
            onClick={() => setTypeFilter('all')}
            className="px-2 py-0.5 rounded-full text-[8px] font-semibold transition-colors"
            style={{
              background: typeFilter === 'all' ? 'var(--text-3)' : 'var(--elevated)',
              color:      typeFilter === 'all' ? 'white' : 'var(--text-4)',
              border:     `1px solid ${typeFilter === 'all' ? 'var(--text-3)' : 'var(--border)'}`,
            }}
          >
            All ({chunks.length})
          </button>
          {(Object.keys(TYPE_CFG) as ChunkType[]).map((t) => {
            const count = chunks.filter((c) => c.type === t).length
            const cfg = TYPE_CFG[t]
            return (
              <button
                key={t}
                onClick={() => setTypeFilter(t)}
                className="px-2 py-0.5 rounded-full text-[8px] font-semibold capitalize transition-colors"
                style={{
                  background: typeFilter === t ? cfg.color : 'var(--elevated)',
                  color:      typeFilter === t ? 'white' : 'var(--text-4)',
                  border:     `1px solid ${typeFilter === t ? cfg.color : 'var(--border)'}`,
                }}
              >
                {t} ({count})
              </button>
            )
          })}
        </div>
      </div>

      {/* View content */}
      <AnimatePresence mode="wait">
        {viewMode === 'list' ? (
          <motion.div
            key="list"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="grid grid-cols-1 lg:grid-cols-2 gap-2"
          >
            {filtered.map((chunk) => (
              <ChunkCard
                key={chunk.id}
                chunk={chunk}
                isActive={activeId === chunk.id}
                onSelect={() => setActiveId((v) => v === chunk.id ? null : chunk.id)}
              />
            ))}
          </motion.div>
        ) : (
          <motion.div
            key="embeddings"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="space-y-3"
          >
            <EmbeddingPlot chunks={filtered} activeId={activeId} onSelect={(id) => setActiveId((v) => v === id ? null : id)} />
            {activeChunk && (
              <motion.div
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-xl p-3"
                style={{ background: 'var(--elevated)', border: `1px solid ${TYPE_CFG[activeChunk.type].color}40` }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[9px] font-bold uppercase tracking-wide" style={{ color: TYPE_CFG[activeChunk.type].color }}>
                    {TYPE_CFG[activeChunk.type].label}
                  </span>
                  <span className="text-[8px] text-[var(--text-4)]">{activeChunk.pageRef} · {activeChunk.sectionRef}</span>
                  <span className="text-[8px] font-mono text-[var(--text-4)]">{activeChunk.tokenCount} tokens</span>
                </div>
                <p className="text-[10px] text-[var(--text-2)] leading-relaxed">{activeChunk.text}</p>
                {activeChunk.similarityTo && (
                  <div className="mt-2 pt-2 border-t border-[var(--border)]">
                    <p className="text-[8px] text-[var(--text-4)] mb-1.5">Top similar chunks:</p>
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(activeChunk.similarityTo)
                        .sort((a, b) => b[1] - a[1])
                        .slice(0, 4)
                        .map(([id, sim]) => {
                          const other = chunks.find((c) => c.id === id)
                          if (!other) return null
                          return (
                            <button
                              key={id}
                              onClick={() => setActiveId(id)}
                              className="px-1.5 py-0.5 rounded text-[8px] font-mono transition-colors"
                              style={{ background: TYPE_CFG[other.type].bg, color: TYPE_CFG[other.type].color, border: `1px solid ${TYPE_CFG[other.type].color}30` }}
                            >
                              #{other.index + 1} {(sim * 100).toFixed(0)}%
                            </button>
                          )
                        })}
                    </div>
                  </div>
                )}
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
