import { useState, useCallback, useRef } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import {
  ZoomIn, ZoomOut, ChevronLeft, ChevronRight, Maximize2, Download,
} from 'lucide-react'
import { clsx } from 'clsx'
import type { CaseDocument, ExtractedEntity, BoundingBox } from '@/api/types'
import { useReviewStore } from '@/store/reviewStore'
import { PanelLoader } from '@/components/common/LoadingSpinner'
import { apiClient } from '@/api/client'

// Use bundled worker to avoid CORS issues
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

interface DocumentViewerProps {
  caseId: string
  documents: CaseDocument[]
  entities: ExtractedEntity[]
}

export function DocumentViewer({ caseId, documents, entities }: DocumentViewerProps) {
  const [selectedDocId, setSelectedDocId] = useState(documents[0]?.document_id ?? null)
  const [pdfUrl, setPdfUrl]               = useState<string | null>(null)
  const [loadError, setLoadError]         = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const {
    currentPage, totalPages, zoom,
    setCurrentPage, setTotalPages, setZoom,
    highlightedEntityId,
  } = useReviewStore()

  const selectedDoc = documents.find((d) => d.document_id === selectedDocId)

  // Fetch document blob when selection changes
  const loadDocument = useCallback(async (docId: string) => {
    try {
      setLoadError(null)
      const response = await apiClient.get(`/cases/${caseId}/documents/${docId}`, {
        responseType: 'blob',
      })
      const url = URL.createObjectURL(response.data as Blob)
      setPdfUrl(url)
    } catch {
      setLoadError('Failed to load document. Please try again.')
    }
  }, [caseId])

  const handleDocSelect = (docId: string) => {
    setSelectedDocId(docId)
    setCurrentPage(1)
    loadDocument(docId)
  }

  // Entities on the current page that should be highlighted
  const pageEntities = entities.filter(
    (e) => e.bounding_box?.page === currentPage,
  )
  const highlightedEntity = entities.find((e) => e.entity_id === highlightedEntityId)

  return (
    <div className="flex flex-col h-full bg-slate-800 rounded-xl overflow-hidden">
      {/* Document tabs */}
      {documents.length > 1 && (
        <div className="flex bg-slate-900 border-b border-slate-700 overflow-x-auto flex-shrink-0">
          {documents.map((doc) => (
            <button
              key={doc.document_id}
              onClick={() => handleDocSelect(doc.document_id)}
              className={clsx(
                'px-3 py-2.5 text-xs font-medium whitespace-nowrap border-r border-slate-700 transition-colors',
                doc.document_id === selectedDocId
                  ? 'bg-slate-700 text-white'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800',
              )}
            >
              {doc.document_type.replace(/_/g, ' ')}
              {doc.ocr_confidence != null && (
                <span className={clsx('ml-1.5 text-xs', doc.ocr_confidence >= 0.85 ? 'text-green-400' : 'text-amber-400')}>
                  {Math.round(doc.ocr_confidence * 100)}%
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-2 bg-slate-900 border-b border-slate-700 flex-shrink-0">
        {/* Page navigation */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
            disabled={currentPage <= 1}
            className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-700 disabled:opacity-40 transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-xs text-slate-300 tabular-nums min-w-[4rem] text-center">
            {currentPage} / {totalPages}
          </span>
          <button
            onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
            disabled={currentPage >= totalPages}
            className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-700 disabled:opacity-40 transition-colors"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        <div className="h-4 w-px bg-slate-700" />

        {/* Zoom controls */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setZoom(zoom - 0.15)}
            disabled={zoom <= 0.5}
            className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-700 disabled:opacity-40 transition-colors"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <span className="text-xs text-slate-300 tabular-nums w-10 text-center">
            {Math.round(zoom * 100)}%
          </span>
          <button
            onClick={() => setZoom(zoom + 0.15)}
            disabled={zoom >= 3.0}
            className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-700 disabled:opacity-40 transition-colors"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1" />

        {/* OCR confidence */}
        {selectedDoc?.ocr_confidence != null && (
          <span className={clsx(
            'text-xs font-medium px-2 py-0.5 rounded',
            selectedDoc.ocr_confidence >= 0.85 ? 'text-green-400 bg-green-900/30' :
            selectedDoc.ocr_confidence >= 0.65 ? 'text-amber-400 bg-amber-900/30' :
            'text-red-400 bg-red-900/30',
          )}>
            OCR {Math.round(selectedDoc.ocr_confidence * 100)}%
          </span>
        )}

        <button className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-700 transition-colors">
          <Download className="w-4 h-4" />
        </button>
      </div>

      {/* PDF canvas */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto flex justify-center py-4 px-2 relative"
        style={{ background: '#525659' }}
      >
        {loadError ? (
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <p className="text-slate-300 text-sm">{loadError}</p>
            <button
              onClick={() => selectedDocId && loadDocument(selectedDocId)}
              className="px-4 py-2 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700"
            >
              Retry
            </button>
          </div>
        ) : !pdfUrl ? (
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <PanelLoader />
            <button
              onClick={() => selectedDocId && loadDocument(selectedDocId)}
              className="px-4 py-2 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700"
            >
              Load Document
            </button>
          </div>
        ) : (
          <div className="relative">
            <Document
              file={pdfUrl}
              onLoadSuccess={({ numPages }) => setTotalPages(numPages)}
              loading={<PanelLoader />}
              error={<div className="text-red-400 text-sm p-4">Failed to render PDF.</div>}
            >
              <Page
                pageNumber={currentPage}
                scale={zoom}
                loading={<PanelLoader />}
                renderTextLayer={true}
                renderAnnotationLayer={true}
              />
            </Document>

            {/* Entity highlight overlays */}
            {pageEntities.map((entity) => (
              <EntityOverlay
                key={entity.entity_id}
                entity={entity}
                isHighlighted={entity.entity_id === highlightedEntityId}
                zoom={zoom}
              />
            ))}
          </div>
        )}
      </div>

      {/* Highlighted entity info bar */}
      {highlightedEntity && (
        <div className="flex items-center gap-2 px-4 py-2 bg-yellow-900/40 border-t border-yellow-700/50 flex-shrink-0">
          <span className="text-yellow-400 text-xs font-medium">
            Highlighting:
          </span>
          <span className="text-yellow-200 text-xs font-semibold">
            {highlightedEntity.entity_type.replace(/_/g, ' ')}
          </span>
          <span className="text-yellow-300 text-xs">—</span>
          <span className="text-yellow-100 text-xs truncate">{highlightedEntity.value}</span>
          <span className={clsx(
            'ml-auto text-xs font-medium',
            highlightedEntity.confidence >= 0.85 ? 'text-green-400' :
            highlightedEntity.confidence >= 0.65 ? 'text-amber-400' : 'text-red-400',
          )}>
            {Math.round(highlightedEntity.confidence * 100)}% confidence
          </span>
        </div>
      )}
    </div>
  )
}

interface EntityOverlayProps {
  entity: ExtractedEntity
  isHighlighted: boolean
  zoom: number
}

function EntityOverlay({ entity, isHighlighted, zoom }: EntityOverlayProps) {
  const bb = entity.bounding_box
  if (!bb) return null

  return (
    <div
      className={clsx(
        'absolute pointer-events-none rounded transition-all duration-200',
        isHighlighted
          ? 'bg-yellow-400/40 ring-2 ring-yellow-400'
          : 'bg-blue-400/15 ring-1 ring-blue-400/40',
      )}
      style={{
        left:   bb.x * zoom,
        top:    bb.y * zoom,
        width:  bb.width * zoom,
        height: bb.height * zoom,
      }}
      title={`${entity.entity_type}: ${entity.value}`}
    />
  )
}
