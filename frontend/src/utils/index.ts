// ─── Formatters ───────────────────────────────────────────────────────────────

export { cn, formatDate, formatDateTime, formatRelative, formatConfidence, formatFileSize, getConfidenceLevel, truncate, capitalize, slugToLabel } from '@/lib/utils'

// ─── Validators ───────────────────────────────────────────────────────────────

export function isValidNpi(npi: string): boolean {
  return /^\d{10}$/.test(npi)
}

export function isValidIcd10(code: string): boolean {
  return /^[A-Z]\d{2}(\.\d{1,4})?$/.test(code)
}

export function isValidCpt(code: string): boolean {
  return /^\d{5}$/.test(code)
}

// ─── Transforms ───────────────────────────────────────────────────────────────

export function pick<T extends object, K extends keyof T>(obj: T, keys: K[]): Pick<T, K> {
  return keys.reduce((acc, k) => { acc[k] = obj[k]; return acc }, {} as Pick<T, K>)
}

export function omit<T extends object, K extends keyof T>(obj: T, keys: K[]): Omit<T, K> {
  const result = { ...obj }
  keys.forEach((k) => delete result[k])
  return result as Omit<T, K>
}

export function groupBy<T>(arr: T[], key: (item: T) => string): Record<string, T[]> {
  return arr.reduce((acc, item) => {
    const k = key(item)
    if (!acc[k]) acc[k] = []
    acc[k].push(item)
    return acc
  }, {} as Record<string, T[]>)
}

// ─── Permissions ─────────────────────────────────────────────────────────────

export { hasPermission, hasAnyPermission, hasAllPermissions } from '@/constants/roles.constants'

// ─── Misc ─────────────────────────────────────────────────────────────────────

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function assertNever(x: never): never {
  throw new Error(`Unhandled case: ${JSON.stringify(x)}`)
}