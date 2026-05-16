import { useHealthCheck } from '../hooks/useHealthCheck'
import { Activity, CheckCircle2, AlertTriangle, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

const STATUS_CFG = {
  healthy:  { icon: CheckCircle2,  color: 'text-emerald-400', label: 'All systems operational' },
  degraded: { icon: AlertTriangle, color: 'text-amber-400',   label: 'Partial degradation' },
  down:     { icon: XCircle,       color: 'text-red-400',     label: 'System outage' },
}

interface SystemStatusProps { compact?: boolean }

export function SystemStatus({ compact }: SystemStatusProps) {
  const { data, isLoading } = useHealthCheck()

  if (isLoading || !data) {
    return (
      <div className="flex items-center gap-2">
        <Activity className="w-3.5 h-3.5 text-[var(--text-3)] animate-pulse" />
        {!compact && <span className="text-xs text-[var(--text-3)]">Checking status…</span>}
      </div>
    )
  }

  const cfg = STATUS_CFG[data.status]
  const Icon = cfg.icon

  return (
    <div className="flex items-center gap-2">
      <Icon className={cn('w-3.5 h-3.5', cfg.color)} />
      {!compact && <span className={cn('text-xs font-medium', cfg.color)}>{cfg.label}</span>}
    </div>
  )
}