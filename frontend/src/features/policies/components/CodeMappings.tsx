import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, X, Search, Code2, Activity } from 'lucide-react'
import type { CPTCode, ICDCode, PolicyDocument } from '../hooks/usePolicyManager'

// ─── Code badge ───────────────────────────────────────────────────────────────

function CodeBadge({
  code, description, category, color, onRemove,
}: { code: string; description: string; category: string; color: string; onRemove: () => void }) {
  const [hovered, setHovered] = useState(false)
  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.85 }}
      className="relative group rounded-lg p-2.5 transition-all"
      style={{ background: `${color}0d`, border: `1px solid ${color}30` }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="flex items-start justify-between gap-1">
        <div>
          <span className="text-[10px] font-bold font-mono" style={{ color }}>{code}</span>
          <span className="ml-2 text-[8px] px-1 py-0.5 rounded" style={{ background: `${color}15`, color }}>
            {category}
          </span>
        </div>
        <AnimatePresence>
          {hovered && (
            <motion.button
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              onClick={onRemove}
              className="w-4 h-4 rounded-full flex items-center justify-center shrink-0 hover:bg-red-500/20 transition-colors"
            >
              <X className="w-2.5 h-2.5 text-red-400" />
            </motion.button>
          )}
        </AnimatePresence>
      </div>
      <p className="text-[9px] text-[var(--text-3)] mt-1 leading-snug line-clamp-2">{description}</p>
    </motion.div>
  )
}

// ─── Code picker ──────────────────────────────────────────────────────────────

interface CodePickerProps<T extends CPTCode | ICDCode> {
  pool:     T[]
  active:   T[]
  color:    string
  onAdd:    (code: T) => void
  label:    string
}

function CodePicker<T extends CPTCode | ICDCode>({ pool, active, color, onAdd, label }: CodePickerProps<T>) {
  const [search, setSearch] = useState('')
  const [open, setOpen]     = useState(false)

  const activeCodes = new Set(active.map((c) => c.code))
  const filtered = pool.filter((c) =>
    !activeCodes.has(c.code) &&
    (c.code.toLowerCase().includes(search.toLowerCase()) || c.description.toLowerCase().includes(search.toLowerCase())),
  )

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10px] font-semibold text-white transition-colors"
        style={{ background: color }}
      >
        <Plus className="w-3 h-3" />
        Add {label}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.97 }}
            className="absolute top-full mt-1 left-0 z-20 rounded-xl shadow-xl w-80 overflow-hidden"
            style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
          >
            <div className="p-2 border-b border-[var(--border)]">
              <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
                <Search className="w-3 h-3 text-[var(--text-4)]" />
                <input
                  autoFocus
                  className="flex-1 bg-transparent text-xs text-[var(--text-1)] placeholder:text-[var(--text-4)] outline-none"
                  placeholder={`Search ${label} codes…`}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
            </div>
            <div className="max-h-56 overflow-y-auto">
              {filtered.length === 0 && (
                <div className="p-4 text-center text-[10px] text-[var(--text-4)]">No codes match</div>
              )}
              {filtered.map((code) => (
                <button
                  key={code.code}
                  onClick={() => { onAdd(code); setOpen(false); setSearch('') }}
                  className="w-full flex items-start gap-2 px-3 py-2 text-left hover:bg-[var(--surface)] transition-colors"
                >
                  <span className="text-[10px] font-bold font-mono shrink-0 mt-0.5" style={{ color }}>{code.code}</span>
                  <div className="min-w-0">
                    <p className="text-[9px] text-[var(--text-2)] leading-snug line-clamp-2">{code.description}</p>
                    <p className="text-[8px] text-[var(--text-4)] mt-0.5">{code.category}</p>
                  </div>
                </button>
              ))}
            </div>
            <div className="px-3 py-2 border-t border-[var(--border)]">
              <button onClick={() => setOpen(false)} className="text-[9px] text-[var(--text-4)] hover:text-[var(--text-2)]">Close</button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ─── Category grouping ────────────────────────────────────────────────────────

function groupByCategory<T extends CPTCode | ICDCode>(codes: T[]): Record<string, T[]> {
  return codes.reduce((acc, c) => {
    ;(acc[c.category] ??= []).push(c)
    return acc
  }, {} as Record<string, T[]>)
}

// ─── Main component ───────────────────────────────────────────────────────────

interface CodeMappingsProps {
  policy:      PolicyDocument
  cptPool:     CPTCode[]
  icdPool:     ICDCode[]
  onAddCPT:    (code: CPTCode) => void
  onRemoveCPT: (code: string) => void
  onAddICD:    (code: ICDCode) => void
  onRemoveICD: (code: string) => void
}

export function CodeMappings({ policy, cptPool, icdPool, onAddCPT, onRemoveCPT, onAddICD, onRemoveICD }: CodeMappingsProps) {
  const [activeSection, setActiveSection] = useState<'cpt' | 'icd'>('cpt')

  const cptGroups = groupByCategory(policy.cptCodes)
  const icdGroups = groupByCategory(policy.icdCodes)

  return (
    <div className="p-4 space-y-4">
      {/* Section toggle */}
      <div className="flex items-center gap-2 p-1 rounded-xl" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
        {([
          { id: 'cpt', label: 'CPT Codes', icon: Code2, color: '#6366f1', count: policy.cptCodes.length },
          { id: 'icd', label: 'ICD-10 Codes', icon: Activity, color: '#0ea5e9', count: policy.icdCodes.length },
        ] as const).map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveSection(tab.id)}
            className="flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-[10px] font-semibold transition-all"
            style={{
              background: activeSection === tab.id ? 'var(--elevated)' : 'transparent',
              color:      activeSection === tab.id ? tab.color : 'var(--text-4)',
              border:     `1px solid ${activeSection === tab.id ? tab.color + '40' : 'transparent'}`,
            }}
          >
            <tab.icon className="w-3.5 h-3.5" />
            {tab.label}
            <span
              className="px-1.5 py-0.5 rounded-full text-[8px] font-bold"
              style={{
                background: activeSection === tab.id ? `${tab.color}20` : 'var(--surface)',
                color:      activeSection === tab.id ? tab.color : 'var(--text-4)',
              }}
            >
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {activeSection === 'cpt' && (
          <motion.div
            key="cpt"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 8 }}
            className="space-y-3"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[10px] font-bold text-[var(--text-2)]">Procedure Codes (CPT)</p>
                <p className="text-[9px] text-[var(--text-4)]">Procedures covered or excluded by this policy</p>
              </div>
              <CodePicker
                pool={cptPool}
                active={policy.cptCodes}
                color="#6366f1"
                onAdd={onAddCPT}
                label="CPT"
              />
            </div>
            {Object.entries(cptGroups).map(([cat, codes]) => (
              <div key={cat}>
                <p className="text-[8px] font-bold uppercase tracking-widest text-[var(--text-4)] mb-2 pl-1">{cat}</p>
                <div className="grid grid-cols-1 gap-2">
                  <AnimatePresence>
                    {codes.map((code) => (
                      <CodeBadge
                        key={code.code}
                        code={code.code}
                        description={code.description}
                        category={code.category}
                        color="#6366f1"
                        onRemove={() => onRemoveCPT(code.code)}
                      />
                    ))}
                  </AnimatePresence>
                </div>
              </div>
            ))}
            {policy.cptCodes.length === 0 && (
              <div className="py-8 text-center">
                <Code2 className="w-6 h-6 text-[var(--text-4)] mx-auto mb-2" />
                <p className="text-[10px] text-[var(--text-4)]">No CPT codes mapped. Click "Add CPT" to begin.</p>
              </div>
            )}
          </motion.div>
        )}

        {activeSection === 'icd' && (
          <motion.div
            key="icd"
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            className="space-y-3"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[10px] font-bold text-[var(--text-2)]">Diagnosis Codes (ICD-10)</p>
                <p className="text-[9px] text-[var(--text-4)]">Qualifying diagnoses covered by this policy</p>
              </div>
              <CodePicker
                pool={icdPool}
                active={policy.icdCodes}
                color="#0ea5e9"
                onAdd={onAddICD}
                label="ICD-10"
              />
            </div>
            {Object.entries(icdGroups).map(([cat, codes]) => (
              <div key={cat}>
                <p className="text-[8px] font-bold uppercase tracking-widest text-[var(--text-4)] mb-2 pl-1">{cat}</p>
                <div className="grid grid-cols-1 gap-2">
                  <AnimatePresence>
                    {codes.map((code) => (
                      <CodeBadge
                        key={code.code}
                        code={code.code}
                        description={code.description}
                        category={code.category}
                        color="#0ea5e9"
                        onRemove={() => onRemoveICD(code.code)}
                      />
                    ))}
                  </AnimatePresence>
                </div>
              </div>
            ))}
            {policy.icdCodes.length === 0 && (
              <div className="py-8 text-center">
                <Activity className="w-6 h-6 text-[var(--text-4)] mx-auto mb-2" />
                <p className="text-[10px] text-[var(--text-4)]">No ICD-10 codes mapped. Click "Add ICD-10" to begin.</p>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
