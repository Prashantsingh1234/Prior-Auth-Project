export type UploadStatus = 'idle' | 'uploading' | 'success' | 'error'

export interface UploadFile {
  id:           string
  file:         File
  documentType: string
  status:       UploadStatus
  progress:     number
  error?:       string
  resultId?:    string
}