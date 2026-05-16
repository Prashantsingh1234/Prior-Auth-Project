import { CheckCircle2, AlertTriangle, Info, XCircle, X } from 'lucide-react'
import { cn } from '@/lib/utils'

type AlertVariant = 'info' | 'success' | 'warning' | 'error'

const CFG: Record<AlertVariant, { icon: React.ElementType; className: string }> = {
  info:    { icon: Info,          className: 'bg-brand-500/10   border-brand-500/20   text-brand-400' },
  success: { icon: CheckCircle2,  className: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' },
  warning: { icon: AlertTriangle, className: 'bg-amber-500/10   border-amber-500/20   text-amber-400' },
  error:   { icon: XCircle,       className: 'bg-red-500/10     border-red-500/20     text-red-400' },
}

interface AlertProps {
  variant:   AlertVariant
  title?:    string
  message:   string
  onDismiss?: () => void
  className?: string
}

export function Alert({ variant, title, message, onDismiss, className }: AlertProps) {
  const { icon: Icon, className: variantClass } = CFG[variant]
  return (
    <div className={cn('flex items-start gap-3 p-3 rounded-lg border', variantClass, className)}>
      <Icon className="w-4 h-4 flex-shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        {title && <p className="text-xs font-semibold">{title}</p>}
        <p className="text-xs mt-0.5">{message}</p>
      </div>
      {onDismiss && (
        <button onClick={onDismiss} className="flex-shrink-0 opacity-60 hover:opacity-100">
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  )
}