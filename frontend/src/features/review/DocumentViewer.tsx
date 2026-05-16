import { useState } from 'react'
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut, FileText, Download } from 'lucide-react'
import { motion } from 'framer-motion'

const MOCK_DOCUMENTS = [
  { id: 'd1', name: 'Clinical Notes.pdf',        type: 'CLINICAL_NOTES',    pages: 4 },
  { id: 'd2', name: 'Lab Results.pdf',           type: 'LAB_RESULTS',       pages: 2 },
  { id: 'd3', name: 'Physician Order.pdf',       type: 'PHYSICIAN_ORDER',   pages: 1 },
  { id: 'd4', name: 'Insurance Card.pdf',        type: 'INSURANCE_CARD',    pages: 1 },
]

const MOCK_EXTRACTED_TEXT = `CLINICAL NOTES — PATIENT: MARIA GONZALEZ
DATE OF SERVICE: 2024-01-15
ATTENDING: Dr. Robert Stein, MD — Orthopedic Surgery

CHIEF COMPLAINT:
Patient presents with severe right knee pain, rated 9/10, significantly limiting ambulation. Pain has been progressive over 18 months despite conservative management.

HISTORY OF PRESENT ILLNESS:
73-year-old female with longstanding severe osteoarthritis of the right knee (ICD-10: M17.11). Patient has failed conservative treatment including:
• Physical therapy (6 months, 24 sessions) — inadequate pain relief
• NSAIDs: Naproxen 500mg BID × 3 months — discontinued due to GI intolerance
• Corticosteroid injections × 3 (last: 2023-10-12) — temporary relief only
• Viscosupplementation × 1 course — no significant benefit

PHYSICAL EXAMINATION:
• Right knee: severe varus deformity, crepitus with range of motion
• ROM: Flexion 85°, Extension -15° (flexion contracture)
• BMI: 28.4 kg/m² (within acceptable surgical range)
• Neurovascular: intact distally

RADIOGRAPHIC FINDINGS:
• AP/Lateral right knee X-rays (2024-01-10): Severe tricompartmental osteoarthritis
  with bone-on-bone changes, significant joint space narrowing, subchondral sclerosis
  and osteophyte formation

ASSESSMENT & PLAN:
Severe right knee osteoarthritis (M17.11) with significant functional limitation.
Patient has failed appropriate conservative management. Recommend total knee arthroplasty
(CPT 27447) as medically necessary.

Surgical planning: Scheduled 2024-02-15, pre-op evaluation completed.`

export function DocumentViewer() {
  const [selectedDoc, setSelectedDoc] = useState(MOCK_DOCUMENTS[0])
  const [page, setPage] = useState(1)
  const [zoom, setZoom] = useState(100)

  return (
    <div className="flex gap-4 h-full">
      {/* Document list */}
      <div className="w-48 flex-shrink-0 space-y-1.5">
        <p className="section-label mb-2">Documents ({MOCK_DOCUMENTS.length})</p>
        {MOCK_DOCUMENTS.map((doc) => (
          <button
            key={doc.id}
            onClick={() => { setSelectedDoc(doc); setPage(1) }}
            className={`w-full text-left px-3 py-2.5 rounded-lg border transition-colors ${
              selectedDoc.id === doc.id
                ? 'border-brand-500/30 bg-brand-500/10 text-brand-400'
                : 'border-[var(--border)] text-[var(--text-2)] hover:bg-[var(--elevated)]'
            }`}
          >
            <div className="flex items-start gap-2">
              <FileText className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
              <div className="min-w-0">
                <p className="text-xs font-medium leading-snug truncate">{doc.name}</p>
                <p className="text-xs text-[var(--text-3)] mt-0.5">{doc.pages}p</p>
              </div>
            </div>
          </button>
        ))}
      </div>

      {/* Viewer */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Toolbar */}
        <div className="flex items-center gap-2 mb-3">
          <div className="flex items-center gap-1 bg-[var(--elevated)] rounded-lg p-1 border border-[var(--border)]">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-1.5 rounded text-[var(--text-2)] hover:text-[var(--text-1)] disabled:opacity-40"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <span className="text-xs text-[var(--text-2)] px-1 tabular-nums">
              {page} / {selectedDoc.pages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(selectedDoc.pages, p + 1))}
              disabled={page >= selectedDoc.pages}
              className="p-1.5 rounded text-[var(--text-2)] hover:text-[var(--text-1)] disabled:opacity-40"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="flex items-center gap-1 bg-[var(--elevated)] rounded-lg p-1 border border-[var(--border)]">
            <button
              onClick={() => setZoom((z) => Math.max(50, z - 25))}
              className="p-1.5 rounded text-[var(--text-2)] hover:text-[var(--text-1)]"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <span className="text-xs text-[var(--text-2)] px-1.5 tabular-nums min-w-12 text-center">{zoom}%</span>
            <button
              onClick={() => setZoom((z) => Math.min(200, z + 25))}
              className="p-1.5 rounded text-[var(--text-2)] hover:text-[var(--text-1)]"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="flex-1" />

          <button className="btn btn-ghost py-1.5 px-3 text-xs gap-1.5">
            <Download className="w-3.5 h-3.5" /> Download
          </button>
        </div>

        {/* Document content */}
        <motion.div
          key={selectedDoc.id + page}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex-1 bg-white dark:bg-[#1a1a2e] rounded-xl border border-[var(--border)] overflow-auto p-6 shadow-card"
          style={{ fontSize: `${zoom}%` }}
        >
          <pre className="font-mono text-xs text-slate-800 dark:text-slate-200 whitespace-pre-wrap leading-relaxed">
            {MOCK_EXTRACTED_TEXT}
          </pre>
        </motion.div>
      </div>
    </div>
  )
}