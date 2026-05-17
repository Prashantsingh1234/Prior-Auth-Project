import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { BookOpen, Layers, GitBranch, Code2, Search, Edit3, BarChart2, Clock } from 'lucide-react'
import { usePolicyManager } from './hooks/usePolicyManager'
import { PolicyList }       from './components/PolicyList'
import { MetadataEditor }   from './components/MetadataEditor'
import { VersionHistory }   from './components/VersionHistory'
import { ChunkVisualizer }  from './components/ChunkVisualizer'
import { CodeMappings }     from './components/CodeMappings'
import { SemanticSearch }   from './components/SemanticSearch'

// ─── Detail tabs ──────────────────────────────────────────────────────────────

type DetailTab = 'metadata' | 'chunks' | 'versions' | 'codes' | 'search'

const DETAIL_TABS: Array<{ id: DetailTab; label: string; icon: React.ElementType }> = [
  { id: 'metadata', label: 'Metadata',        icon: Edit3 },
  { id: 'chunks',   label: 'Chunk Explorer',  icon: Layers },
  { id: 'versions', label: 'Version History', icon: GitBranch },
  { id: 'codes',    label: 'CPT / ICD',       icon: Code2 },
  { id: 'search',   label: 'Semantic Search', icon: Search },
]

// ─── Policy stat chips ────────────────────────────────────────────────────────

function PolicyStats({ total, active, draft }: { total: number; active: number; draft: number }) {
  return (
    <div className="flex items-center gap-2 px-5 py-2 border-b border-[var(--border)] shrink-0"
         style={{ background: 'rgba(0,0,0,0.08)' }}>
      {[
        { label: 'Total Policies', value: total.toString(), color: '#6366f1' },
        { label: 'Active',         value: active.toString(), color: '#10b981' },
        { label: 'Draft',          value: draft.toString(),  color: '#f59e0b' },
      ].map((s) => (
        <div key={s.label} className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg"
             style={{ background: `${s.color}10`, border: `1px solid ${s.color}20` }}>
          <span className="text-[8px] uppercase tracking-widest font-bold text-[var(--text-4)]">{s.label}</span>
          <span className="text-xs font-bold font-mono" style={{ color: s.color }}>{s.value}</span>
        </div>
      ))}
      <div className="ml-auto flex items-center gap-1 text-[9px] text-[var(--text-4)]">
        <Clock className="w-3 h-3" />
        Last indexed: today
      </div>
    </div>
  )
}

// ─── Retrieval quality badge ──────────────────────────────────────────────────

function RetrievalQualityBadge({ score }: { score: number }) {
  const color = score >= 0.90 ? '#10b981' : score >= 0.82 ? '#6366f1' : '#f59e0b'
  return (
    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg shrink-0"
         style={{ background: `${color}12`, border: `1px solid ${color}30` }}>
      <BarChart2 className="w-3 h-3" style={{ color }} />
      <span className="text-[9px] font-bold font-mono" style={{ color }}>
        {(score * 100).toFixed(1)}% retrieval quality
      </span>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export function PoliciesPage() {
  const pm = usePolicyManager()
  const [detailTab, setDetailTab] = useState<DetailTab>('metadata')

  const { selectedPolicy: policy } = pm

  return (
    <div className="flex flex-col h-full min-h-0 overflow-hidden">

      {/* ── Page header ──────────────────────────────────────────────────────── */}
      <div className="shrink-0 border-b border-[var(--border)]" style={{ background: 'var(--elevated)' }}>
        <div className="flex items-center gap-3 px-5 py-3">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
            style={{ background: '#6366f115', border: '1px solid #6366f130' }}
          >
            <BookOpen className="w-4 h-4 text-[#6366f1]" />
          </div>
          <div>
            <p className="text-sm font-bold text-[var(--text-1)]">Policy Management</p>
            <p className="text-[10px] text-[var(--text-4)]">Upload · Version control · Chunk visualization · Code mapping · Semantic search</p>
          </div>
        </div>
        <PolicyStats
          total={pm.policies.length}
          active={pm.policies.filter((p) => p.status === 'active').length}
          draft={pm.policies.filter((p) => p.status === 'draft').length}
        />
      </div>

      {/* ── Body: list + detail ───────────────────────────────────────────────── */}
      <div className="flex-1 min-h-0 flex overflow-hidden">

        {/* LEFT — Policy list */}
        <div className="w-72 shrink-0 border-r border-[var(--border)] overflow-hidden flex flex-col">
          <PolicyList
            policies={pm.filteredPolicies}
            selectedId={policy?.id ?? ''}
            search={pm.search}
            categoryFilter={pm.categoryFilter}
            statusFilter={pm.statusFilter}
            categories={pm.categories}
            onSelect={pm.setSelectedId}
            onSearchChange={pm.setSearch}
            onCategoryChange={pm.setCategoryFilter}
            onStatusChange={pm.setStatusFilter}
            onUpload={pm.simulateUpload}
            uploadDragging={pm.uploadDragging}
            setUploadDragging={pm.setUploadDragging}
          />
        </div>

        {/* RIGHT — Detail panel */}
        <div className="flex-1 min-w-0 min-h-0 flex flex-col overflow-hidden">
          {policy ? (
            <>
              {/* Policy title bar */}
              <div
                className="shrink-0 px-5 py-3 border-b border-[var(--border)] flex items-center gap-3"
                style={{ background: 'var(--elevated)' }}
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold text-[var(--text-1)] truncate">{policy.name}</p>
                  <p className="text-[9px] text-[var(--text-4)] font-mono">{policy.policyNumber} · v{policy.currentVersion} · {policy.payerName}</p>
                </div>
                <RetrievalQualityBadge score={policy.retrievalQuality} />
                <div className="flex items-center gap-1 shrink-0 text-[9px] text-[var(--text-4)]">
                  <Layers className="w-3 h-3" />
                  {policy.chunkCount} chunks
                </div>
              </div>

              {/* Tab bar */}
              <div
                className="shrink-0 flex items-center gap-1 px-4 py-2 border-b border-[var(--border)]"
                style={{ background: 'var(--surface)' }}
              >
                {DETAIL_TABS.map((tab) => {
                  const isActive = detailTab === tab.id
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setDetailTab(tab.id)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-semibold transition-all"
                      style={{
                        background: isActive ? 'var(--elevated)' : 'transparent',
                        color:      isActive ? 'var(--text-1)' : 'var(--text-4)',
                        border:     `1px solid ${isActive ? 'var(--border)' : 'transparent'}`,
                      }}
                    >
                      <tab.icon className="w-3 h-3" />
                      {tab.label}
                    </button>
                  )
                })}
              </div>

              {/* Tab content */}
              <div className="flex-1 min-h-0 overflow-y-auto">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={`${policy.id}-${detailTab}`}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.15 }}
                    className="h-full"
                  >
                    {detailTab === 'metadata' && (
                      <MetadataEditor
                        policy={policy}
                        onSave={(patch) => pm.updateMetadata(policy.id, patch)}
                      />
                    )}
                    {detailTab === 'chunks' && (
                      <ChunkVisualizer chunks={policy.chunks} />
                    )}
                    {detailTab === 'versions' && (
                      <VersionHistory
                        versions={policy.versions}
                        currentVersion={policy.currentVersion}
                      />
                    )}
                    {detailTab === 'codes' && (
                      <CodeMappings
                        policy={policy}
                        cptPool={pm.CPT_POOL_ALL}
                        icdPool={pm.ICD_POOL_ALL}
                        onAddCPT={(code) => pm.addCPT(policy.id, code)}
                        onRemoveCPT={(code) => pm.removeCPT(policy.id, code)}
                        onAddICD={(code) => pm.addICD(policy.id, code)}
                        onRemoveICD={(code) => pm.removeICD(policy.id, code)}
                      />
                    )}
                    {detailTab === 'search' && (
                      <SemanticSearch
                        query={pm.searchQuery}
                        results={pm.searchResults}
                        isSearching={pm.isSearching}
                        onQueryChange={pm.setSearchQuery}
                        onSearch={pm.runSearch}
                      />
                    )}
                  </motion.div>
                </AnimatePresence>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <BookOpen className="w-10 h-10 text-[var(--text-4)] mx-auto mb-3" />
                <p className="text-sm text-[var(--text-4)]">Select a policy to view details</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
