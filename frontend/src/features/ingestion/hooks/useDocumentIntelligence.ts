import { useState, useEffect, useCallback, useRef } from 'react'

// ─── Pipeline ─────────────────────────────────────────────────────────────────

export type PipelineStage =
  | 'idle'
  | 'upload'
  | 'validate'
  | 'ocr'
  | 'classify'
  | 'layout'
  | 'extract'
  | 'quality'
  | 'complete'
  | 'error'

export type StageStatus = 'waiting' | 'running' | 'done' | 'error'

export interface StageInfo {
  id:        PipelineStage
  label:     string
  sublabel:  string
  durationMs: number
  status:    StageStatus
  elapsedMs?: number
  detail?:   string
}

const STAGE_SEQUENCE: Omit<StageInfo, 'status'>[] = [
  { id: 'upload',   label: 'Upload',      sublabel: 'Receiving file',             durationMs: 400  },
  { id: 'validate', label: 'Validate',    sublabel: 'Format & integrity check',   durationMs: 600  },
  { id: 'ocr',      label: 'OCR Engine',  sublabel: 'Extracting text from pages', durationMs: 3200 },
  { id: 'classify', label: 'Classify',    sublabel: 'Identifying document type',  durationMs: 900  },
  { id: 'layout',   label: 'Layout',      sublabel: 'Detecting structure & zones',durationMs: 1200 },
  { id: 'extract',  label: 'AI Extract',  sublabel: 'NLP entity extraction',      durationMs: 2400 },
  { id: 'quality',  label: 'QA Score',    sublabel: 'Validating extraction',      durationMs: 700  },
  { id: 'complete', label: 'Complete',    sublabel: 'Ready for review',           durationMs: 0    },
]

// ─── Classification ───────────────────────────────────────────────────────────

export interface ClassificationResult {
  primaryType:       string
  primaryLabel:      string
  confidence:        number
  alternatives:      { type: string; label: string; confidence: number }[]
  detectedSections:  string[]
  pageCount:         number
  wordCount:         number
  language:          string
}

// ─── Layout detection ─────────────────────────────────────────────────────────

export type LayoutElementType = 'header' | 'field_block' | 'table' | 'paragraph' | 'signature' | 'logo' | 'footer'

export interface LayoutElement {
  id:         string
  type:       LayoutElementType
  label:      string
  x:          number  // 0-100 percent of doc width
  y:          number  // 0-100 percent of doc height
  w:          number
  h:          number
  confidence: number
  pageIndex:  number
}

// ─── OCR quality ──────────────────────────────────────────────────────────────

export interface OCRMetrics {
  overallConfidence:  number
  pageConfidences:    number[]
  wordCount:          number
  lowConfidenceWords: number
  skewDetected:       boolean
  skewAngle:          number
  noiseLevel:         'low' | 'medium' | 'high'
  resolution:         number
  colorMode:          'grayscale' | 'color' | 'binary'
  engineUsed:         string
  processingMs:       number
}

// ─── Extraction field ─────────────────────────────────────────────────────────

export type FieldSource = 'ocr_direct' | 'ai_inferred' | 'pattern_match' | 'calculated'
export type VerificationState = null | 'confirmed' | 'corrected' | 'rejected'

export interface ExtractionField {
  id:            string
  label:         string
  value:         string
  rawOCR?:       string          // the raw OCR output before normalization
  confidence:    number          // combined confidence
  ocrConfidence: number
  aiConfidence:  number
  source:        FieldSource
  verified:      VerificationState
  correction?:   string
  boundPage:     number
  entityType?:   string
  unit?:         string
  referenceRange?: string
  status?:       'normal' | 'abnormal' | 'critical'
  trend?:        'up' | 'down' | 'stable'
}

export interface ExtractionCardData {
  id:               string
  type:             string
  title:            string
  iconKey:          string
  color:            string
  fields:           ExtractionField[]
  overallConfidence: number
  completeness:     number   // 0-1
  expectedFields:   number
  foundFields:      number
}

// ─── Mock data ────────────────────────────────────────────────────────────────

function field(
  id: string, label: string, value: string,
  conf: number, ocr: number, ai: number,
  source: FieldSource, rawOCR?: string,
  extra?: Partial<ExtractionField>
): ExtractionField {
  return { id, label, value, rawOCR, confidence: conf, ocrConfidence: ocr, aiConfidence: ai, source, verified: null, boundPage: 0, ...extra }
}

export const MOCK_CARDS: ExtractionCardData[] = [
  {
    id: 'patient_info', type: 'patient_info', title: 'Patient Information',
    iconKey: 'User', color: '#0ea5e9', expectedFields: 7, foundFields: 7, completeness: 1.0, overallConfidence: 0.957,
    fields: [
      field('p1', 'Full Name',       'James Mitchell',           0.99, 0.99, 0.99, 'ocr_direct'),
      field('p2', 'Date of Birth',   '04/12/1958',               0.97, 0.95, 0.99, 'pattern_match', '04/12/1953', { rawOCR: '04/12/1953' }),
      field('p3', 'Age',             '66 years',                 0.99, 0.99, 0.99, 'calculated'),
      field('p4', 'Gender',          'Male',                     0.99, 0.99, 0.99, 'ocr_direct'),
      field('p5', 'Member ID',       'UHC-4821937',              0.98, 0.97, 0.99, 'pattern_match'),
      field('p6', 'Insurance Plan',  'UnitedHealth PPO Gold',    0.96, 0.94, 0.98, 'ocr_direct'),
      field('p7', 'Address',         '4821 Maple Drive, CA 90210', 0.93, 0.91, 0.95, 'ocr_direct'),
    ],
  },
  {
    id: 'provider_info', type: 'provider_info', title: 'Provider Information',
    iconKey: 'Stethoscope', color: '#8b5cf6', expectedFields: 6, foundFields: 6, completeness: 1.0, overallConfidence: 0.972,
    fields: [
      field('pr1', 'Provider Name',  'Dr. Sarah Chen, MD',               0.99, 0.99, 0.99, 'ocr_direct'),
      field('pr2', 'NPI',            '1497836254',                        0.99, 0.99, 0.99, 'pattern_match'),
      field('pr3', 'Specialty',      'Orthopedic Surgery',               0.98, 0.97, 0.99, 'ai_inferred'),
      field('pr4', 'Organization',   'Westside Orthopedic Associates',   0.97, 0.96, 0.98, 'ocr_direct'),
      field('pr5', 'Phone',          '(310) 555-0142',                   0.99, 0.99, 0.99, 'pattern_match'),
      field('pr6', 'Tax ID',         '95-4821376',                       0.96, 0.94, 0.98, 'pattern_match'),
    ],
  },
  {
    id: 'cpt_codes', type: 'cpt_codes', title: 'CPT Procedure Codes',
    iconKey: 'Code', color: '#06b6d4', expectedFields: 3, foundFields: 3, completeness: 1.0, overallConfidence: 0.981,
    fields: [
      field('c1', '27447 — Total Knee Arthroplasty (R)',    '27447', 0.99, 0.99, 0.99, 'pattern_match', undefined, { entityType: 'CPT' }),
      field('c2', '99213 — Office Visit, Est. Patient',     '99213', 0.97, 0.97, 0.97, 'pattern_match', undefined, { entityType: 'CPT' }),
      field('c3', '73562 — X-Ray Knee, 3 Views',            '73562', 0.98, 0.98, 0.98, 'pattern_match', undefined, { entityType: 'CPT' }),
    ],
  },
  {
    id: 'icd_codes', type: 'icd_codes', title: 'ICD-10 Diagnosis Codes',
    iconKey: 'BookMarked', color: '#a855f7', expectedFields: 4, foundFields: 3, completeness: 0.75, overallConfidence: 0.943,
    fields: [
      field('i1', 'M17.11 — Primary OA, Right Knee',          'M17.11', 0.99, 0.99, 0.99, 'pattern_match', undefined, { entityType: 'ICD' }),
      field('i2', 'M25.361 — Stiffness, Right Knee',          'M25.361',0.97, 0.96, 0.98, 'pattern_match', undefined, { entityType: 'ICD' }),
      field('i3', 'Z96.651 — Presence of Right Artif. Knee',  'Z96.651',0.95, 0.94, 0.96, 'pattern_match', undefined, { entityType: 'ICD' }),
    ],
  },
  {
    id: 'medications', type: 'medications', title: 'Medications',
    iconKey: 'Pill', color: '#10b981', expectedFields: 5, foundFields: 4, completeness: 0.80, overallConfidence: 0.918,
    fields: [
      field('m1', 'Naproxen',   '500mg BID × 18 months',      0.96, 0.94, 0.98, 'ai_inferred', 'Naproxen 500 mg twice daily'),
      field('m2', 'Celecoxib',  '200mg QD × 6 months',        0.94, 0.92, 0.96, 'ai_inferred'),
      field('m3', 'Cortisone',  'IA injection × 3, quarterly',0.92, 0.89, 0.95, 'ai_inferred', 'corticosteroid inj q3m'),
      field('m4', 'Lisinopril', '10mg QD (HTN)',               0.88, 0.85, 0.91, 'ai_inferred'),
    ],
  },
  {
    id: 'lab_values', type: 'lab_values', title: 'Lab Values',
    iconKey: 'FlaskConical', color: '#f59e0b', expectedFields: 8, foundFields: 7, completeness: 0.875, overallConfidence: 0.963,
    fields: [
      field('l1', 'HbA1c',          '5.9%',                0.99, 0.99, 0.99, 'pattern_match', undefined, { unit: '%',         referenceRange: '<5.7% normal', status: 'abnormal' as const }),
      field('l2', 'Hemoglobin',     '14.2 g/dL',           0.99, 0.99, 0.99, 'pattern_match', undefined, { unit: 'g/dL',      referenceRange: '13.5–17.5',    status: 'normal'   as const }),
      field('l3', 'Creatinine',     '0.98 mg/dL',          0.98, 0.97, 0.99, 'pattern_match', undefined, { unit: 'mg/dL',     referenceRange: '0.74–1.35',    status: 'normal'   as const }),
      field('l4', 'INR',            '1.0',                  0.99, 0.99, 0.99, 'pattern_match', undefined, { unit: '',          referenceRange: '0.9–1.1',      status: 'normal'   as const }),
      field('l5', 'Platelet Count', '224 × 10³/μL',        0.97, 0.95, 0.99, 'pattern_match', undefined, { unit: '×10³/μL',  referenceRange: '150–400',       status: 'normal'   as const }),
      field('l6', 'WBC',            '6.8 × 10³/μL',        0.98, 0.97, 0.99, 'pattern_match', undefined, { unit: '×10³/μL',  referenceRange: '4.5–11.0',      status: 'normal'   as const }),
      field('l7', 'BMP Sodium',     '139 mEq/L',           0.96, 0.94, 0.98, 'pattern_match', undefined, { unit: 'mEq/L',    referenceRange: '136–145',        status: 'normal'   as const }),
    ],
  },
  {
    id: 'insulin', type: 'insulin', title: 'Insulin & Glucose Management',
    iconKey: 'Droplets', color: '#06b6d4', expectedFields: 6, foundFields: 3, completeness: 0.50, overallConfidence: 0.781,
    fields: [
      field('in1', 'Insulin Prescribed', 'Not documented',          0.72, 0.65, 0.79, 'ai_inferred'),
      field('in2', 'Diabetes Status',    'Pre-diabetic (HbA1c 5.9%)',0.88, 0.82, 0.94, 'ai_inferred'),
      field('in3', 'Glucose Control',    'Diet & exercise managed', 0.76, 0.71, 0.81, 'ai_inferred'),
    ],
  },
  {
    id: 'glucose', type: 'glucose', title: 'Glucose Trends',
    iconKey: 'TrendingUp', color: '#f97316', expectedFields: 5, foundFields: 4, completeness: 0.80, overallConfidence: 0.849,
    fields: [
      field('g1', 'Fasting Glucose (latest)',    '98 mg/dL',      0.91, 0.88, 0.94, 'pattern_match', undefined, { unit: 'mg/dL', referenceRange: '70–99',   status: 'normal'  as const, trend: 'stable' as const }),
      field('g2', 'Post-prandial Glucose',       '142 mg/dL',     0.87, 0.84, 0.90, 'ai_inferred',  undefined, { unit: 'mg/dL', referenceRange: '<140',    status: 'abnormal'as const, trend: 'up'     as const }),
      field('g3', 'HbA1c Trend (12 months)',     '5.7 → 5.9%',   0.85, 0.82, 0.88, 'calculated',   undefined, { trend: 'up' as const }),
      field('g4', 'Glucose Risk Category',       'Pre-diabetic',  0.92, 0.88, 0.96, 'ai_inferred'),
    ],
  },
]

export const MOCK_CLASSIFICATION: ClassificationResult = {
  primaryType:      'CLINICAL_NOTES',
  primaryLabel:     'Clinical Notes',
  confidence:       0.963,
  alternatives: [
    { type: 'REFERRAL_LETTER',   label: 'Referral Letter',  confidence: 0.031 },
    { type: 'DISCHARGE_SUMMARY', label: 'Discharge Summary',confidence: 0.006 },
  ],
  detectedSections: ['Chief Complaint', 'HPI', 'Physical Exam', 'Assessment & Plan', 'Medications', 'Labs'],
  pageCount:    4,
  wordCount:    1847,
  language:     'English (en-US)',
}

export const MOCK_LAYOUT: LayoutElement[] = [
  { id: 'ly1', type: 'header',      label: 'Document Header',       x: 2,  y: 1,  w: 96, h: 8,  confidence: 0.99, pageIndex: 0 },
  { id: 'ly2', type: 'field_block', label: 'Patient Demographics',  x: 2,  y: 11, w: 45, h: 22, confidence: 0.97, pageIndex: 0 },
  { id: 'ly3', type: 'field_block', label: 'Provider Info',         x: 52, y: 11, w: 45, h: 22, confidence: 0.96, pageIndex: 0 },
  { id: 'ly4', type: 'paragraph',   label: 'Chief Complaint',       x: 2,  y: 36, w: 96, h: 12, confidence: 0.98, pageIndex: 0 },
  { id: 'ly5', type: 'paragraph',   label: 'HPI Narrative',         x: 2,  y: 51, w: 96, h: 20, confidence: 0.97, pageIndex: 0 },
  { id: 'ly6', type: 'field_block', label: 'Medications List',      x: 2,  y: 74, w: 96, h: 18, confidence: 0.95, pageIndex: 0 },
  { id: 'ly7', type: 'footer',      label: 'Footer / Signature',    x: 2,  y: 94, w: 96, h: 5,  confidence: 0.99, pageIndex: 0 },
  { id: 'ly8', type: 'table',       label: 'Lab Results Table',     x: 2,  y: 10, w: 96, h: 55, confidence: 0.98, pageIndex: 3 },
  { id: 'ly9', type: 'signature',   label: 'Physician Signature',   x: 60, y: 80, w: 38, h: 12, confidence: 0.91, pageIndex: 3 },
]

export const MOCK_OCR: OCRMetrics = {
  overallConfidence:  0.974,
  pageConfidences:    [0.981, 0.972, 0.969, 0.975],
  wordCount:          1847,
  lowConfidenceWords: 23,
  skewDetected:       false,
  skewAngle:          0.3,
  noiseLevel:         'low',
  resolution:         300,
  colorMode:          'grayscale',
  engineUsed:         'AWS Textract + Tesseract 5',
  processingMs:       3218,
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export interface DocumentIntelligenceState {
  // Pipeline
  stages:          StageInfo[]
  currentStage:    PipelineStage
  isProcessing:    boolean
  isComplete:      boolean
  hasFile:         boolean
  fileName:        string
  fileSize:        string
  totalElapsedMs:  number
  // Results
  ocr:             OCRMetrics | null
  classification:  ClassificationResult | null
  layout:          LayoutElement[]
  cards:           ExtractionCardData[]
  // UI state
  activeCardId:    string | null
  showLayout:      boolean
  // Actions
  startProcessing: (fileName: string, fileSize: string) => void
  reset:           () => void
  verifyField:     (cardId: string, fieldId: string, state: VerificationState, correction?: string) => void
  setActiveCard:   (id: string | null) => void
  toggleLayout:    () => void
}

const INITIAL_STAGES: StageInfo[] = STAGE_SEQUENCE.map((s) => ({
  ...s,
  status: 'waiting' as StageStatus,
}))

export function useDocumentIntelligence(): DocumentIntelligenceState {
  const [stages,          setStages]         = useState<StageInfo[]>(INITIAL_STAGES)
  const [currentStage,    setCurrentStage]   = useState<PipelineStage>('idle')
  const [hasFile,         setHasFile]        = useState(false)
  const [fileName,        setFileName]       = useState('')
  const [fileSize,        setFileSize]       = useState('')
  const [totalElapsedMs,  setTotalElapsed]   = useState(0)
  const [ocr,             setOCR]            = useState<OCRMetrics | null>(null)
  const [classification,  setClassification] = useState<ClassificationResult | null>(null)
  const [layout,          setLayout]         = useState<LayoutElement[]>([])
  const [cards,           setCards]          = useState<ExtractionCardData[]>([])
  const [activeCardId,    setActiveCard]     = useState<string | null>(null)
  const [showLayout,      setShowLayout]     = useState(true)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const startRef = useRef<number>(0)

  const isProcessing = currentStage !== 'idle' && currentStage !== 'complete' && currentStage !== 'error'
  const isComplete   = currentStage === 'complete'

  // Elapsed timer
  useEffect(() => {
    if (isProcessing) {
      timerRef.current = setInterval(() => {
        setTotalElapsed(Date.now() - startRef.current)
      }, 100)
    } else {
      if (timerRef.current) clearInterval(timerRef.current)
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [isProcessing])

  const startProcessing = useCallback(async (fn: string, fs: string) => {
    setFileName(fn)
    setFileSize(fs)
    setHasFile(true)
    setStages(INITIAL_STAGES)
    setOCR(null)
    setClassification(null)
    setLayout([])
    setCards([])
    startRef.current = Date.now()

    // Run stages sequentially
    const stageList = STAGE_SEQUENCE.filter((s) => s.id !== 'idle')

    for (const stageDef of stageList) {
      setCurrentStage(stageDef.id as PipelineStage)
      setStages((prev) => prev.map((s) =>
        s.id === stageDef.id ? { ...s, status: 'running' } : s
      ))

      await new Promise((r) => setTimeout(r, stageDef.durationMs))

      setStages((prev) => prev.map((s) =>
        s.id === stageDef.id ? { ...s, status: 'done', elapsedMs: stageDef.durationMs } : s
      ))

      // Release data as each stage completes
      if (stageDef.id === 'ocr') setOCR(MOCK_OCR)
      if (stageDef.id === 'classify') setClassification(MOCK_CLASSIFICATION)
      if (stageDef.id === 'layout') setLayout(MOCK_LAYOUT)
      if (stageDef.id === 'extract') {
        // Reveal cards one at a time for drama
        for (let i = 0; i < MOCK_CARDS.length; i++) {
          await new Promise((r) => setTimeout(r, 180))
          setCards((prev) => [...prev, MOCK_CARDS[i]])
        }
      }
    }

    setCurrentStage('complete')
  }, [])

  const reset = useCallback(() => {
    setStages(INITIAL_STAGES)
    setCurrentStage('idle')
    setHasFile(false)
    setFileName('')
    setFileSize('')
    setTotalElapsed(0)
    setOCR(null)
    setClassification(null)
    setLayout([])
    setCards([])
    setActiveCard(null)
  }, [])

  const verifyField = useCallback((cardId: string, fieldId: string, state: VerificationState, correction?: string) => {
    setCards((prev) => prev.map((card) =>
      card.id !== cardId ? card : {
        ...card,
        fields: card.fields.map((f) =>
          f.id !== fieldId ? f : {
            ...f,
            verified:   state,
            correction: correction ?? f.correction,
            value:      correction ?? f.value,
          }
        ),
      }
    ))
  }, [])

  const toggleLayout = useCallback(() => setShowLayout((v) => !v), [])

  return {
    stages, currentStage, isProcessing, isComplete, hasFile, fileName, fileSize, totalElapsedMs,
    ocr, classification, layout, cards,
    activeCardId, showLayout,
    startProcessing, reset, verifyField, setActiveCard, toggleLayout,
  }
}
