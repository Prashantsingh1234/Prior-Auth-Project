import { cn } from '@/lib/utils'
import type { LucideIcon } from 'lucide-react'

interface Props {
  label: string
  value: string | number
  icon?: LucideIcon
  iconColor?: string
  className?: string
  sub?: string
}

export function StatCard({ label, value, icon: Icon, iconColor = 'text-blue-600', className, sub }: Props) {
  return (
    <div className={cn('card p-5', className)}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className="mt-1 text-2xl font-semibold text-gray-900">{value}</p>
          {sub && <p className="mt-0.5 text-xs text-gray-400">{sub}</p>}
        </div>
        {Icon && (
          <div className="p-2 bg-gray-50 rounded-lg">
            <Icon className={cn('w-5 h-5', iconColor)} />
          </div>
        )}
      </div>
    </div>
  )
}
