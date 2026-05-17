import { motion } from 'framer-motion'
import { AlertTriangle, RefreshCw, WifiOff } from 'lucide-react'
import { cn } from '@/lib/utils'

interface APIErrorFallbackProps {
  error?:    Error | { statusCode?: number; message?: string } | null
  reset?:    () => void
  title?:    string
  compact?:  boolean
  className?: string
}

function getIcon(error: APIErrorFallbackProps['error']) {
  const code = (error as any)?.statusCode
  if (code === 0 || (error as any)?.code === 'NETWORK_ERROR') return WifiOff
  return AlertTriangle
}

function getTitle(error: APIErrorFallbackProps['error'], fallback?: string) {
  if (fallback) return fallback
  const code = (error as any)?.statusCode
  if (!code || code === 0) return 'Connection lost'
  if (code >= 500)         return 'Server error'
  if (code === 403)        return 'Access denied'
  if (code === 404)        return 'Not found'
  return 'Something went wrong'
}

function getMessage(error: APIErrorFallbackProps['error']): string {
  if (!error) return 'An unexpected error occurred.'
  const msg = (error as any).message
  if (typeof msg === 'string' && msg.length > 0) return msg
  const code = (error as any)?.statusCode
  if (!code || code === 0) return 'Unable to reach the server. Check your connection.'
  if (code >= 500)         return 'The server encountered an error. Try again in a moment.'
  return 'An unexpected error occurred.'
}

export function APIErrorFallback({ error, reset, title, compact, className }: APIErrorFallbackProps) {
  const Icon = getIcon(error)

  if (compact) {
    return (
      <div className={cn('flex items-center gap-2 px-3 py-2.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm', className)}>
        <Icon className="w-4 h-4 flex-shrink-0" />
        <span className="flex-1 text-xs">{getMessage(error)}</span>
        {reset && (
          <button onClick={reset} className="ml-auto flex-shrink-0 hover:text-red-300 transition-colors" aria-label="Retry">
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.25 }}
      className={cn('flex flex-col items-center justify-center text-center py-16 px-6', className)}
    >
      <div className="mb-4 w-14 h-14 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
        <Icon className="w-6 h-6 text-red-400" />
      </div>

      <p className="text-sm font-semibold text-[var(--text-1)] mb-1">
        {getTitle(error, title)}
      </p>
      <p className="text-xs text-[var(--text-3)] max-w-xs leading-relaxed mb-5">
        {getMessage(error)}
      </p>

      {reset && (
        <motion.button
          onClick={reset}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.97 }}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[var(--elevated)] border border-[var(--border)] text-xs font-medium text-[var(--text-2)] hover:text-[var(--text-1)] transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Try again
        </motion.button>
      )}
    </motion.div>
  )
}
