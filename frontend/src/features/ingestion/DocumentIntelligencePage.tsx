import { useEffect, useCallback, useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, FileText, Brain, RefreshCw,
  Sparkles, ScanLine, Layers,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useUIStore } from '@/store/uiStore'
import { useDocumentIntelligence } from './hooks/useDocumentIntelligence'
import { PipelineProgress }  from './components/PipelineProgress'
import { DocumentQuality }   from './components/DocumentQuality'
import { ExtractionCards }   from './components/ExtractionCards'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatBytes(bytes: number): string {
  if (bytes < 1024)       return `${bytes} B`
  if (bytes < 1048576)    return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

// ─── Drop zone ────────────────────────────────────────────────────────────────

interface DropZoneProps {
  onFile: (name: string, size: string) => void
}

function DropZone({ onFile }: DropZoneProps) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback((file: File) => {
    onFile(file.name, formatBytes(file.size))
  }, [onFile])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  const onInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }, [handleFile])

  // Demo files
  const DEMO_DOCS = [
    { name: 'Clinical_Notes_Mitchell_J.pdf',     size: '2.4 MB',  type: 'Clinical Notes'     },
    { name: 'Radiology_Report_2024-01-30.pdf',   size: '1.1 MB',  type: 'Radiology Report'   },
    { name: 'Lab_Results_Quest_2024-01-15.pdf',  size: '0.8 MB',  type: 'Lab Results'        },
    { name: 'Referral_Letter_Stein_R.pdf',       size: '0.4 MB',  type: 'Referral Letter'    },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      {/* Hero upload area */}
      <label
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          'relative flex flex-col items-center justify-center rounded-3xl border-2 border-dashed cursor-pointer transition-all overflow-hidden',
          dragging
            ? 'border-violet-500 bg-violet-500/10 scale-[1.01]'
            : 'border-[var(--border)] hover:border-violet-500/60 hover:bg-violet-500/5',
        )}
        style={{ minHeight: 280 }}
      >
        <input ref={inputRef} type="file" className="hidden" accept=".pdf,.png,.jpg,.jpeg,.tiff" onChange={onInput} />

        {/* Animated background orbs */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          {[
            { x: '20%', y: '30%', color: 'rgba(139,92,246,0.08)', size: 200 },
            { x: '70%', y: '60%', color: 'rgba(14,165,233,0.07)', size: 160 },
            { x: '50%', y: '80%', color: 'rgba(16,185,129,0.06)', size: 120 },
          ].map((orb, i) => (
            <motion.div
              key={i}
              className="absolute rounded-full"
              style={{ width: orb.size, height: orb.size, background: orb.color, left: orb.x, top: orb.y, transform: 'translate(-50%,-50%)' }}
              animate={{ scale: [1, 1.15, 1], opacity: [0.6, 1, 0.6] }}
              transition={{ duration: 3 + i, repeat: Infinity, delay: i * 0.8 }}
            />
          ))}
        </div>

        {/* Upload icon */}
        <motion.div
          animate={dragging ? { scale: 1.1 } : { scale: 1 }}
          className="relative flex flex-col items-center gap-4"
        >
          <motion.div
            className="w-16 h-16 rounded-2xl flex items-center justify-center"
            style={{ background: 'rgba(139,92,246,0.15)', border: '1px solid rgba(139,92,246,0.3)' }}
            animate={{ boxShadow: dragging
              ? ['0 0 0 0 rgba(139,92,246,0)', '0 0 32px 8px rgba(139,92,246,0.25)', '0 0 0 0 rgba(139,92,246,0)']
              : '0 0 0 0 rgba(139,92,246,0)',
            }}
            transition={{ duration: 1.5, repeat: Infinity }}
          >
            {dragging ? (
              <motion.div initial={{ scale: 0.8 }} animate={{ scale: 1.1 }} transition={{ duration: 0.2 }}>
                <ScanLine className="w-8 h-8 text-violet-400" />
              </motion.div>
            ) : (
              <Upload className="w-8 h-8 text-violet-400" />
            )}
          </motion.div>

          <div className="text-center">
            <p className="text-base font-bold text-[var(--text-1)]">
              {dragging ? 'Release to analyze' : 'Drop document here'}
            </p>
            <p className="text-sm text-[var(--text-4)] mt-1">
              PDF, PNG, JPG, TIFF · up to 50MB per document
            </p>
          </div>

          {/* Feature pills */}
          <div className="flex items-center gap-2 flex-wrap justify-center">
            {[
              { icon: Brain,   label: 'AI Extraction' },
              { icon: ScanLine,label: 'OCR' },
              { icon: Layers,  label: 'Layout Detection' },
            ].map(({ icon: Icon, label }) => (
              <div
                key={label}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-medium"
                style={{ background: 'var(--elevated)', border: '1px solid var(--border)', color: 'var(--text-3)' }}
              >
                <Icon className="w-3 h-3" />
                {label}
              </div>
            ))}
          </div>
        </motion.div>
      </label>

      {/* Demo documents */}
      <div>
        <p className="text-[11px] text-[var(--text-4)] uppercase tracking-wider font-medium mb-3">
          Or try a demo document
        </p>
        <div className="grid grid-cols-2 gap-3">
          {DEMO_DOCS.map((doc) => (
            <button
              key={doc.name}
              onClick={() => onFile(doc.name, doc.size)}
              className="flex items-start gap-3 px-4 py-3 rounded-xl border border-[var(--border)] hover:border-violet-500/40 hover:bg-violet-500/5 transition-all text-left group"
            >
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
                style={{ background: 'rgba(139,92,246,0.1)' }}
              >
                <FileText className="w-4 h-4 text-violet-400" />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-medium text-[var(--text-1)] truncate group-hover:text-violet-300 transition-colors">
                  {doc.name}
                </p>
                <p className="text-[9px] text-[var(--text-4)] mt-0.5">{doc.type} · {doc.size}</p>
              </div>
              <Sparkles className="w-3.5 h-3.5 text-violet-400 opacity-0 group-hover:opacity-100 transition-opacity ml-auto flex-shrink-0 mt-1" />
            </button>
          ))}
        </div>
      </div>
    </motion.div>
  )
}

// ─── Page header ──────────────────────────────────────────────────────────────

function PageHeader({ isProcessing, isComplete, onReset }: {
  isProcessing: boolean; isComplete: boolean; onReset: () => void
}) {
  return (
    <div className="flex items-center justify-between flex-wrap gap-3">
      <div>
        <h1 className="text-xl font-bold text-[var(--text-1)]">Document Intelligence</h1>
        <p className="text-sm text-[var(--text-4)] mt-0.5">
          AI-powered OCR · Entity extraction · Classification · Layout detection
        </p>
      </div>

      <div className="flex items-center gap-2">
        {(isProcessing || isComplete) && (
          <button
            onClick={onReset}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-[var(--border)] text-xs font-medium text-[var(--text-3)] hover:bg-[var(--elevated)] transition-all"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            New document
          </button>
        )}

        {isProcessing && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-2 px-3 py-1.5 rounded-xl"
            style={{ background: 'rgba(139,92,246,0.12)', border: '1px solid rgba(139,92,246,0.25)' }}
          >
            <motion.div
              className="w-1.5 h-1.5 rounded-full bg-violet-400"
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ duration: 0.8, repeat: Infinity }}
            />
            <span className="text-xs font-medium text-violet-400">AI Processing</span>
          </motion.div>
        )}

        {isComplete && (
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="flex items-center gap-2 px-3 py-1.5 rounded-xl"
            style={{ background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.25)' }}
          >
            <span className="text-xs font-bold text-emerald-400">✓ Extraction Complete</span>
          </motion.div>
        )}
      </div>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function DocumentIntelligencePage() {
  const addTab      = useUIStore((s) => s.addTab)
  const intelligence = useDocumentIntelligence()
  const {
    stages, currentStage, isProcessing, isComplete, hasFile,
    fileName, fileSize, totalElapsedMs,
    ocr, classification, layout, cards,
    activeCardId, showLayout,
    startProcessing, reset, verifyField, setActiveCard, toggleLayout,
  } = intelligence

  // Register workspace tab
  useEffect(() => {
    addTab({
      title:     'Doc Intelligence',
      path:      '/ingestion',
      type:      'page',
      closeable: true,
    })
  }, [addTab])

  const handleFile = useCallback((name: string, size: string) => {
    startProcessing(name, size)
  }, [startProcessing])

  return (
    <div className="min-h-full p-6 space-y-6">

      {/* Page header */}
      <PageHeader
        isProcessing={isProcessing}
        isComplete={isComplete}
        onReset={reset}
      />

      {/* Drop zone (shown when no file) */}
      <AnimatePresence mode="wait">
        {!hasFile && (
          <motion.div
            key="dropzone"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ duration: 0.25 }}
          >
            <DropZone onFile={handleFile} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Pipeline progress (shown after file selected) */}
      <AnimatePresence>
        {hasFile && (
          <motion.div
            key="pipeline"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <PipelineProgress
              stages={stages}
              currentStage={currentStage}
              isComplete={isComplete}
              elapsedMs={totalElapsedMs}
              fileName={fileName}
              fileSize={fileSize}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main content: two-column layout when results appear */}
      <AnimatePresence>
        {(ocr || classification || cards.length > 0) && (
          <motion.div
            key="results"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4 }}
            className="grid grid-cols-1 xl:grid-cols-3 gap-6"
          >
            {/* LEFT: Extraction cards (2/3 width) */}
            <div className="xl:col-span-2 space-y-6">
              {/* Section label */}
              <div className="flex items-center gap-2">
                <Brain className="w-4 h-4 text-violet-400" />
                <h2 className="text-sm font-semibold text-[var(--text-2)]">Smart Extraction</h2>
                <span
                  className="text-[9px] font-medium px-2 py-0.5 rounded-full ml-1"
                  style={{ background: 'rgba(139,92,246,0.12)', color: '#a78bfa' }}
                >
                  {cards.length} entity types
                </span>

                {/* Loading shimmer while more cards stream in */}
                {isProcessing && currentStage === 'extract' && (
                  <motion.span
                    animate={{ opacity: [0.4, 1, 0.4] }}
                    transition={{ duration: 1.2, repeat: Infinity }}
                    className="text-[10px] text-violet-400 ml-auto"
                  >
                    Extracting entities…
                  </motion.span>
                )}
              </div>

              <ExtractionCards
                cards={cards}
                activeCardId={activeCardId}
                onSetActive={setActiveCard}
                onVerify={verifyField}
              />
            </div>

            {/* RIGHT: Quality panels (1/3 width) */}
            <div>
              <div className="flex items-center gap-2 mb-4">
                <ScanLine className="w-4 h-4 text-cyan-400" />
                <h2 className="text-sm font-semibold text-[var(--text-2)]">Analysis Results</h2>
              </div>
              <DocumentQuality
                ocr={ocr}
                classification={classification}
                layout={layout}
                showLayout={showLayout}
                onToggleLayout={toggleLayout}
                cards={cards}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Processing skeleton while OCR running */}
      <AnimatePresence>
        {isProcessing && !ocr && cards.length === 0 && (
          <motion.div
            key="skeleton"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="grid grid-cols-1 xl:grid-cols-3 gap-6"
          >
            <div className="xl:col-span-2 grid grid-cols-2 gap-4">
              {Array.from({ length: 6 }, (_, i) => (
                <div
                  key={i}
                  className="rounded-2xl overflow-hidden"
                  style={{ background: 'var(--surface)', border: '1px solid var(--border)', height: 160 }}
                >
                  <div className="h-0.5 w-full animate-pulse" style={{ background: 'var(--border)' }} />
                  <div className="p-4 space-y-3">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-xl animate-pulse" style={{ background: 'var(--elevated)' }} />
                      <div className="space-y-1.5 flex-1">
                        <div className="h-3 rounded animate-pulse w-3/4" style={{ background: 'var(--elevated)' }} />
                        <div className="h-2 rounded animate-pulse w-1/2" style={{ background: 'var(--elevated)' }} />
                      </div>
                    </div>
                    {[0.9, 0.7, 0.5].map((w, j) => (
                      <div key={j} className="h-2 rounded animate-pulse" style={{ background: 'var(--elevated)', width: `${w * 100}%` }} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="space-y-4">
              {[200, 160, 180].map((h, i) => (
                <div
                  key={i}
                  className="rounded-2xl animate-pulse"
                  style={{ background: 'var(--elevated)', height: h }}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
