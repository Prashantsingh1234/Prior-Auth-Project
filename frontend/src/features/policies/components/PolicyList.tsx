import { useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, Upload, BookOpen, CheckCircle2, Clock, Archive, AlertCircle, Tag } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { PolicyDocument, PolicyStatus } from '../hooks/usePolicyManager'

const STATUS_CFG: Record<PolicyStatus, { icon: React.ElementType; color: string; label: string }> = {
  active:       { icon: CheckCircle2, color: '#10b981', label: 'Active' },
  draft:        { icon: Clock,        color: '#f59e0b', label: 'Draft' },
  archived:     { icon: Archive,      color: '#6b7280', label: 'Archived' },
  under_review: { icon: AlertCircle,  color: '#6366f1', label: 'Under Review' },
}

interface PolicyListProps {
  policies:         PolicyDocument[]
  selectedId:       string
  search:           string
  categoryFilter:   string
  statusFilter:     PolicyStatus | 'all'
  categories:       string[]
  onSelect:         (id: string) => void
  onSearchChange:   (v: string) => void
  onCategoryChange: (v: string) => void
  onStatusChange:   (v: PolicyStatus | 'all') => void
  onUpload:         (name: string) => void
  uploadDragging:   boolean
  setUploadDragging:(v: boolean) => void
}

export function PolicyList({
  policies, selectedId, search, categoryFilter, statusFilter, categories,
  onSelect, onSearchChange, onCategoryChange, onStatusChange, onUpload,
  uploadDragging, setUploadDragging,
}: PolicyListProps) {
  const fileRef = useRef<HTMLInputElement>(null)

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setUploadDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) onUpload(file.name)
  }

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) onUpload(file.name)
    e.target.value = ''
  }

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--surface)' }}>
      {/* Upload zone */}
      <div
        className={cn(
          'mx-3 mt-3 rounded-xl border-2 border-dashed transition-all duration-200 cursor-pointer',
          uploadDragging
            ? 'border-[#6366f1] bg-[#6366f112]'
            : 'border-[var(--border)] hover:border-[#6366f180] hover:bg-[var(--elevated)]',
        )}
        onDragOver={(e) => { e.preventDefault(); setUploadDragging(true) }}
        onDragLeave={() => setUploadDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileRef.current?.click()}
      >
        <input ref={fileRef} type="file" accept=".pdf,.doc,.docx" className="hidden" onChange={handleFile} />
        <motion.div
          animate={uploadDragging ? { scale: 1.02 } : { scale: 1 }}
          className="flex flex-col items-center gap-1.5 py-4"
        >
          <Upload className="w-5 h-5" style={{ color: uploadDragging ? '#6366f1' : 'var(--text-4)' }} />
          <span className="text-[10px] font-semibold text-[var(--text-3)]">
            {uploadDragging ? 'Drop to upload' : 'Upload policy (PDF / DOCX)'}
          </span>
          <span className="text-[9px] text-[var(--text-4)]">Drag & drop or click to browse</span>
        </motion.div>
      </div>

      {/* Search */}
      <div className="px-3 pt-3 pb-2 space-y-2">
        <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg"
             style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
          <Search className="w-3.5 h-3.5 text-[var(--text-4)] shrink-0" />
          <input
            className="flex-1 bg-transparent text-xs text-[var(--text-1)] placeholder:text-[var(--text-4)] outline-none"
            placeholder="Search policies…"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-1">
          {(['all', 'active', 'draft', 'under_review', 'archived'] as const).map((s) => (
            <button
              key={s}
              onClick={() => onStatusChange(s)}
              className="px-2 py-0.5 rounded-full text-[9px] font-semibold capitalize transition-colors"
              style={{
                background: statusFilter === s ? '#6366f1' : 'var(--elevated)',
                color:      statusFilter === s ? 'white' : 'var(--text-4)',
                border:     `1px solid ${statusFilter === s ? '#6366f1' : 'var(--border)'}`,
              }}
            >
              {s === 'all' ? 'All' : STATUS_CFG[s as PolicyStatus].label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap gap-1">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => onCategoryChange(cat)}
              className="px-2 py-0.5 rounded-full text-[9px] font-semibold capitalize transition-colors"
              style={{
                background: categoryFilter === cat ? '#0ea5e9' : 'var(--elevated)',
                color:      categoryFilter === cat ? 'white' : 'var(--text-4)',
                border:     `1px solid ${categoryFilter === cat ? '#0ea5e9' : 'var(--border)'}`,
              }}
            >
              {cat === 'all' ? 'All Categories' : cat}
            </button>
          ))}
        </div>
      </div>

      <div className="mx-3 text-[9px] text-[var(--text-4)] px-1 pb-1">{policies.length} polic{policies.length !== 1 ? 'ies' : 'y'}</div>

      {/* List */}
      <div className="flex-1 overflow-y-auto divide-y divide-[var(--border)]">
        <AnimatePresence initial={false}>
          {policies.map((policy) => {
            const sCfg    = STATUS_CFG[policy.status]
            const isActive = policy.id === selectedId
            return (
              <motion.button
                key={policy.id}
                layout
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                onClick={() => onSelect(policy.id)}
                className={cn(
                  'w-full text-left px-3 py-3 transition-colors relative',
                  isActive ? 'bg-[var(--elevated)]' : 'hover:bg-[var(--elevated)]/60',
                )}
              >
                {isActive && (
                  <motion.div
                    layoutId="policy-indicator"
                    className="absolute left-0 top-0 bottom-0 w-0.5 rounded-full"
                    style={{ background: '#6366f1' }}
                  />
                )}
                <div className="flex items-start justify-between gap-2 mb-1">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <BookOpen className="w-3 h-3 shrink-0" style={{ color: isActive ? '#6366f1' : 'var(--text-4)' }} />
                    <span className="text-[11px] font-semibold text-[var(--text-1)] truncate">{policy.name}</span>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <sCfg.icon className="w-2.5 h-2.5" style={{ color: sCfg.color }} />
                    <span className="text-[8px] font-semibold" style={{ color: sCfg.color }}>{sCfg.label}</span>
                  </div>
                </div>
                <p className="text-[9px] text-[var(--text-4)] font-mono mb-1.5">{policy.policyNumber}</p>
                <p className="text-[9px] text-[var(--text-3)] line-clamp-2 mb-2">{policy.description}</p>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[8px] text-[var(--text-4)]">{policy.payerName}</span>
                  <span className="text-[8px] text-[var(--text-4)]">·</span>
                  <span className="text-[8px] text-[var(--text-4)]">v{policy.currentVersion}</span>
                  <span className="text-[8px] text-[var(--text-4)]">·</span>
                  <span className="text-[8px] text-[var(--text-4)]">{policy.chunkCount} chunks</span>
                </div>
                {policy.tags.length > 0 && (
                  <div className="flex items-center gap-1 mt-1.5 flex-wrap">
                    <Tag className="w-2 h-2 text-[var(--text-4)]" />
                    {policy.tags.slice(0, 3).map((t) => (
                      <span key={t} className="px-1.5 py-0.5 rounded-full text-[8px] font-medium bg-[var(--elevated)] text-[var(--text-3)]">{t}</span>
                    ))}
                  </div>
                )}
              </motion.button>
            )
          })}
        </AnimatePresence>
      </div>
    </div>
  )
}
