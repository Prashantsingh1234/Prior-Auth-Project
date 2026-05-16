import { useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ZoomIn, ZoomOut, ChevronLeft, ChevronRight,
  Maximize2, ScanLine, Layers,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ReviewState, DocEntity, DocPage, PageContent } from '../hooks/useCaseReviewData'

// ─── Entity type config ───────────────────────────────────────────────────────

const ENTITY_CONFIG: Record<DocEntity['type'], {
  bg: string; border: string; text: string; label: string; dot: string
}> = {
  CPT:        { bg: 'rgba(14,165,233,0.18)',  border: 'rgba(14,165,233,0.5)',  text: '#38bdf8', label: 'CPT',  dot: '#0ea5e9' },
  ICD:        { bg: 'rgba(139,92,246,0.18)',  border: 'rgba(139,92,246,0.5)',  text: '#a78bfa', label: 'ICD',  dot: '#8b5cf6' },
  MEDICATION: { bg: 'rgba(16,185,129,0.18)',  border: 'rgba(16,185,129,0.5)',  text: '#34d399', label: 'Rx',   dot: '#10b981' },
  LAB_VALUE:  { bg: 'rgba(245,158,11,0.18)',  border: 'rgba(245,158,11,0.5)',  text: '#fbbf24', label: 'Lab',  dot: '#f59e0b' },
  DATE:       { bg: 'rgba(20,184,166,0.18)',  border: 'rgba(20,184,166,0.5)',  text: '#2dd4bf', label: 'Date', dot: '#14b8a6' },
  PROVIDER:   { bg: 'rgba(249,115,22,0.18)',  border: 'rgba(249,115,22,0.5)',  text: '#fb923c', label: 'MD',   dot: '#f97316' },
  PATIENT:    { bg: 'rgba(236,72,153,0.18)',  border: 'rgba(236,72,153,0.5)',  text: '#f472b6', label: 'Pt',   dot: '#ec4899' },
}

// ─── Entity highlight chip ────────────────────────────────────────────────────

interface EntityChipProps {
  entity:      DocEntity
  highlighted: boolean
  onHover:     (ids: string[]) => void
  onLeave:     () => void
}

function EntityChip({ entity, highlighted, onHover, onLeave }: EntityChipProps) {
  const cfg = ENTITY_CONFIG[entity.type]
  return (
    <motion.span
      onMouseEnter={() => onHover([entity.id])}
      onMouseLeave={onLeave}
      animate={{ scale: highlighted ? 1.04 : 1 }}
      transition={{ duration: 0.15 }}
      className="inline-flex items-center gap-1 mx-0.5 px-1.5 py-0.5 rounded-md cursor-pointer select-none font-mono text-xs"
      style={{
        background: cfg.bg,
        border: `1px solid ${highlighted ? cfg.border : 'transparent'}`,
        color: cfg.text,
        boxShadow: highlighted ? `0 0 10px ${cfg.dot}44` : 'none',
      }}
      title={entity.normalized}
    >
      <span className="text-[8px] font-bold opacity-70">{cfg.label}</span>
      <span>{entity.value}</span>
    </motion.span>
  )
}

// ─── Page content renderers ───────────────────────────────────────────────────

interface ContentRendererProps {
  content:     PageContent
  allEntities: DocEntity[]
  highlighted: string[]
  onHover:     (ids: string[]) => void
  onLeave:     () => void
}

function ContentBlock({ content, allEntities, highlighted, onHover, onLeave }: ContentRendererProps) {
  const entityMap = new Map(allEntities.map((e) => [e.id, e]))

  function renderText(text: string, entityIds?: string[]) {
    if (!entityIds?.length) return <span>{text}</span>

    // Find entities whose values appear in text and wrap them
    let result: (React.ReactNode)[] = [text]
    entityIds.forEach((eid) => {
      const entity = entityMap.get(eid)
      if (!entity) return
      const next: React.ReactNode[] = []
      result.forEach((part, pi) => {
        if (typeof part !== 'string') { next.push(part); return }
        const idx = part.indexOf(entity.value)
        if (idx === -1) { next.push(part); return }
        next.push(part.slice(0, idx))
        next.push(
          <EntityChip
            key={`${eid}-${pi}`}
            entity={entity}
            highlighted={highlighted.includes(eid)}
            onHover={onHover}
            onLeave={onLeave}
          />
        )
        next.push(part.slice(idx + entity.value.length))
      })
      result = next
    })
    return <>{result}</>
  }

  switch (content.type) {
    case 'heading':
      return (
        <h2 className="text-sm font-bold text-[var(--text-1)] tracking-wide uppercase mb-1">
          {content.text}
        </h2>
      )
    case 'subheading':
      return (
        <h3 className="text-[11px] font-semibold text-[var(--text-3)] uppercase tracking-wider mt-3 mb-1">
          {content.text}
        </h3>
      )
    case 'divider':
      return <div className="border-t border-[var(--border)] my-3" />

    case 'paragraph':
      return (
        <p className="text-[12px] leading-relaxed text-[var(--text-2)] mb-2">
          {renderText(content.text ?? '', content.entityIds)}
        </p>
      )

    case 'field-row':
      return (
        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 mb-3">
          {content.rows?.map((row, i) => {
            const entity = row.entityId ? entityMap.get(row.entityId) : null
            return (
              <div key={i} className="flex flex-col gap-0.5">
                <span className="text-[9px] text-[var(--text-4)] uppercase tracking-wider">{row.label}</span>
                <span className="text-[11px] text-[var(--text-1)] font-medium">
                  {entity ? (
                    <EntityChip
                      entity={entity}
                      highlighted={highlighted.includes(entity.id)}
                      onHover={onHover}
                      onLeave={onLeave}
                    />
                  ) : row.value}
                </span>
              </div>
            )
          })}
        </div>
      )

    case 'table':
      return (
        <div className="rounded-lg overflow-hidden border border-[var(--border)] mb-3">
          {content.rows?.map((row, i) => {
            const entity = row.entityId ? entityMap.get(row.entityId) : null
            const isHighlighted = entity ? highlighted.includes(entity.id) : false
            return (
              <div
                key={i}
                className={cn(
                  'flex items-start gap-3 px-3 py-2 text-[11px] border-b border-[var(--border)] last:border-0 transition-colors',
                  isHighlighted && 'bg-[var(--elevated)]'
                )}
              >
                <span className="text-[var(--text-4)] w-32 flex-shrink-0 font-medium">{row.label}</span>
                <span className="text-[var(--text-1)] flex-1 font-mono">
                  {entity ? (
                    <EntityChip
                      entity={entity}
                      highlighted={isHighlighted}
                      onHover={onHover}
                      onLeave={onLeave}
                    />
                  ) : row.value}
                </span>
              </div>
            )
          })}
        </div>
      )

    default: return null
  }
}

// ─── Document page ────────────────────────────────────────────────────────────

function DocumentPage({ page, allEntities, highlighted, onHover, onLeave }: {
  page:        DocPage
  allEntities: DocEntity[]
  highlighted: string[]
  onHover:     (ids: string[]) => void
  onLeave:     () => void
}) {
  const pageEntities = allEntities.filter((e) => e.pageIndex === page.index)

  return (
    <div
      className="w-full mx-auto rounded-xl overflow-hidden shadow-xl"
      style={{
        background: 'white',
        border: '1px solid rgba(0,0,0,0.1)',
        minHeight: 640,
        maxWidth: 680,
        padding: '40px 44px',
        color: '#1a1a2e',
        fontFamily: '"Georgia", serif',
        position: 'relative',
      }}
    >
      {/* OCR scan overlay indicator */}
      <div
        className="absolute top-3 right-3 flex items-center gap-1.5 px-2 py-1 rounded-lg text-[9px] font-medium"
        style={{ background: 'rgba(16,185,129,0.1)', color: '#10b981', border: '1px solid rgba(16,185,129,0.2)' }}
      >
        <ScanLine className="w-2.5 h-2.5" />
        OCR · {Math.round(98 + Math.sin(page.index) * 0.7)}% confidence
      </div>

      {/* Page header watermark */}
      <div className="absolute top-3 left-3 text-[9px] text-gray-400 font-mono">
        {page.docType.replace(/_/g, ' ')} · PAGE {page.index + 1}
      </div>

      {/* Content */}
      <div className="mt-6">
        {page.content.map((block, i) => (
          <ContentBlock
            key={i}
            content={block}
            allEntities={allEntities}
            highlighted={highlighted}
            onHover={onHover}
            onLeave={onLeave}
          />
        ))}
      </div>

      {/* Entity legend at bottom */}
      {pageEntities.length > 0 && (
        <div className="mt-6 pt-4 border-t border-gray-200">
          <p className="text-[8px] text-gray-400 uppercase tracking-wider mb-2">AI-Extracted Entities</p>
          <div className="flex flex-wrap gap-1.5">
            {pageEntities.map((e) => (
              <EntityChip
                key={e.id}
                entity={e}
                highlighted={highlighted.includes(e.id)}
                onHover={onHover}
                onLeave={onLeave}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Thumbnail strip ──────────────────────────────────────────────────────────

function ThumbnailStrip({ pages, activePage, onSelect }: {
  pages: DocPage[]; activePage: number; onSelect: (i: number) => void
}) {
  return (
    <div className="flex flex-col gap-2 py-3 px-2 overflow-y-auto" style={{ maxHeight: '100%' }}>
      {pages.map((_page, i) => (
        <button
          key={i}
          onClick={() => onSelect(i)}
          className={cn(
            'relative flex-shrink-0 rounded-lg overflow-hidden border-2 transition-all',
            activePage === i
              ? 'border-cyan-500 shadow-lg shadow-cyan-500/20'
              : 'border-[var(--border)] hover:border-[var(--text-4)]',
          )}
          style={{ width: 72, height: 88, background: 'white' }}
        >
          <div className="absolute inset-0 p-1.5">
            <div className="w-full h-1 rounded bg-gray-300 mb-1" />
            <div className="w-3/4 h-0.5 rounded bg-gray-200 mb-0.5" />
            <div className="w-full h-0.5 rounded bg-gray-200 mb-0.5" />
            <div className="w-2/3 h-0.5 rounded bg-gray-200 mb-1" />
            <div className="w-full h-0.5 rounded bg-gray-200 mb-0.5" />
            <div className="w-4/5 h-0.5 rounded bg-gray-200" />
          </div>
          <div className="absolute bottom-1 left-0 right-0 text-center">
            <span className="text-[7px] font-medium" style={{ color: activePage === i ? '#0ea5e9' : '#888' }}>
              {i + 1}
            </span>
          </div>
          {activePage === i && (
            <div className="absolute inset-0 rounded-lg ring-2 ring-cyan-500/50 pointer-events-none" />
          )}
        </button>
      ))}
    </div>
  )
}

// ─── Entity legend ────────────────────────────────────────────────────────────

function EntityLegend() {
  return (
    <div className="flex items-center gap-2 flex-wrap px-4 py-1.5 border-b border-[var(--border)]"
      style={{ background: 'var(--elevated)' }}>
      <span className="text-[9px] text-[var(--text-4)] font-medium uppercase tracking-wider mr-1">AI Entities</span>
      {(Object.entries(ENTITY_CONFIG) as [DocEntity['type'], typeof ENTITY_CONFIG[DocEntity['type']]][]).map(([type, cfg]) => (
        <div key={type} className="flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: cfg.dot }} />
          <span className="text-[9px] text-[var(--text-4)]">{cfg.label}</span>
        </div>
      ))}
    </div>
  )
}

// ─── Main panel ───────────────────────────────────────────────────────────────

interface Props {
  state: ReviewState
}

export function DocumentPanel({ state }: Props) {
  const { pages, entities, activePage, zoom, highlightedEntityIds, setPage, setZoom, highlightEntity, clearHighlight } = state
  const containerRef = useRef<HTMLDivElement>(null)
  const page = pages[activePage]

  const zoomIn  = () => setZoom(Math.min(zoom + 0.15, 2))
  const zoomOut = () => setZoom(Math.max(zoom - 0.15, 0.5))

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg)' }}>

      {/* Toolbar */}
      <div
        className="flex items-center gap-2 px-4 py-2 border-b border-[var(--border)] flex-shrink-0"
        style={{ background: 'var(--surface)' }}
      >
        {/* Page navigation */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setPage(Math.max(0, activePage - 1))}
            disabled={activePage === 0}
            className="p-1.5 rounded-lg text-[var(--text-3)] hover:bg-[var(--elevated)] disabled:opacity-30 transition-colors"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
          </button>
          <span className="text-xs text-[var(--text-2)] tabular-nums px-2">
            {activePage + 1} / {pages.length}
          </span>
          <button
            onClick={() => setPage(Math.min(pages.length - 1, activePage + 1))}
            disabled={activePage === pages.length - 1}
            className="p-1.5 rounded-lg text-[var(--text-3)] hover:bg-[var(--elevated)] disabled:opacity-30 transition-colors"
          >
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="w-px h-4 bg-[var(--border)]" />

        {/* Document title */}
        <span className="text-xs font-medium text-[var(--text-2)] flex-1 min-w-0 truncate">
          {page?.label}
        </span>

        {/* Zoom controls */}
        <div className="flex items-center gap-1 bg-[var(--elevated)] rounded-lg p-1 border border-[var(--border)]">
          <button onClick={zoomOut} className="p-1 rounded hover:bg-[var(--surface)] text-[var(--text-3)] hover:text-[var(--text-1)] transition-colors">
            <ZoomOut className="w-3 h-3" />
          </button>
          <span className="text-[10px] font-mono text-[var(--text-3)] px-1 w-10 text-center tabular-nums">
            {Math.round(zoom * 100)}%
          </span>
          <button onClick={zoomIn} className="p-1 rounded hover:bg-[var(--surface)] text-[var(--text-3)] hover:text-[var(--text-1)] transition-colors">
            <ZoomIn className="w-3 h-3" />
          </button>
        </div>

        <button
          onClick={() => setZoom(1)}
          className="p-1.5 rounded-lg text-[var(--text-4)] hover:bg-[var(--elevated)] hover:text-[var(--text-2)] transition-colors"
          title="Reset zoom"
        >
          <Maximize2 className="w-3.5 h-3.5" />
        </button>

        <button
          className="flex items-center gap-1.5 px-2 py-1 rounded-lg text-[9px] font-medium text-[var(--text-3)] hover:bg-[var(--elevated)] transition-colors border border-[var(--border)]"
        >
          <Layers className="w-3 h-3" />
          <span className="hidden sm:inline">Overlays</span>
        </button>
      </div>

      {/* Entity legend */}
      <EntityLegend />

      {/* Main content area */}
      <div className="flex flex-1 min-h-0">

        {/* Thumbnail sidebar */}
        <div
          className="w-20 flex-shrink-0 border-r border-[var(--border)] overflow-hidden"
          style={{ background: 'var(--bg)' }}
        >
          <ThumbnailStrip pages={pages} activePage={activePage} onSelect={setPage} />
        </div>

        {/* Scrollable document area */}
        <div
          ref={containerRef}
          className="flex-1 overflow-auto p-6"
          style={{ background: 'var(--bg)' }}
        >
          <AnimatePresence mode="wait">
            <motion.div
              key={activePage}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
              style={{
                transform: `scale(${zoom})`,
                transformOrigin: 'top center',
                marginBottom: zoom > 1 ? `${(zoom - 1) * 640}px` : 0,
              }}
            >
              {page && (
                <DocumentPage
                  page={page}
                  allEntities={entities}
                  highlighted={highlightedEntityIds}
                  onHover={highlightEntity}
                  onLeave={clearHighlight}
                />
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
