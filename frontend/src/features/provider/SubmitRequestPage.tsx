import { useCallback, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Upload, X, CheckCircle, AlertCircle, FileText,
  ClipboardList, FolderOpen, ChevronDown, ChevronUp,
} from 'lucide-react'
import { casesService } from '@/services/cases.service'

// ── Constants ────────────────────────────────────────────────────────────────

const SERVICE_TYPES = [
  { value: 'IMAGING',                   label: 'Imaging (MRI, CT, X-Ray)' },
  { value: 'LABORATORY',                label: 'Laboratory' },
  { value: 'DURABLE_MEDICAL_EQUIPMENT', label: 'Durable Medical Equipment (DME)' },
  { value: 'MEDICATION',                label: 'Medication' },
  { value: 'PROCEDURE',                 label: 'Procedure / Surgery' },
  { value: 'OUTPATIENT_SURGERY',        label: 'Outpatient Surgery' },
  { value: 'INPATIENT_ADMISSION',       label: 'Inpatient Admission' },
  { value: 'SPECIALTY_REFERRAL',        label: 'Specialty Referral' },
  { value: 'HOME_HEALTH',               label: 'Home Health' },
  { value: 'BEHAVIORAL_HEALTH',         label: 'Behavioral Health' },
  { value: 'OTHER',                     label: 'Other' },
]

const PRIORITIES = [
  { value: 'ROUTINE',  label: 'Routine',  sub: '7–10 business days' },
  { value: 'URGENT',   label: 'Urgent',   sub: '24–72 hours' },
  { value: 'EMERGENT', label: 'Emergent', sub: 'Same day' },
]

const GENDERS = ['Male', 'Female', 'Other', 'Unknown']

const ACCEPTED_EXTS = '.pdf,.doc,.docx,.png,.jpg,.jpeg,.tif,.tiff,.txt'
const MAX_FILE_MB   = 50

// ── Sub-components ────────────────────────────────────────────────────────────

function OptionalTag() {
  return (
    <span className="ml-1.5 text-[10px] font-medium uppercase tracking-wide text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">
      optional
    </span>
  )
}

function SectionCard({
  title,
  icon,
  hint,
  collapsible,
  defaultOpen = true,
  children,
}: {
  title: string
  icon: React.ReactNode
  hint?: string
  collapsible?: boolean
  defaultOpen?: boolean
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="card overflow-hidden">
      <button
        type="button"
        className={`w-full flex items-center gap-2.5 px-5 py-4 border-b border-gray-100 text-left ${collapsible ? 'hover:bg-gray-50 transition-colors' : ''}`}
        onClick={() => collapsible && setOpen((o) => !o)}
      >
        <span className="text-blue-600">{icon}</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-900">{title}</p>
          {hint && <p className="text-xs text-gray-400 mt-0.5">{hint}</p>}
        </div>
        {collapsible && (open ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />)}
      </button>
      {open && <div className="p-5">{children}</div>}
    </div>
  )
}

function FileRow({ file, onRemove }: { file: File; onRemove: () => void }) {
  const ext = file.name.split('.').pop()?.toUpperCase() ?? 'FILE'
  const sizeMB = (file.size / 1024 / 1024).toFixed(1)
  return (
    <div className="flex items-center gap-3 px-3 py-2.5 bg-gray-50 border border-gray-200 rounded-lg">
      <div className="flex-shrink-0 w-8 h-8 bg-blue-100 rounded flex items-center justify-center">
        <FileText className="w-4 h-4 text-blue-600" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-800 truncate">{file.name}</p>
        <p className="text-xs text-gray-400">{ext} · {sizeMB} MB</p>
      </div>
      <button
        type="button"
        onClick={onRemove}
        className="flex-shrink-0 p-1 text-gray-400 hover:text-red-500 rounded transition-colors"
        aria-label="Remove file"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  )
}

// ── Success screen ────────────────────────────────────────────────────────────

function SuccessScreen({
  caseNumber,
  message,
  onNew,
}: {
  caseNumber: string
  message: string
  onNew: () => void
}) {
  const navigate = useNavigate()
  return (
    <div className="max-w-lg mx-auto mt-16 text-center">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-100 mb-5">
        <CheckCircle className="w-8 h-8 text-green-600" />
      </div>
      <h2 className="text-xl font-semibold text-gray-900 mb-1">Request Submitted</h2>
      <p className="text-sm text-gray-500 mb-1">
        Case <span className="font-mono font-semibold text-blue-600">{caseNumber}</span> has been created.
      </p>
      <p className="text-sm text-gray-400 mb-2">{message}</p>
      <p className="text-xs text-gray-400 mb-7">
        AI extraction and evaluation will begin shortly. Track progress in My Cases.
      </p>
      <div className="flex gap-3 justify-center">
        <button onClick={() => navigate('/provider/cases')} className="btn-primary">
          View My Cases
        </button>
        <button onClick={onNew} className="btn-secondary">
          New Request
        </button>
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

function initForm() {
  return {
    providerNPI: '', providerFirstName: '', providerLastName: '',
    providerSpecialty: '', providerOrganization: '',
    patientFirstName: '', patientLastName: '', patientDOB: '',
    patientMemberId: '', patientGender: '', patientGroupNumber: '',
    patientInsurancePlan: '',
    serviceType: '', priority: 'ROUTINE',
    cptCodes: '', icdCodes: '', clinicalNotes: '',
  }
}

export default function SubmitRequestPage() {
  const navigate = useNavigate()
  const dropRef  = useRef<HTMLLabelElement>(null)

  const [form, setForm]       = useState(initForm)
  const [files, setFiles]     = useState<File[]>([])
  const [dragging, setDragging] = useState(false)
  const [submitting, setSubmit] = useState(false)
  const [error, setError]     = useState<string | null>(null)
  const [result, setResult]   = useState<{ caseNumber: string; message: string } | null>(null)

  // Derived: whether form has any patient name filled
  const hasPatientName = form.patientFirstName.trim() !== '' && form.patientLastName.trim() !== ''
  const hasFiles       = files.length > 0

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }))
  }

  function addFiles(incoming: FileList | null) {
    if (!incoming) return
    const valid = Array.from(incoming).filter((f) => {
      if (f.size > MAX_FILE_MB * 1024 * 1024) {
        setError(`"${f.name}" exceeds the ${MAX_FILE_MB} MB limit.`)
        return false
      }
      return true
    })
    setFiles((prev) => {
      const existing = new Set(prev.map((f) => f.name + f.size))
      return [...prev, ...valid.filter((f) => !existing.has(f.name + f.size))]
    })
  }

  // ── Drag-and-drop ──────────────────────────────────────────────────────────
  const onDragOver = useCallback((e: React.DragEvent) => { e.preventDefault(); setDragging(true) }, [])
  const onDragLeave = useCallback(() => setDragging(false), [])
  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    addFiles(e.dataTransfer.files)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Submit ─────────────────────────────────────────────────────────────────
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    const npiClean = form.providerNPI.replace(/\D/g, '')
    if (npiClean.length !== 10) {
      setError('Provider NPI must be exactly 10 digits.')
      return
    }
    if (!hasFiles && !hasPatientName) {
      setError('Please upload at least one document OR enter the patient\'s first and last name.')
      return
    }

    setSubmit(true)
    try {
      const fd = new FormData()

      // Files (all appended under same field name "files")
      files.forEach((f) => fd.append('files', f))

      // Provider
      fd.append('provider_npi', npiClean)
      if (form.providerFirstName.trim())    fd.append('provider_first_name',   form.providerFirstName.trim())
      if (form.providerLastName.trim())     fd.append('provider_last_name',    form.providerLastName.trim())
      if (form.providerSpecialty.trim())    fd.append('provider_specialty',    form.providerSpecialty.trim())
      if (form.providerOrganization.trim()) fd.append('provider_organization', form.providerOrganization.trim())

      // Patient
      if (form.patientFirstName.trim())   fd.append('patient_first_name',    form.patientFirstName.trim())
      if (form.patientLastName.trim())    fd.append('patient_last_name',     form.patientLastName.trim())
      if (form.patientDOB)               fd.append('patient_dob',           form.patientDOB)
      if (form.patientMemberId.trim())    fd.append('patient_member_id',     form.patientMemberId.trim())
      if (form.patientGender)            fd.append('patient_gender',        form.patientGender)
      if (form.patientGroupNumber.trim()) fd.append('patient_group_number',  form.patientGroupNumber.trim())
      if (form.patientInsurancePlan.trim()) fd.append('patient_insurance_plan', form.patientInsurancePlan.trim())

      // Clinical
      if (form.serviceType)           fd.append('service_type',    form.serviceType)
      fd.append('priority',           form.priority)
      if (form.cptCodes.trim())       fd.append('cpt_codes',       form.cptCodes.trim())
      if (form.icdCodes.trim())       fd.append('icd_codes',       form.icdCodes.trim())
      if (form.clinicalNotes.trim())  fd.append('clinical_notes',  form.clinicalNotes.trim())

      const res = await casesService.submitIntake(fd)
      setResult({ caseNumber: res.case_number, message: res.message })
    } catch (err: any) {
      setError(err?.message ?? 'Submission failed. Please try again.')
    } finally {
      setSubmit(false)
    }
  }

  function resetAll() {
    setResult(null)
    setFiles([])
    setForm(initForm())
    setError(null)
  }

  // ── Result screen ──────────────────────────────────────────────────────────
  if (result) {
    return <SuccessScreen caseNumber={result.caseNumber} message={result.message} onNew={resetAll} />
  }

  // ── Form ───────────────────────────────────────────────────────────────────
  return (
    <div className="max-w-2xl">
      {/* Header */}
      <div className="page-header mb-2">
        <h1 className="page-title">Submit Prior Authorization Request</h1>
        <p className="page-subtitle">
          Upload patient documents, fill the form, or use both — all fields except Provider NPI are optional.
        </p>
      </div>

      {/* Mode hint bar */}
      <div className="flex items-start gap-3 mb-5 px-4 py-3 bg-blue-50 border border-blue-100 rounded-lg text-sm text-blue-700">
        <AlertCircle className="w-4 h-4 mt-0.5 shrink-0 text-blue-500" />
        <span>
          <strong>Flexible submission:</strong> Upload PDFs, scanned documents, or images and the AI will extract
          patient demographics, diagnoses, and procedure codes automatically. You can also fill the form manually, or do both.
        </span>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">

        {/* ── Document Upload ────────────────────────────────────────────── */}
        <SectionCard
          title="Patient Documents"
          icon={<FolderOpen className="w-5 h-5" />}
          hint="PDF, DOCX, PNG, JPG, TIFF — multiple files allowed, all for the same patient"
        >
          {/* Drop zone */}
          <label
            ref={dropRef}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            className={`flex flex-col items-center justify-center gap-2 w-full h-36 border-2 border-dashed rounded-xl cursor-pointer transition-colors
              ${dragging
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
              }`}
          >
            <Upload className={`w-7 h-7 ${dragging ? 'text-blue-500' : 'text-gray-400'}`} />
            <div className="text-center">
              <p className="text-sm font-medium text-gray-600">
                {dragging ? 'Drop files here' : 'Drag & drop files or click to browse'}
              </p>
              <p className="text-xs text-gray-400 mt-0.5">PDF · DOCX · PNG · JPG · TIFF · TXT — up to {MAX_FILE_MB} MB each</p>
            </div>
            <input
              type="file"
              className="hidden"
              multiple
              accept={ACCEPTED_EXTS}
              onChange={(e) => addFiles(e.target.files)}
            />
          </label>

          {/* File list */}
          {files.length > 0 && (
            <div className="mt-3 space-y-2">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                {files.length} file{files.length !== 1 ? 's' : ''} queued
              </p>
              {files.map((f, i) => (
                <FileRow key={f.name + i} file={f} onRemove={() => setFiles((p) => p.filter((_, idx) => idx !== i))} />
              ))}
            </div>
          )}

          {!hasFiles && (
            <p className="mt-2 text-xs text-gray-400 text-center">
              No files yet — you can still submit using the form below.
            </p>
          )}
        </SectionCard>

        {/* ── Provider ──────────────────────────────────────────────────── */}
        <SectionCard
          title="Ordering Provider"
          icon={<ClipboardList className="w-5 h-5" />}
          hint="NPI is required. Other provider fields are optional."
        >
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                NPI <span className="text-red-500">*</span>
              </label>
              <input
                name="providerNPI"
                value={form.providerNPI}
                onChange={handleChange}
                className="input"
                placeholder="10-digit National Provider Identifier"
                inputMode="numeric"
                maxLength={10}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">First Name <OptionalTag /></label>
              <input name="providerFirstName" value={form.providerFirstName} onChange={handleChange} className="input" placeholder="Dr. First" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Last Name <OptionalTag /></label>
              <input name="providerLastName" value={form.providerLastName} onChange={handleChange} className="input" placeholder="Last" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Specialty <OptionalTag /></label>
              <input name="providerSpecialty" value={form.providerSpecialty} onChange={handleChange} className="input" placeholder="e.g. Orthopedic Surgery" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Organization <OptionalTag /></label>
              <input name="providerOrganization" value={form.providerOrganization} onChange={handleChange} className="input" placeholder="Clinic / hospital name" />
            </div>
          </div>
        </SectionCard>

        {/* ── Patient ───────────────────────────────────────────────────── */}
        <SectionCard
          title="Patient Information"
          icon={<FileText className="w-5 h-5" />}
          hint={hasFiles
            ? "AI will extract missing fields from your uploaded documents."
            : "Required if no documents are uploaded."}
          collapsible
          defaultOpen
        >
          {!hasFiles && !hasPatientName && (
            <div className="mb-4 px-3 py-2 bg-amber-50 border border-amber-100 rounded text-xs text-amber-700">
              Either upload documents above <strong>or</strong> enter the patient's first and last name.
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                First Name {hasFiles ? <OptionalTag /> : <span className="text-red-500">*</span>}
              </label>
              <input
                name="patientFirstName"
                value={form.patientFirstName}
                onChange={handleChange}
                className="input"
                placeholder={hasFiles ? 'AI will extract if blank' : 'Required'}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Last Name {hasFiles ? <OptionalTag /> : <span className="text-red-500">*</span>}
              </label>
              <input
                name="patientLastName"
                value={form.patientLastName}
                onChange={handleChange}
                className="input"
                placeholder={hasFiles ? 'AI will extract if blank' : 'Required'}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Date of Birth <OptionalTag /></label>
              <input name="patientDOB" type="date" value={form.patientDOB} onChange={handleChange} className="input" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Member ID <OptionalTag /></label>
              <input name="patientMemberId" value={form.patientMemberId} onChange={handleChange} className="input" placeholder="Insurance member ID" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Gender <OptionalTag /></label>
              <select name="patientGender" value={form.patientGender} onChange={handleChange} className="input">
                <option value="">Select…</option>
                {GENDERS.map((g) => <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Group Number <OptionalTag /></label>
              <input name="patientGroupNumber" value={form.patientGroupNumber} onChange={handleChange} className="input" placeholder="Insurance group number" />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Insurance Plan <OptionalTag /></label>
              <input name="patientInsurancePlan" value={form.patientInsurancePlan} onChange={handleChange} className="input" placeholder="e.g. BlueCross BlueShield PPO" />
            </div>
          </div>
        </SectionCard>

        {/* ── Clinical Details ──────────────────────────────────────────── */}
        <SectionCard
          title="Clinical Details"
          icon={<ClipboardList className="w-5 h-5" />}
          hint="All optional — AI extracts codes and justification from uploaded documents."
          collapsible
          defaultOpen={!hasFiles}
        >
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Service Type <OptionalTag /></label>
              <select name="serviceType" value={form.serviceType} onChange={handleChange} className="input">
                <option value="">AI will determine…</option>
                {SERVICE_TYPES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
              <div className="grid grid-cols-3 gap-2">
                {PRIORITIES.map((p) => (
                  <label
                    key={p.value}
                    className={`flex flex-col items-center justify-center p-2 border rounded-lg cursor-pointer text-center transition-colors text-xs
                      ${form.priority === p.value
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-200 text-gray-600 hover:border-gray-300'
                      }`}
                  >
                    <input
                      type="radio"
                      name="priority"
                      value={p.value}
                      checked={form.priority === p.value}
                      onChange={handleChange}
                      className="sr-only"
                    />
                    <span className="font-semibold">{p.label}</span>
                    <span className="text-[10px] mt-0.5 opacity-70">{p.sub}</span>
                  </label>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">CPT Code(s) <OptionalTag /></label>
              <input name="cptCodes" value={form.cptCodes} onChange={handleChange} className="input" placeholder="e.g. 72148, 72141" />
              <p className="text-xs text-gray-400 mt-1">Comma-separated</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">ICD-10 Code(s) <OptionalTag /></label>
              <input name="icdCodes" value={form.icdCodes} onChange={handleChange} className="input" placeholder="e.g. M54.5, M51.16" />
              <p className="text-xs text-gray-400 mt-1">Comma-separated</p>
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Clinical Notes <OptionalTag /></label>
              <textarea
                name="clinicalNotes"
                value={form.clinicalNotes}
                onChange={handleChange}
                rows={4}
                className="input resize-none"
                placeholder="Clinical justification, failed conservative treatments, relevant history… (AI fills this from documents if left blank)"
              />
            </div>
          </div>
        </SectionCard>

        {/* ── Submit bar ────────────────────────────────────────────────── */}
        <div className="flex items-center gap-3 pt-1">
          <button
            type="submit"
            disabled={submitting}
            className="btn-primary px-8 disabled:opacity-60"
          >
            {submitting ? 'Submitting…' : 'Submit Request'}
          </button>
          <button type="button" onClick={() => navigate(-1)} className="btn-secondary">
            Cancel
          </button>
          <p className="ml-auto text-xs text-gray-400">
            {hasFiles && `${files.length} file${files.length !== 1 ? 's' : ''} ready · `}
            {hasPatientName ? `Patient: ${form.patientFirstName} ${form.patientLastName}` : 'Patient info from documents'}
          </p>
        </div>

      </form>
    </div>
  )
}
