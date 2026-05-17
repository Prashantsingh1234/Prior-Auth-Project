/**
 * Client-side upload security:
 * - Magic-byte verification: reads the first 8 bytes of the file to confirm the
 *   actual format, regardless of what the browser infers from the extension.
 * - Size enforcement before upload begins.
 *
 * A renamed .exe won't pass the PDF/JPEG/PNG/TIFF signature check.
 */

import { APP_CONFIG } from '@/config/app.config'

interface Signature {
  bytes:   number[]
  offset?: number
}

const SIGNATURES: Record<string, Signature[]> = {
  'application/pdf': [{ bytes: [0x25, 0x50, 0x44, 0x46] }],              // %PDF
  'image/jpeg':      [{ bytes: [0xFF, 0xD8, 0xFF] }],                    // SOI marker
  'image/png':       [{ bytes: [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A] }], // ‰PNG
  'image/tiff':      [
    { bytes: [0x49, 0x49, 0x2A, 0x00] },  // TIFF LE  (II*)
    { bytes: [0x4D, 0x4D, 0x00, 0x2A] },  // TIFF BE  (MM*)
  ],
}

async function readHeader(file: File, n = 8): Promise<Uint8Array> {
  return new Uint8Array(await file.slice(0, n).arrayBuffer())
}

/** Returns the actual MIME type detected from file bytes, or null if unrecognised. */
export async function detectMimeFromBytes(file: File): Promise<string | null> {
  const header = await readHeader(file, 8)
  for (const [mime, sigs] of Object.entries(SIGNATURES)) {
    const match = sigs.some((sig) =>
      sig.bytes.every((b, i) => header[(sig.offset ?? 0) + i] === b),
    )
    if (match) return mime
  }
  return null
}

const MAX_BYTES = APP_CONFIG.upload.maxFileSizeMb * 1024 * 1024

export interface ValidationResult {
  valid:  boolean
  error?: string
  mime?:  string
}

/**
 * Full validation: size check + magic-byte MIME detection.
 * Call this before adding a file to the upload queue.
 */
export async function validateUploadFile(file: File): Promise<ValidationResult> {
  if (file.size === 0) {
    return { valid: false, error: 'File is empty' }
  }
  if (file.size > MAX_BYTES) {
    return { valid: false, error: `Exceeds ${APP_CONFIG.upload.maxFileSizeMb} MB limit` }
  }

  const mime = await detectMimeFromBytes(file)
  if (!mime) {
    return { valid: false, error: 'Unrecognised file format — only PDF, JPEG, PNG, or TIFF allowed' }
  }
  if (!(APP_CONFIG.upload.acceptedMimeTypes as readonly string[]).includes(mime)) {
    return { valid: false, error: `File type not permitted` }
  }

  return { valid: true, mime }
}
