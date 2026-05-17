import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, Sparkles, Shield, BookOpen, FolderOpen, ClipboardList, Loader2, ChevronRight, Zap } from 'lucide-react'
import type { SearchResult, ChunkType } from '../hooks/usePolicyManager'

const TYPE_CFG: Record<ChunkType, { color: string; icon: React.ElementType; label: string }> = {
  criterion:     { color: '#6366f1', icon: Shield,      label: 'Criterion' },
  exclusion:     { color: '#ef4444', icon: Shield,      label: 'Exclusion' },
  definition:    { color: '#0ea5e9', icon: BookOpen,    label: 'Definition' },
  coverage:      { color: '#10b981', icon: FolderOpen,  label: 'Coverage' },
  documentation: { color: '#f59e0b', icon: ClipboardList, label: 'Documentation' },
}

const EXAMPLE_QUERIES = [
  'BMI requirements for TKA',
  'physical therapy failure criteria',
  'conservative treatment minimum duration',
  'cardiac clearance documentation',
  'Kellgren-Lawrence grade III',
  'bilateral procedure authorization',
  'WOMAC score threshold',
  'exclusion inflammatory arthropathy',
]

function ScoreBar({ score }: { score: number }) {
  const color = score >= 0.75 ? '#10b981' : score >= 0.55 ? '#6366f1' : '#f59e0b'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1 rounded-full overflow-hidden" style={{ background: 'var(--surface)' }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${score * 100}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="h-full rounded-full"
          style={{ background: color }}
        />
      </div>
      <span className="text-[9px] font-mono font-bold shrink-0" style={{ color }}>
        {(score * 100).toFixed(0)}%
      </span>
    </div>
  )
}

function ResultCard({ result, rank }: { result: SearchResult; rank: number }) {
  const [expanded, setExpanded] = useState(false)
  const cfg = TYPE_CFG[result.chunkType]
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: rank * 0.05 }}
      className="rounded-xl overflow-hidden"
      style={{ background: 'var(--elevated)', border: `1px solid ${cfg.color}25` }}
    >
      <button
        className="w-full flex items-start gap-3 p-3 text-left"
        onClick={() => setExpanded((v) => !v)}
      >
        {/* Rank */}
        <div
          className="w-6 h-6 rounded-full flex items-center justify-center text-[9px] font-bold shrink-0 mt-0.5"
          style={{ background: `${cfg.color}20`, color: cfg.color }}
        >
          {rank + 1}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 mb-1">
            <div className="flex items-center gap-1.5">
              <cfg.icon className="w-3 h-3 shrink-0" style={{ color: cfg.color }} />
              <span className="text-[9px] font-bold uppercase tracking-wide" style={{ color: cfg.color }}>{cfg.label}</span>
              <span className="text-[8px] text-[var(--text-4)] font-mono">· {result.policyName}</span>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <span className="text-[8px] text-[var(--text-4)]">{result.pageRef} · {result.sectionRef}</span>
              <ChevronRight className="w-3 h-3 text-[var(--text-4)]" style={{ transform: expanded ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s' }} />
            </div>
          </div>
          <ScoreBar score={result.score} />
          <p className="text-[9px] text-[var(--text-2)] mt-1.5 leading-relaxed line-clamp-2">{result.chunkText}</p>
        </div>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-[var(--border)]"
          >
            <div className="p-3 pt-2">
              <p className="text-[10px] text-[var(--text-1)] leading-relaxed">{result.chunkText}</p>
              <div className="flex items-center gap-3 mt-2">
                <span className="text-[8px] text-[var(--text-4)]">Policy: <span className="text-[var(--text-2)] font-semibold">{result.policyName}</span></span>
                <span className="text-[8px] text-[var(--text-4)]">Similarity: <span className="text-[var(--text-2)] font-mono font-semibold">{(result.score * 100).toFixed(1)}%</span></span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

interface SemanticSearchProps {
  query:      string
  results:    SearchResult[]
  isSearching: boolean
  onQueryChange: (q: string) => void
  onSearch:   () => void
}

export function SemanticSearch({ query, results, isSearching, onQueryChange, onSearch }: SemanticSearchProps) {
  const hasResults = results.length > 0

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') onSearch()
  }

  return (
    <div className="flex flex-col h-full p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: '#8b5cf615', border: '1px solid #8b5cf630' }}>
          <Sparkles className="w-3.5 h-3.5 text-violet-400" />
        </div>
        <div>
          <p className="text-[11px] font-bold text-[var(--text-1)]">Semantic Search Testing</p>
          <p className="text-[9px] text-[var(--text-4)]">Test retrieval quality across all indexed policy chunks</p>
        </div>
      </div>

      {/* Search input */}
      <div>
        <div
          className="flex items-center gap-2 px-3 py-2.5 rounded-xl transition-all"
          style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
        >
          <Search className="w-4 h-4 text-[var(--text-4)] shrink-0" />
          <input
            className="flex-1 bg-transparent text-sm text-[var(--text-1)] placeholder:text-[var(--text-4)] outline-none"
            placeholder="Enter a clinical query to test retrieval…"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <motion.button
            whileTap={{ scale: 0.95 }}
            onClick={onSearch}
            disabled={!query.trim() || isSearching}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold text-white shrink-0 disabled:opacity-50"
            style={{ background: '#8b5cf6' }}
          >
            {isSearching ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
            {isSearching ? 'Searching…' : 'Search'}
          </motion.button>
        </div>

        {/* Example chips */}
        {!hasResults && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {EXAMPLE_QUERIES.map((q) => (
              <button
                key={q}
                onClick={() => { onQueryChange(q); }}
                className="px-2 py-1 rounded-full text-[9px] font-medium transition-colors hover:bg-[#8b5cf620] hover:text-violet-400"
                style={{ background: 'var(--elevated)', border: '1px solid var(--border)', color: 'var(--text-4)' }}
              >
                {q}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Stats bar */}
      <AnimatePresence>
        {hasResults && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="flex items-center gap-4 px-3 py-2 rounded-xl"
            style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
          >
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span className="text-[9px] font-semibold text-[var(--text-2)]">{results.length} results</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="text-[9px] text-[var(--text-4)]">Top score:</span>
              <span className="text-[9px] font-mono font-bold text-emerald-400">{(results[0]?.score * 100).toFixed(1)}%</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="text-[9px] text-[var(--text-4)]">Avg score:</span>
              <span className="text-[9px] font-mono font-bold text-[var(--text-2)]">
                {((results.reduce((s, r) => s + r.score, 0) / results.length) * 100).toFixed(1)}%
              </span>
            </div>
            {/* Type breakdown */}
            <div className="flex items-center gap-2 ml-auto">
              {(Object.keys(TYPE_CFG) as ChunkType[]).map((t) => {
                const count = results.filter((r) => r.chunkType === t).length
                if (count === 0) return null
                const cfg = TYPE_CFG[t]
                return (
                  <span key={t} className="flex items-center gap-1 text-[8px]" style={{ color: cfg.color }}>
                    <cfg.icon className="w-2.5 h-2.5" />
                    {count}
                  </span>
                )
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Score distribution */}
      {hasResults && (
        <div className="grid grid-cols-3 gap-2">
          {[
            { label: 'High (≥75%)', count: results.filter((r) => r.score >= 0.75).length, color: '#10b981' },
            { label: 'Mid (55–75%)', count: results.filter((r) => r.score >= 0.55 && r.score < 0.75).length, color: '#6366f1' },
            { label: 'Low (<55%)', count: results.filter((r) => r.score < 0.55).length, color: '#f59e0b' },
          ].map((band) => (
            <div key={band.label} className="rounded-lg p-2 text-center"
                 style={{ background: `${band.color}10`, border: `1px solid ${band.color}25` }}>
              <p className="text-lg font-bold font-mono" style={{ color: band.color }}>{band.count}</p>
              <p className="text-[8px] text-[var(--text-4)]">{band.label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Results */}
      <div className="flex-1 overflow-y-auto space-y-2">
        <AnimatePresence mode="wait">
          {isSearching ? (
            <motion.div
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-col items-center justify-center py-12 gap-3"
            >
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
              >
                <Sparkles className="w-6 h-6 text-violet-400" />
              </motion.div>
              <p className="text-[10px] text-[var(--text-4)]">Computing semantic similarity…</p>
            </motion.div>
          ) : hasResults ? (
            <motion.div key="results" className="space-y-2">
              {results.map((r, i) => (
                <ResultCard key={r.chunkId} result={r} rank={i} />
              ))}
            </motion.div>
          ) : (
            <motion.div
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-col items-center justify-center py-16 gap-3"
            >
              <Search className="w-8 h-8 text-[var(--text-4)]" />
              <p className="text-xs text-[var(--text-4)]">Enter a query to test semantic retrieval</p>
              <p className="text-[9px] text-[var(--text-4)]">Results show similarity scores across all policy chunks</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
