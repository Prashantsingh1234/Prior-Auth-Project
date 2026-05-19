import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Search, Upload, RefreshCw, Trash2, Database, FileText } from 'lucide-react'
import { policiesService, type PolicyListItem, type PolicyProcessingStatus } from '@/services/policies.service'

const STATUS_LABEL: Record<PolicyProcessingStatus, string> = {
  UPLOADED: 'Uploaded',
  EXTRACTED: 'Text Extracted',
  CHUNKED: 'Chunked',
  EMBEDDED: 'Embedded',
  STORED: 'Stored',
  FAILED: 'Failed',
}

function StatusPill({ status }: { status: PolicyProcessingStatus }) {
  const style =
    status === 'FAILED'
      ? 'bg-red-100 text-red-700'
      : status === 'STORED'
        ? 'bg-green-100 text-green-700'
        : status === 'UPLOADED'
          ? 'bg-gray-100 text-gray-700'
          : 'bg-blue-100 text-blue-700'

  return <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${style}`}>{STATUS_LABEL[status]}</span>
}

function formatDate(iso?: string | null) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString()
}

function UploadModal(props: { open: boolean; onClose: () => void; onUploaded: () => void }) {
  const { open, onClose, onUploaded } = props
  const [file, setFile] = useState<File | null>(null)
  const [policyName, setPolicyName] = useState('')
  const [version, setVersion] = useState('v1')
  const [policyType, setPolicyType] = useState('')
  const [effectiveDate, setEffectiveDate] = useState<string>('')
  const [namespace, setNamespace] = useState('')

  const upload = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error('Select a file')
      if (!policyName.trim()) throw new Error('Enter policy name')
      const fd = new FormData()
      fd.append('file', file)
      fd.append('policy_name', policyName.trim())
      fd.append('policy_version', version.trim() || 'v1')
      if (policyType.trim()) fd.append('policy_type', policyType.trim())
      if (effectiveDate) fd.append('effective_date', effectiveDate)
      if (namespace.trim()) fd.append('pinecone_namespace', namespace.trim())
      return policiesService.uploadPolicy(fd)
    },
    onSuccess: () => {
      toast.success('Policy uploaded')
      onUploaded()
      onClose()
      setFile(null)
      setPolicyName('')
      setPolicyType('')
      setVersion('v1')
      setEffectiveDate('')
      setNamespace('')
    },
    onError: (e: any) => toast.error(e?.message ?? 'Upload failed'),
  })

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
      <div className="card w-full max-w-xl shadow-lg">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-gray-900">Upload Policy</h2>
            <p className="text-xs text-gray-500 mt-0.5">Upload first, then process manually (extract → chunk → embed → store).</p>
          </div>
          <button className="btn-ghost" onClick={onClose}>
            Close
          </button>
        </div>

        <div className="p-5 space-y-4">
          <div>
            <label className="text-xs font-semibold text-gray-600">Policy Document</label>
            <input
              className="input mt-1"
              type="file"
              accept=".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg,.tif,.tiff"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-gray-600">Policy Name</label>
              <input className="input mt-1" value={policyName} onChange={(e) => setPolicyName(e.target.value)} placeholder="e.g., MRI — Lumbar Spine" />
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-600">Version</label>
              <input className="input mt-1" value={version} onChange={(e) => setVersion(e.target.value)} placeholder="v1" />
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-600">Policy Type</label>
              <input className="input mt-1" value={policyType} onChange={(e) => setPolicyType(e.target.value)} placeholder="Imaging, DME, Medication…" />
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-600">Effective Date</label>
              <input className="input mt-1" value={effectiveDate} onChange={(e) => setEffectiveDate(e.target.value)} type="date" />
            </div>
            <div className="md:col-span-2">
              <label className="text-xs font-semibold text-gray-600">Pinecone Namespace (optional)</label>
              <input className="input mt-1" value={namespace} onChange={(e) => setNamespace(e.target.value)} placeholder="Leave blank to use default" />
            </div>
          </div>
        </div>

        <div className="px-5 py-4 border-t border-gray-100 flex items-center justify-end gap-2">
          <button className="btn-secondary" onClick={onClose} disabled={upload.isPending}>
            Cancel
          </button>
          <button className="btn-primary" onClick={() => upload.mutate()} disabled={upload.isPending}>
            <Upload className="w-4 h-4" />
            {upload.isPending ? 'Uploading…' : 'Upload'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function PolicyManagementPage() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<'All' | PolicyProcessingStatus>('All')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [uploadOpen, setUploadOpen] = useState(false)

  const policiesQ = useQuery({
    queryKey: ['policies', { search, status }],
    queryFn: async () => {
      const res = await policiesService.listPolicies({
        page: 1,
        page_size: 50,
        search: search || undefined,
        status: status === 'All' ? undefined : status,
      })
      return res
    },
  })

  const policies = policiesQ.data?.data.items ?? []
  const selected = useMemo(() => policies.find((p) => p.id === selectedId) ?? null, [policies, selectedId])

  const chunksQ = useQuery({
    queryKey: ['policy-chunks', selectedId],
    enabled: !!selectedId,
    queryFn: async () => policiesService.listChunks(selectedId!, { page: 1, page_size: 200 }),
  })

  const processM = useMutation({
    mutationFn: async (policyId: string) => policiesService.processPolicy(policyId),
    onSuccess: async () => {
      toast.success('Policy processed')
      await qc.invalidateQueries({ queryKey: ['policies'] })
      if (selectedId) await qc.invalidateQueries({ queryKey: ['policy-chunks', selectedId] })
    },
    onError: (e: any) => toast.error(e?.message ?? 'Processing failed'),
  })

  const deleteEmbeddingsM = useMutation({
    mutationFn: async (policyId: string) => policiesService.deleteEmbeddings(policyId),
    onSuccess: async () => {
      toast.success('Embeddings deleted')
      await qc.invalidateQueries({ queryKey: ['policies'] })
    },
    onError: (e: any) => toast.error(e?.message ?? 'Delete failed'),
  })

  const deleteChunksM = useMutation({
    mutationFn: async (policyId: string) => policiesService.deleteChunks(policyId),
    onSuccess: async () => {
      toast.success('Chunks deleted')
      await qc.invalidateQueries({ queryKey: ['policies'] })
      if (selectedId) await qc.invalidateQueries({ queryKey: ['policy-chunks', selectedId] })
    },
    onError: (e: any) => toast.error(e?.message ?? 'Delete failed'),
  })

  const deletePolicyM = useMutation({
    mutationFn: async (policyId: string) => policiesService.deletePolicy(policyId),
    onSuccess: async () => {
      toast.success('Policy deleted')
      setSelectedId(null)
      await qc.invalidateQueries({ queryKey: ['policies'] })
    },
    onError: (e: any) => toast.error(e?.message ?? 'Delete failed'),
  })

  const chunks = chunksQ.data?.data.items ?? []

  return (
    <div>
      <UploadModal open={uploadOpen} onClose={() => setUploadOpen(false)} onUploaded={() => qc.invalidateQueries({ queryKey: ['policies'] })} />

      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">Policy Management</h1>
          <p className="page-subtitle">Manual upload, processing, chunk transparency, and Pinecone management</p>
        </div>
        <button className="btn-primary" onClick={() => setUploadOpen(true)}>
          <Upload className="w-4 h-4" />
          Upload Policy
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-5">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by policy name, key, or filename…" className="input pl-9 w-[360px]" />
        </div>
        <select value={status} onChange={(e) => setStatus(e.target.value as any)} className="input w-auto">
          <option value="All">All Statuses</option>
          <option value="UPLOADED">Uploaded</option>
          <option value="STORED">Stored</option>
          <option value="FAILED">Failed</option>
          <option value="EXTRACTED">Extracted</option>
          <option value="CHUNKED">Chunked</option>
          <option value="EMBEDDED">Embedded</option>
        </select>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_420px] gap-4">
        <div className="card overflow-hidden">
          <table className="data-table">
            <thead>
              <tr>
                <th>Policy</th>
                <th>Version</th>
                <th>Status</th>
                <th>Chunks</th>
                <th>Namespace</th>
                <th>Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {policiesQ.isLoading && (
                <tr>
                  <td colSpan={6} className="text-gray-500">
                    Loading…
                  </td>
                </tr>
              )}
              {!policiesQ.isLoading && policies.length === 0 && (
                <tr>
                  <td colSpan={6} className="text-gray-500">
                    No policies found.
                  </td>
                </tr>
              )}
              {policies.map((p: PolicyListItem) => (
                <tr key={p.id} className={selectedId === p.id ? 'bg-blue-50/40' : ''} onClick={() => setSelectedId(p.id)} style={{ cursor: 'pointer' }}>
                  <td>
                    <div className="flex items-start gap-2">
                      <FileText className="w-4 h-4 text-gray-400 mt-0.5" />
                      <div>
                        <div className="font-medium text-gray-900">{p.policy_name}</div>
                        <div className="text-xs text-gray-400 font-mono">{p.policy_key}</div>
                      </div>
                    </div>
                  </td>
                  <td className="font-mono text-xs text-gray-600">{p.policy_version}</td>
                  <td>
                    <StatusPill status={p.processing_status} />
                    {p.last_error && <div className="text-xs text-red-600 mt-1 line-clamp-1">{p.last_error}</div>}
                  </td>
                  <td className="font-mono text-xs text-gray-600">{p.total_chunks}</td>
                  <td className="font-mono text-xs text-gray-600">{p.pinecone_namespace}</td>
                  <td className="text-gray-500 text-sm">{formatDate(p.upload_date)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-900">Policy Details</h2>
            <p className="text-xs text-gray-500 mt-0.5">Select a policy to view chunks and actions</p>
          </div>

          {!selected && <div className="p-5 text-sm text-gray-500">No policy selected.</div>}

          {selected && (
            <div className="p-5 space-y-4">
              <div>
                <div className="font-medium text-gray-900">{selected.policy_name}</div>
                <div className="text-xs text-gray-400 font-mono mt-0.5">{selected.policy_key}</div>
              </div>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Version</div>
                  <div className="mt-1 font-mono text-xs text-gray-700">{selected.policy_version}</div>
                </div>
                <div>
                  <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Effective</div>
                  <div className="mt-1 text-gray-700">{selected.effective_date ?? '—'}</div>
                </div>
                <div>
                  <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Namespace</div>
                  <div className="mt-1 font-mono text-xs text-gray-700">{selected.pinecone_namespace}</div>
                </div>
                <div>
                  <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Chunks</div>
                  <div className="mt-1 font-mono text-xs text-gray-700">{selected.total_chunks}</div>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                <button className="btn-primary" onClick={() => processM.mutate(selected.id)} disabled={processM.isPending}>
                  <RefreshCw className="w-4 h-4" />
                  {processM.isPending ? 'Processing…' : 'Process / Reprocess'}
                </button>
                <button className="btn-secondary" onClick={() => deleteEmbeddingsM.mutate(selected.id)} disabled={deleteEmbeddingsM.isPending}>
                  <Database className="w-4 h-4" />
                  Delete Embeddings
                </button>
                <button
                  className="btn-secondary"
                  onClick={() => {
                    if (confirm('Delete processed chunks from the database? (Does not delete Pinecone vectors.)')) deleteChunksM.mutate(selected.id)
                  }}
                  disabled={deleteChunksM.isPending}
                >
                  Delete Chunks
                </button>
                <button
                  className="btn-deny"
                  onClick={() => {
                    if (confirm('Delete this policy (vectors + metadata)? This cannot be undone.')) deletePolicyM.mutate(selected.id)
                  }}
                  disabled={deletePolicyM.isPending}
                >
                  <Trash2 className="w-4 h-4" />
                  Delete Policy
                </button>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Chunks</p>
                  <span className="text-xs text-gray-400">{chunksQ.isFetching ? 'Loading…' : `${chunks.length}`}</span>
                </div>

                <div className="space-y-2 max-h-[420px] overflow-auto pr-1">
                  {chunks.map((c) => (
                    <div key={c.id} className="border border-gray-200 rounded-md p-3 bg-white">
                      <div className="flex items-center justify-between">
                        <div className="font-mono text-xs text-gray-500">#{c.chunk_index}</div>
                        <div className="text-xs text-gray-400">
                          {c.chunk_length} chars • overlap {c.chunk_overlap}
                        </div>
                      </div>
                      <div className="text-sm text-gray-700 mt-2 whitespace-pre-wrap">{c.preview || '—'}</div>
                      <div className="flex flex-wrap gap-1 mt-2">
                        {(c.cpt_codes || []).slice(0, 6).map((code) => (
                          <span key={code} className="px-1.5 py-0.5 bg-gray-100 text-gray-600 text-xs font-mono rounded">
                            {code}
                          </span>
                        ))}
                        {(c.icd_codes || []).slice(0, 6).map((code) => (
                          <span key={code} className="px-1.5 py-0.5 bg-blue-50 text-blue-700 text-xs font-mono rounded">
                            {code}
                          </span>
                        ))}
                      </div>
                      <details className="mt-2">
                        <summary className="text-xs text-gray-500 cursor-pointer select-none">Metadata</summary>
                        <pre className="mt-2 text-xs bg-gray-50 border border-gray-200 rounded p-2 overflow-auto whitespace-pre-wrap">
                          {JSON.stringify(c.metadata ?? {}, null, 2)}
                        </pre>
                      </details>
                    </div>
                  ))}
                  {chunksQ.isLoading && <div className="text-sm text-gray-500">Loading chunks…</div>}
                  {!chunksQ.isLoading && selected.total_chunks === 0 && <div className="text-sm text-gray-500">No chunks yet. Click “Process / Reprocess”.</div>}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
