import { type LucideIcon, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Card } from '@/components/ui/Card'

interface MetricCardProps {
  label:      string
  value:      string | number
  delta?:     string
  trend?:     'up' | 'down' | 'neutral'
  icon:       LucideIcon
  iconColor:  string
  iconBg:     string
  className?: string
  loading?:   boolean
}

export function MetricCard({ label, value, delta, trend = 'neutral', icon: Icon, iconColor, iconBg, className, loading }: MetricCardProps) {
  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus
  const trendColor = trend === 'up' ? 'text-emerald-400' : trend === 'down' ? 'text-red-400' : 'text-[var(--text-3)]'

  return (
    <Card className={cn('p-5', className)}>
      <div className="flex items-center justify-between mb-3">
        <div className={cn('w-9 h-9 rounded-lg flex items-center justify-center', iconBg)}>
          <Icon className={cn('w-4.5 h-4.5', iconColor)} />
        </div>
        {delta && (
          <div className={cn('flex items-center gap-1', trendColor)}>
            <TrendIcon className="w-3.5 h-3.5" />
            <span className="text-xs font-medium">{delta}</span>
          </div>
        )}
      </div>
      {loading ? (
        <div className="space-y-1.5">
          <div className="h-7 w-20 animate-pulse rounded bg-[var(--elevated)]" />
          <div className="h-3 w-28 animate-pulse rounded bg-[var(--elevated)]" />
        </div>
      ) : (
        <>
          <p className="text-2xl font-bold text-[var(--text-1)] tabular-nums">{value}</p>
          <p className="text-xs text-[var(--text-3)] mt-0.5">{label}</p>
        </>
      )}
    </Card>
  )
}