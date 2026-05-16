import { useCallback, useState } from 'react'
import { Upload, FileText, X, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react'
import { cn, formatFileSize } from '@/lib/utils'
import type { UploadFile } from '../types'
import { APP_CONFIG } from '@/config/app.config'

interface UploadZoneProps {
  files:          UploadFile[]
  onFilesAdded:   (files: File[], documentType: string) => void
  onRemove:       (id: string) => void
  onUploadAll:    () => void
  documentType:   string
  disabled?:      boolean
}

export function UploadZone({ files, onFilesAdded, onRemove, onUploadAll, documentType, disabled }: UploadZoneProps) {
  const [dragging, setDragging] = useState(false)

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const dropped = Array.from(e.dataTransfer.files).filter((f) =>
      APP_CONFIG.upload.acceptedMimeTypes.includes(f.type as any)
    )
    if (dropped.length) onFilesAdded(dropped, documentType)
  }, [documentType, onFilesAdded])

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files ?? [])
    if (selected.length) onFilesAdded(selected, documentType)
    e.target.value = ''
  }, [documentType, onFilesAdded])

  const pendingCount = files.filter((f) => f.status === 'idle').length

  return (
    <div className="space-y-3">
      <label
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={cn(
          'flex flex-col items-center justify-center gap-3 p-8 rounded-xl border-2 border-dashed cursor-pointer transition-colors',
          dragging
            ? 'border-brand-400 bg-brand-500/10'
            : 'border-[var(--border)] hover:border-brand-500/50 hover:bg-brand-500/5',
          disabled && 'pointer-events-none opacity-50'
        )}
      >
        <Upload className="w-8 h-8 text-[var(--text-3)]" />
        <div className="text-center">
          <p className="text-sm font-medium text-[var(--text-1)]">Drop files here or click to browse</p>
          <p className="text-xs text-[var(--text-3)] mt-1">
            PDF, JPEG, PNG, TIFF — max {APP_CONFIG.upload.maxFileSizeMb}MB each
          </p>
        </div>
        <input type="file" className="hidden" multiple accept=".pdf,.jpg,.jpeg,.png,.tiff" onChange={handleChange} />
      </label>

      {files.length > 0 && (
        <div className="space-y-2">
          {files.map((f) => (
            <div key={f.id} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-[var(--elevated)] border border-[var(--border)]">
              <FileText className="w-4 h-4 text-brand-400 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-[var(--text-1)] truncate">{f.file.name}</p>
                {f.status === 'uploading' && (
                  <div className="mt-1 h-1 rounded-full bg-[var(--border)]">
                    <div className="h-full rounded-full bg-brand-500 transition-all" style={{ width: `${f.progress}%` }} />
                  </div>
                )}
                {f.status === 'error' && (
                  <p className="text-xs text-red-400 mt-0.5">{f.error}</p>
                )}
                {f.status === 'idle' && (
                  <p className="text-xs text-[var(--text-3)]">{formatFileSize(f.file.size)}</p>
                )}
              </div>
              {f.status === 'uploading' && <Loader2 className="w-4 h-4 animate-spin text-brand-400 flex-shrink-0" />}
              {f.status === 'success'   && <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />}
              {f.status === 'error'     && <AlertCircle  className="w-4 h-4 text-red-400 flex-shrink-0" />}
              {(f.status === 'idle' || f.status === 'error') && (
                <button onClick={() => onRemove(f.id)} className="text-[var(--text-3)] hover:text-red-400 flex-shrink-0">
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))}

          {pendingCount > 0 && (
            <button onClick={onUploadAll} className="btn btn-primary w-full text-sm" disabled={disabled}>
              Upload {pendingCount} file{pendingCount !== 1 ? 's' : ''}
            </button>
          )}
        </div>
      )}
    </div>
  )
}