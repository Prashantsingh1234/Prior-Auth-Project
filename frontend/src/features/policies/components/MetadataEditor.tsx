import { useState } from 'react'
import { motion } from 'framer-motion'
import { Edit3, Save, X, Calendar, Building2, Tag, Plus } from 'lucide-react'
import type { PolicyDocument, PolicyStatus } from '../hooks/usePolicyManager'

const STATUS_OPTIONS: PolicyStatus[] = ['active', 'draft', 'under_review', 'archived']
const CATEGORIES = ['Musculoskeletal', 'Radiology', 'Rehabilitation', 'Cardiovascular', 'Oncology', 'Neurology', 'Endocrine', 'Behavioral Health', 'Uncategorized']
const LOB_OPTIONS = ['Commercial', 'Medicare Advantage', 'Medicaid', 'Self-Insured', 'ACA Marketplace']

interface FieldProps {
  label:    string
  children: React.ReactNode
}

function Field({ label, children }: FieldProps) {
  return (
    <div>
      <label className="block text-[9px] font-semibold uppercase tracking-wide text-[var(--text-4)] mb-1">{label}</label>
      {children}
    </div>
  )
}

const inputCls = 'w-full px-2.5 py-1.5 rounded-lg text-xs text-[var(--text-1)] outline-none transition-colors'
const inputStyle = { background: 'var(--surface)', border: '1px solid var(--border)' }
const inputFocusStyle = { border: '1px solid #6366f1' }

interface MetadataEditorProps {
  policy:         PolicyDocument
  onSave:         (patch: Partial<PolicyDocument>) => void
}

export function MetadataEditor({ policy, onSave }: MetadataEditorProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft]     = useState<Partial<PolicyDocument>>({})
  const [newTag, setNewTag]   = useState('')

  function startEdit() {
    setDraft({
      name:          policy.name,
      description:   policy.description,
      policyNumber:  policy.policyNumber,
      effectiveDate: policy.effectiveDate,
      expiryDate:    policy.expiryDate,
      status:        policy.status,
      category:      policy.category,
      payerName:     policy.payerName,
      lob:           policy.lob,
      tags:          [...policy.tags],
    })
    setEditing(true)
  }

  function save() {
    onSave(draft)
    setEditing(false)
  }

  function cancel() {
    setDraft({})
    setEditing(false)
  }

  function set<K extends keyof PolicyDocument>(key: K, val: PolicyDocument[K]) {
    setDraft((d) => ({ ...d, [key]: val }))
  }

  function addTag() {
    const t = newTag.trim().toLowerCase()
    if (!t) return
    const tags = draft.tags ?? []
    if (!tags.includes(t)) set('tags', [...tags, t])
    setNewTag('')
  }

  function removeTag(tag: string) {
    set('tags', (draft.tags ?? []).filter((t) => t !== tag))
  }

  const d = editing ? draft : policy

  return (
    <div className="p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-bold uppercase tracking-wide text-[var(--text-3)]">Policy Metadata</span>
        {editing ? (
          <div className="flex items-center gap-1.5">
            <motion.button
              whileTap={{ scale: 0.96 }}
              onClick={cancel}
              className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px] text-[var(--text-3)] hover:text-red-400 transition-colors"
              style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
            >
              <X className="w-3 h-3" /> Cancel
            </motion.button>
            <motion.button
              whileTap={{ scale: 0.96 }}
              onClick={save}
              className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px] font-semibold text-white transition-colors"
              style={{ background: '#6366f1', border: '1px solid #6366f1' }}
            >
              <Save className="w-3 h-3" /> Save
            </motion.button>
          </div>
        ) : (
          <motion.button
            whileTap={{ scale: 0.96 }}
            onClick={startEdit}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px] text-[var(--text-3)] hover:text-[var(--text-1)] transition-colors"
            style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
          >
            <Edit3 className="w-3 h-3" /> Edit
          </motion.button>
        )}
      </div>

      {/* Read-only view */}
      {!editing && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl p-3" style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
              <p className="text-[8px] text-[var(--text-4)] uppercase tracking-wide mb-1">Policy Number</p>
              <p className="text-[10px] font-mono font-semibold text-[var(--text-1)]">{policy.policyNumber}</p>
            </div>
            <div className="rounded-xl p-3" style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
              <p className="text-[8px] text-[var(--text-4)] uppercase tracking-wide mb-1">Status</p>
              <p className="text-[10px] font-semibold capitalize text-[var(--text-1)]">{policy.status.replace('_', ' ')}</p>
            </div>
            <div className="rounded-xl p-3 col-span-2" style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
              <p className="text-[8px] text-[var(--text-4)] uppercase tracking-wide mb-1">Policy Name</p>
              <p className="text-[11px] font-semibold text-[var(--text-1)]">{policy.name}</p>
            </div>
            <div className="rounded-xl p-3 col-span-2" style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
              <p className="text-[8px] text-[var(--text-4)] uppercase tracking-wide mb-1">Description</p>
              <p className="text-[10px] text-[var(--text-2)] leading-relaxed">{policy.description}</p>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {[
              { icon: Calendar, label: 'Effective', value: policy.effectiveDate },
              { icon: Calendar, label: 'Expires',   value: policy.expiryDate },
              { icon: Building2, label: 'Payer',    value: policy.payerName },
              { icon: Building2, label: 'Category', value: policy.category },
              { icon: Building2, label: 'LOB',      value: policy.lob },
              { icon: Tag,       label: 'Version',  value: `v${policy.currentVersion}` },
            ].map((item) => (
              <div key={item.label} className="rounded-lg p-2" style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
                <div className="flex items-center gap-1 mb-0.5">
                  <item.icon className="w-2.5 h-2.5 text-[var(--text-4)]" />
                  <p className="text-[8px] text-[var(--text-4)] uppercase tracking-wide">{item.label}</p>
                </div>
                <p className="text-[9px] font-semibold text-[var(--text-1)] truncate">{item.value || '—'}</p>
              </div>
            ))}
          </div>
          {policy.tags.length > 0 && (
            <div className="flex items-center gap-1.5 flex-wrap">
              <Tag className="w-3 h-3 text-[var(--text-4)]" />
              {policy.tags.map((tag) => (
                <span key={tag} className="px-2 py-0.5 rounded-full text-[9px] font-medium bg-[var(--elevated)] text-[var(--text-3)] border border-[var(--border)]">{tag}</span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Edit form */}
      {editing && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-3"
        >
          <div className="grid grid-cols-2 gap-3">
            <Field label="Policy Name">
              <input
                className={inputCls} style={inputStyle}
                value={d.name ?? ''} onChange={(e) => set('name', e.target.value)}
                onFocus={(e) => Object.assign(e.target.style, inputFocusStyle)}
                onBlur={(e) => Object.assign(e.target.style, inputStyle)}
              />
            </Field>
            <Field label="Policy Number">
              <input
                className={`${inputCls} font-mono`} style={inputStyle}
                value={d.policyNumber ?? ''} onChange={(e) => set('policyNumber', e.target.value)}
                onFocus={(e) => Object.assign(e.target.style, inputFocusStyle)}
                onBlur={(e) => Object.assign(e.target.style, inputStyle)}
              />
            </Field>
          </div>

          <Field label="Description">
            <textarea
              rows={3}
              className={`${inputCls} resize-none`} style={inputStyle}
              value={d.description ?? ''} onChange={(e) => set('description', e.target.value)}
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Status">
              <select
                className={inputCls} style={inputStyle}
                value={d.status ?? 'draft'}
                onChange={(e) => set('status', e.target.value as PolicyStatus)}
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>{s.replace('_', ' ')}</option>
                ))}
              </select>
            </Field>
            <Field label="Category">
              <select
                className={inputCls} style={inputStyle}
                value={d.category ?? ''} onChange={(e) => set('category', e.target.value)}
              >
                {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </Field>
            <Field label="Payer Name">
              <input
                className={inputCls} style={inputStyle}
                value={d.payerName ?? ''} onChange={(e) => set('payerName', e.target.value)}
              />
            </Field>
            <Field label="Line of Business">
              <select
                className={inputCls} style={inputStyle}
                value={d.lob ?? ''} onChange={(e) => set('lob', e.target.value)}
              >
                <option value="">Select…</option>
                {LOB_OPTIONS.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </Field>
            <Field label="Effective Date">
              <input type="date" className={inputCls} style={inputStyle}
                value={d.effectiveDate ?? ''} onChange={(e) => set('effectiveDate', e.target.value)} />
            </Field>
            <Field label="Expiry Date">
              <input type="date" className={inputCls} style={inputStyle}
                value={d.expiryDate ?? ''} onChange={(e) => set('expiryDate', e.target.value)} />
            </Field>
          </div>

          {/* Tags */}
          <Field label="Tags">
            <div className="space-y-2">
              <div className="flex flex-wrap gap-1">
                {(d.tags ?? []).map((tag) => (
                  <span key={tag} className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-medium border"
                        style={{ background: 'var(--elevated)', border: '1px solid var(--border)', color: 'var(--text-2)' }}>
                    {tag}
                    <button onClick={() => removeTag(tag)} className="hover:text-red-400 transition-colors ml-0.5">
                      <X className="w-2.5 h-2.5" />
                    </button>
                  </span>
                ))}
              </div>
              <div className="flex gap-2">
                <input
                  className={`${inputCls} flex-1`} style={inputStyle}
                  placeholder="Add tag…"
                  value={newTag}
                  onChange={(e) => setNewTag(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTag() } }}
                />
                <button
                  onClick={addTag}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[10px] font-semibold text-white shrink-0"
                  style={{ background: '#6366f1' }}
                >
                  <Plus className="w-3 h-3" />
                </button>
              </div>
            </div>
          </Field>
        </motion.div>
      )}
    </div>
  )
}
