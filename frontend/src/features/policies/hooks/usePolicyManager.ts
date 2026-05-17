import { useState, useCallback, useMemo } from 'react'

// ─── Domain types ─────────────────────────────────────────────────────────────

export type ChunkType = 'criterion' | 'exclusion' | 'definition' | 'coverage' | 'documentation'
export type PolicyStatus = 'active' | 'draft' | 'archived' | 'under_review'

export interface CPTCode {
  code:        string
  description: string
  category:    string
}

export interface ICDCode {
  code:        string
  description: string
  category:    string
}

export interface PolicyChunk {
  id:          string
  index:       number
  type:        ChunkType
  text:        string
  tokenCount:  number
  embedding:   number[]   // 2-D projection for visualization
  similarityTo?: Record<string, number>  // chunk-id → similarity
  pageRef:     string
  sectionRef:  string
  retrievalScore?: number
  criterionRef?: string
}

export interface PolicyVersion {
  version:     string
  uploadedAt:  string
  uploadedBy:  string
  changeSummary: string
  chunkCount:  number
  status:      PolicyStatus
  fileSize:    string
}

export interface PolicyDocument {
  id:            string
  name:          string
  policyNumber:  string
  description:   string
  effectiveDate: string
  expiryDate:    string
  status:        PolicyStatus
  currentVersion: string
  versions:      PolicyVersion[]
  chunks:        PolicyChunk[]
  cptCodes:      CPTCode[]
  icdCodes:      ICDCode[]
  category:      string
  payerName:     string
  lob:           string           // line of business
  tags:          string[]
  chunkCount:    number
  lastIndexedAt: string
  retrievalQuality: number
}

export interface SearchResult {
  chunkId:    string
  policyId:   string
  policyName: string
  chunkText:  string
  score:      number
  chunkType:  ChunkType
  pageRef:    string
  sectionRef: string
}

// ─── Seeded PRNG ──────────────────────────────────────────────────────────────

function s(n: number) { return Math.abs(Math.sin(n * 9301 + 49297) % 1) }
function rnd(seed: number, min: number, max: number) { return min + s(seed) * (max - min) }

// ─── Mock embeddings (2-D PCA projection, clusters by type) ──────────────────

const CLUSTER_CENTERS: Record<ChunkType, [number, number]> = {
  criterion:     [0.15, 0.70],
  exclusion:     [0.80, 0.20],
  definition:    [0.50, 0.85],
  coverage:      [0.25, 0.30],
  documentation: [0.72, 0.65],
}

function makeEmbedding(type: ChunkType, seed: number): number[] {
  const [cx, cy] = CLUSTER_CENTERS[type]
  return [
    Math.min(0.97, Math.max(0.03, cx + (s(seed) - 0.5) * 0.22)),
    Math.min(0.97, Math.max(0.03, cy + (s(seed + 100) - 0.5) * 0.22)),
  ]
}

// ─── CPT / ICD catalogues ────────────────────────────────────────────────────

const CPT_POOL: CPTCode[] = [
  { code: '27447', description: 'Arthroplasty, knee, condyle and plateau; medial AND lateral compartments with or without patella resurfacing', category: 'Musculoskeletal' },
  { code: '27445', description: 'Arthroplasty, knee, hinge prosthesis', category: 'Musculoskeletal' },
  { code: '27440', description: 'Arthroplasty, knee, condyle; medial OR lateral compartment', category: 'Musculoskeletal' },
  { code: '20610', description: 'Arthrocentesis, aspiration and/or injection, major joint or bursa', category: 'Musculoskeletal' },
  { code: '27332', description: 'Arthroscopy, knee, surgical; with removal of loose body or foreign body', category: 'Musculoskeletal' },
  { code: '97110', description: 'Therapeutic exercises to develop strength and endurance, range of motion and flexibility', category: 'Physical Medicine' },
  { code: '99213', description: 'Office or other outpatient visit, established patient, moderate complexity', category: 'E&M' },
  { code: '73721', description: 'Magnetic resonance imaging, any joint of lower extremity', category: 'Radiology' },
  { code: '27570', description: 'Manipulation of knee joint under general anesthesia', category: 'Musculoskeletal' },
  { code: '29881', description: 'Arthroscopy, knee, surgical; with meniscectomy', category: 'Musculoskeletal' },
]

const ICD_POOL: ICDCode[] = [
  { code: 'M17.11', description: 'Primary osteoarthritis, right knee', category: 'Arthropathies' },
  { code: 'M17.12', description: 'Primary osteoarthritis, left knee', category: 'Arthropathies' },
  { code: 'M17.31', description: 'Unilateral post-traumatic osteoarthritis, right knee', category: 'Arthropathies' },
  { code: 'M17.32', description: 'Unilateral post-traumatic osteoarthritis, left knee', category: 'Arthropathies' },
  { code: 'M25.361', description: 'Stiffness of right knee, not elsewhere classified', category: 'Joint disorders' },
  { code: 'M25.362', description: 'Stiffness of left knee, not elsewhere classified', category: 'Joint disorders' },
  { code: 'Z96.641', description: 'Presence of right artificial knee joint', category: 'Status' },
  { code: 'Z96.642', description: 'Presence of left artificial knee joint', category: 'Status' },
  { code: 'M79.3',   description: 'Panniculitis, unspecified', category: 'Soft tissue' },
  { code: 'G89.29',  description: 'Other chronic pain', category: 'Pain' },
  { code: 'E11.9',   description: 'Type 2 diabetes mellitus without complications', category: 'Endocrine' },
  { code: 'I10',     description: 'Essential (primary) hypertension', category: 'Circulatory' },
]

// ─── Mock data factory ────────────────────────────────────────────────────────

const CHUNK_TYPES: ChunkType[] = ['criterion', 'exclusion', 'definition', 'coverage', 'documentation']

const CHUNK_TEXTS: Record<ChunkType, string[]> = {
  criterion: [
    'Member must have a diagnosis of severe osteoarthritis (Grade III or IV on the Kellgren-Lawrence scale) confirmed by radiographic evidence within the past 12 months.',
    'Conservative therapy failure: member must have completed at least 6 months of documented conservative management including physical therapy (minimum 12 sessions) and pharmacological treatment.',
    'BMI requirement: member\'s BMI must be ≤40 at time of authorization request unless documented clinical exception is provided by treating physician.',
    'Functional impairment: member must demonstrate significant functional limitation as evidenced by a WOMAC score ≥50 or equivalent validated outcome measure.',
    'Contralateral joint: authorization for bilateral procedures requires documentation of bilateral disease burden with separate functional assessments for each joint.',
    'Pre-operative cardiac clearance required for all members with known cardiovascular disease, diabetes, or BMI >35.',
  ],
  exclusion: [
    'Inflammatory arthropathy (rheumatoid arthritis, psoriatic arthritis, ankylosing spondylitis) as primary indication — refer to separate policy MP-2024-INFLAM.',
    'Active joint infection or systemic infection within 6 months of requested procedure date.',
    'Severe peripheral vascular disease with ABI <0.6 in the operative extremity.',
    'Uncontrolled psychiatric disorder that would preclude post-operative compliance with rehabilitation protocol.',
    'Prior failed TKA on the same joint within 2 years unless documented hardware failure requiring revision.',
  ],
  definition: [
    'Kellgren-Lawrence Grade: Standardized radiographic grading system for osteoarthritis severity. Grade 0=normal, Grade I=doubtful, Grade II=minimal, Grade III=moderate, Grade IV=severe.',
    'WOMAC (Western Ontario and McMaster Universities Osteoarthritis Index): Validated patient-reported outcome measure assessing pain, stiffness, and physical function. Score range 0-96; higher scores indicate greater disability.',
    'Total Knee Arthroplasty (TKA): Surgical procedure involving replacement of damaged knee joint surfaces with prosthetic implants. Includes unicompartmental, bicompartmental, and total condylar designs.',
    'Conservative Management: Non-surgical treatment modalities including physical therapy, oral analgesics (NSAIDs, acetaminophen), intra-articular injections, and activity modification.',
  ],
  coverage: [
    'This policy covers total knee arthroplasty (TKA) and unicompartmental knee arthroplasty (UKA) procedures when medical necessity criteria are met.',
    'Coverage includes pre-operative evaluation, surgical facility charges, anesthesia services, implant device, and post-operative inpatient stay not to exceed 3 days.',
    'Outpatient rehabilitation following TKA is covered for up to 60 visits within 6 months post-operatively subject to plan benefits and medical necessity.',
    'Revision TKA is covered when documented hardware failure, infection, instability, or aseptic loosening is confirmed by imaging and clinical evaluation.',
  ],
  documentation: [
    'Required documentation: Radiology report confirming KL grade, physical therapy notes documenting session count and progress, treating physician attestation of conservative therapy failure.',
    'Pre-authorization request must include: completed PA request form, supporting clinical notes from past 12 months, BMI documentation, WOMAC or equivalent functional assessment.',
    'Cardiac clearance documentation required: ECG within 30 days, cardiologist clearance letter if applicable, anesthesia pre-assessment for ASA Class III/IV patients.',
    'For revision procedures: operative report from prior TKA, imaging demonstrating failure mode, infectious disease consultation if septic loosening suspected.',
  ],
}

function makePolicyChunks(policyId: string, count: number): PolicyChunk[] {
  const chunks: PolicyChunk[] = []
  let chunkIdx = 0

  for (const type of CHUNK_TYPES) {
    const texts = CHUNK_TEXTS[type]
    const typeCount = Math.ceil(count / CHUNK_TYPES.length)
    for (let i = 0; i < Math.min(typeCount, texts.length); i++) {
      const seed = chunkIdx * 17 + policyId.charCodeAt(0)
      chunks.push({
        id:           `${policyId}-chunk-${chunkIdx}`,
        index:        chunkIdx,
        type,
        text:         texts[i],
        tokenCount:   Math.round(rnd(seed + 1, 80, 280)),
        embedding:    makeEmbedding(type, seed + 2),
        pageRef:      `p. ${Math.floor(rnd(seed + 3, 1, 18))}`,
        sectionRef:   `§${Math.floor(rnd(seed + 4, 1, 8))}.${Math.floor(rnd(seed + 5, 1, 12))}`,
        retrievalScore: rnd(seed + 6, 0.62, 0.98),
        criterionRef: type === 'criterion' ? `C${chunkIdx + 1}` : undefined,
      })
      chunkIdx++
    }
  }

  // Add pairwise similarities for first 8 chunks
  for (const chunk of chunks.slice(0, 8)) {
    chunk.similarityTo = {}
    for (const other of chunks.slice(0, 8)) {
      if (other.id !== chunk.id) {
        const dx = chunk.embedding[0] - other.embedding[0]
        const dy = chunk.embedding[1] - other.embedding[1]
        const dist = Math.sqrt(dx * dx + dy * dy)
        chunk.similarityTo[other.id] = Math.max(0, 1 - dist * 2)
      }
    }
  }

  return chunks
}

function makeVersions(_policyId: string): PolicyVersion[] {
  return [
    { version: '3.2', uploadedAt: '2024-12-01T09:00:00Z', uploadedBy: 'Dr. A. Torres', changeSummary: 'Updated BMI threshold from 45 to 40; added cardiac clearance requirement for ASA III/IV', chunkCount: 22, status: 'active',       fileSize: '1.4 MB' },
    { version: '3.1', uploadedAt: '2024-08-15T14:30:00Z', uploadedBy: 'Dr. A. Torres', changeSummary: 'Revised WOMAC cutoff from 45 to 50; clarified bilateral procedure criteria',             chunkCount: 21, status: 'archived',     fileSize: '1.3 MB' },
    { version: '3.0', uploadedAt: '2024-03-22T10:00:00Z', uploadedBy: 'Policy Team',   changeSummary: 'Major revision: added UKA coverage, expanded exclusion list, new documentation requirements', chunkCount: 20, status: 'archived', fileSize: '1.2 MB' },
    { version: '2.5', uploadedAt: '2023-09-10T08:00:00Z', uploadedBy: 'Policy Team',   changeSummary: 'Annual review — no substantive changes; updated effective dates',                          chunkCount: 18, status: 'archived',     fileSize: '1.1 MB' },
    { version: '2.4', uploadedAt: '2023-02-01T11:00:00Z', uploadedBy: 'Compliance',    changeSummary: 'Added inflammatory arthropathy exclusion per CMS guidance',                                chunkCount: 18, status: 'archived',     fileSize: '1.1 MB' },
  ]
}

const RAW_POLICIES: Omit<PolicyDocument, 'chunks' | 'versions' | 'chunkCount' | 'lastIndexedAt' | 'retrievalQuality'>[] = [
  {
    id: 'POL-001', name: 'Total Knee Arthroplasty', policyNumber: 'MP-2024-TKA-001',
    description: 'Medical necessity criteria for total and unicompartmental knee arthroplasty procedures.',
    effectiveDate: '2024-12-01', expiryDate: '2025-11-30',
    status: 'active', currentVersion: '3.2',
    cptCodes: CPT_POOL.slice(0, 5),
    icdCodes: ICD_POOL.slice(0, 8),
    category: 'Musculoskeletal', payerName: 'BlueCross BlueShield', lob: 'Commercial',
    tags: ['orthopedic', 'surgery', 'knee', 'arthroplasty'],
  },
  {
    id: 'POL-002', name: 'Physical Therapy — Outpatient', policyNumber: 'MP-2024-PT-002',
    description: 'Coverage policy for outpatient physical therapy services including post-surgical rehabilitation.',
    effectiveDate: '2024-01-01', expiryDate: '2024-12-31',
    status: 'active', currentVersion: '2.1',
    cptCodes: [CPT_POOL[5], CPT_POOL[6]],
    icdCodes: ICD_POOL.slice(4, 10),
    category: 'Rehabilitation', payerName: 'BlueCross BlueShield', lob: 'Medicare Advantage',
    tags: ['PT', 'rehabilitation', 'outpatient'],
  },
  {
    id: 'POL-003', name: 'MRI — Extremity Joints', policyNumber: 'MP-2024-IMG-003',
    description: 'Criteria for medical necessity of MRI imaging for extremity joint evaluation.',
    effectiveDate: '2024-06-01', expiryDate: '2025-05-31',
    status: 'under_review', currentVersion: '1.4',
    cptCodes: [CPT_POOL[7]],
    icdCodes: ICD_POOL.slice(0, 6),
    category: 'Radiology', payerName: 'Aetna', lob: 'Commercial',
    tags: ['imaging', 'MRI', 'musculoskeletal'],
  },
  {
    id: 'POL-004', name: 'Viscosupplementation Injections', policyNumber: 'MP-2024-VISC-004',
    description: 'Medical necessity and coverage guidelines for hyaluronic acid knee injections.',
    effectiveDate: '2024-01-01', expiryDate: '2024-12-31',
    status: 'draft', currentVersion: '0.9',
    cptCodes: [CPT_POOL[3]],
    icdCodes: ICD_POOL.slice(0, 4),
    category: 'Musculoskeletal', payerName: 'United Healthcare', lob: 'Medicaid',
    tags: ['injection', 'viscosupplementation', 'knee'],
  },
  {
    id: 'POL-005', name: 'Arthroscopic Knee Procedures', policyNumber: 'MP-2024-ARTH-005',
    description: 'Authorization requirements for diagnostic and surgical knee arthroscopy.',
    effectiveDate: '2023-07-01', expiryDate: '2024-06-30',
    status: 'archived', currentVersion: '2.0',
    cptCodes: [CPT_POOL[4], CPT_POOL[9]],
    icdCodes: ICD_POOL.slice(2, 8),
    category: 'Musculoskeletal', payerName: 'Humana', lob: 'Commercial',
    tags: ['arthroscopy', 'surgical', 'knee'],
  },
]

function buildPolicies(): PolicyDocument[] {
  return RAW_POLICIES.map((raw) => {
    const versions = makeVersions(raw.id)
    const chunks   = makePolicyChunks(raw.id, 22)
    return {
      ...raw,
      versions,
      chunks,
      chunkCount:       chunks.length,
      lastIndexedAt:    new Date(Date.now() - Math.floor(s(raw.id.charCodeAt(4)) * 86400000 * 7)).toISOString(),
      retrievalQuality: rnd(raw.id.charCodeAt(4), 0.78, 0.97),
    }
  })
}

// ─── Semantic search mock ─────────────────────────────────────────────────────

function mockSearch(query: string, policies: PolicyDocument[]): SearchResult[] {
  if (!query.trim()) return []
  const q = query.toLowerCase()
  const results: SearchResult[] = []

  for (const policy of policies) {
    for (const chunk of policy.chunks) {
      const text = chunk.text.toLowerCase()
      let score = 0
      const qWords = q.split(/\s+/).filter(Boolean)
      for (const word of qWords) {
        if (text.includes(word)) score += 0.15
      }
      score += Math.random() * 0.1
      if (score > 0.12) {
        results.push({
          chunkId:    chunk.id,
          policyId:   policy.id,
          policyName: policy.name,
          chunkText:  chunk.text,
          score:      Math.min(0.99, score + s(chunk.index * 3) * 0.2),
          chunkType:  chunk.type,
          pageRef:    chunk.pageRef,
          sectionRef: chunk.sectionRef,
        })
      }
    }
  }

  return results.sort((a, b) => b.score - a.score).slice(0, 12)
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

const INITIAL_POLICIES = buildPolicies()

export function usePolicyManager() {
  const [policies, setPolicies]         = useState<PolicyDocument[]>(INITIAL_POLICIES)
  const [selectedId, setSelectedId]     = useState<string>(INITIAL_POLICIES[0].id)
  const [search, setSearch]             = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<PolicyStatus | 'all'>('all')
  const [searchQuery, setSearchQuery]   = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [isSearching, setIsSearching]   = useState(false)
  const [uploadDragging, setUploadDragging] = useState(false)

  const selectedPolicy = useMemo(
    () => policies.find((p) => p.id === selectedId) ?? policies[0],
    [policies, selectedId],
  )

  const filteredPolicies = useMemo(() => {
    return policies.filter((p) => {
      if (categoryFilter !== 'all' && p.category !== categoryFilter) return false
      if (statusFilter !== 'all' && p.status !== statusFilter) return false
      if (search) {
        const q = search.toLowerCase()
        return (
          p.name.toLowerCase().includes(q) ||
          p.policyNumber.toLowerCase().includes(q) ||
          p.payerName.toLowerCase().includes(q) ||
          p.tags.some((t) => t.includes(q))
        )
      }
      return true
    })
  }, [policies, categoryFilter, statusFilter, search])

  const runSearch = useCallback(() => {
    setIsSearching(true)
    setTimeout(() => {
      setSearchResults(mockSearch(searchQuery, policies))
      setIsSearching(false)
    }, 600)
  }, [searchQuery, policies])

  const updateMetadata = useCallback((id: string, patch: Partial<PolicyDocument>) => {
    setPolicies((prev) => prev.map((p) => p.id === id ? { ...p, ...patch } : p))
  }, [])

  const addCPT = useCallback((policyId: string, code: CPTCode) => {
    setPolicies((prev) => prev.map((p) =>
      p.id === policyId && !p.cptCodes.find((c) => c.code === code.code)
        ? { ...p, cptCodes: [...p.cptCodes, code] }
        : p,
    ))
  }, [])

  const removeCPT = useCallback((policyId: string, code: string) => {
    setPolicies((prev) => prev.map((p) =>
      p.id === policyId ? { ...p, cptCodes: p.cptCodes.filter((c) => c.code !== code) } : p,
    ))
  }, [])

  const addICD = useCallback((policyId: string, code: ICDCode) => {
    setPolicies((prev) => prev.map((p) =>
      p.id === policyId && !p.icdCodes.find((c) => c.code === code.code)
        ? { ...p, icdCodes: [...p.icdCodes, code] }
        : p,
    ))
  }, [])

  const removeICD = useCallback((policyId: string, code: string) => {
    setPolicies((prev) => prev.map((p) =>
      p.id === policyId ? { ...p, icdCodes: p.icdCodes.filter((c) => c.code !== code) } : p,
    ))
  }, [])

  const simulateUpload = useCallback((fileName: string) => {
    const newPolicy: PolicyDocument = {
      id:            `POL-${Date.now()}`,
      name:          fileName.replace(/\.(pdf|docx?)$/i, ''),
      policyNumber:  `MP-${new Date().getFullYear()}-NEW-${Math.floor(Math.random() * 900 + 100)}`,
      description:   'New policy document — edit metadata to complete setup.',
      effectiveDate: new Date().toISOString().slice(0, 10),
      expiryDate:    new Date(Date.now() + 365 * 86400000).toISOString().slice(0, 10),
      status:        'draft',
      currentVersion: '0.1',
      versions:      [{ version: '0.1', uploadedAt: new Date().toISOString(), uploadedBy: 'Current User', changeSummary: 'Initial upload', chunkCount: 0, status: 'draft', fileSize: '—' }],
      chunks:        [],
      cptCodes:      [],
      icdCodes:      [],
      category:      'Uncategorized',
      payerName:     '',
      lob:           '',
      tags:          [],
      chunkCount:    0,
      lastIndexedAt: new Date().toISOString(),
      retrievalQuality: 0,
    }
    setPolicies((prev) => [newPolicy, ...prev])
    setSelectedId(newPolicy.id)
  }, [])

  const categories = useMemo(() => ['all', ...Array.from(new Set(policies.map((p) => p.category)))], [policies])

  const CPT_POOL_ALL = CPT_POOL
  const ICD_POOL_ALL = ICD_POOL

  return {
    policies,
    filteredPolicies,
    selectedPolicy,
    setSelectedId,
    search, setSearch,
    categoryFilter, setCategoryFilter,
    statusFilter, setStatusFilter,
    searchQuery, setSearchQuery,
    searchResults,
    isSearching,
    runSearch,
    updateMetadata,
    addCPT, removeCPT,
    addICD, removeICD,
    simulateUpload,
    uploadDragging, setUploadDragging,
    categories,
    CPT_POOL_ALL,
    ICD_POOL_ALL,
  }
}
