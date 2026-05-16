import { useState, useCallback } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { casesService } from '@/services'
import type { UploadFile, UploadStatus } from '../types'

export function useDocumentUpload(caseId: string) {
  const [files, setFiles] = useState<UploadFile[]>([])
  const qc = useQueryClient()

  const updateFile = useCallback((id: string, patch: Partial<UploadFile>) => {
    setFiles((prev) => prev.map((f) => f.id === id ? { ...f, ...patch } : f))
  }, [])

  const addFiles = useCallback((newFiles: File[], documentType: string) => {
    const items: UploadFile[] = newFiles.map((file) => ({
      id:           crypto.randomUUID(),
      file,
      documentType,
      status:       'idle' as UploadStatus,
      progress:     0,
    }))
    setFiles((prev) => [...prev, ...items])
    return items
  }, [])

  const uploadFile = useCallback(async (uploadFile: UploadFile) => {
    updateFile(uploadFile.id, { status: 'uploading' })
    try {
      const result = await casesService.uploadDocument(
        caseId,
        uploadFile.file,
        uploadFile.documentType,
        (progress) => updateFile(uploadFile.id, { progress }),
      )
      updateFile(uploadFile.id, { status: 'success', resultId: result.id })
      qc.invalidateQueries({ queryKey: ['cases', 'detail', caseId] })
    } catch (error: any) {
      updateFile(uploadFile.id, { status: 'error', error: error?.message ?? 'Upload failed' })
    }
  }, [caseId, updateFile, qc])

  const removeFile = useCallback((id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id))
  }, [])

  const uploadAll = useCallback(async () => {
    const pending = files.filter((f) => f.status === 'idle')
    await Promise.allSettled(pending.map(uploadFile))
  }, [files, uploadFile])

  return { files, addFiles, uploadFile, removeFile, uploadAll }
}