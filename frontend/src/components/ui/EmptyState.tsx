import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'

interface EmptyStateProps {
  icon:        React.ElementType
  title:       string
  description?: string
  action?:     React.ReactNode
  className?:  string
  iconColor?:  string
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
  iconColor = '#64748b',
}: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
      className={cn('flex flex-col items-center justify-center text-center py-16 px-6', className)}
    >
      <motion.div
        initial={{ scale: 0.7, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.4, delay: 0.05, type: 'spring', stiffness: 200, damping: 18 }}
        className="mb-5 w-16 h-16 rounded-2xl flex items-center justify-center"
        style={{ background: `${iconColor}15` }}
      >
        <Icon style={{ color: iconColor, width: 28, height: 28 }} />
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.28, delay: 0.12, ease: 'easeOut' }}
      >
        <p className="text-sm font-semibold text-[var(--text-1)]">{title}</p>
        {description && (
          <p className="text-xs text-[var(--text-3)] mt-1.5 max-w-xs leading-relaxed">{description}</p>
        )}
      </motion.div>

      {action && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28, delay: 0.2, ease: 'easeOut' }}
          className="mt-5"
        >
          {action}
        </motion.div>
      )}
    </motion.div>
  )
}
