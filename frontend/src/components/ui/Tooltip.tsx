import { useState, useRef, useCallback } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { cn } from '@/lib/utils'

type Side = 'top' | 'bottom' | 'left' | 'right'

interface TooltipProps {
  content:    React.ReactNode
  children:   React.ReactElement
  side?:      Side
  delay?:     number
  className?: string
}

const OFFSET = 8

function sideVariants(side: Side) {
  const hidden =
    side === 'top'    ? { opacity: 0, y: 4 } :
    side === 'bottom' ? { opacity: 0, y: -4 } :
    side === 'left'   ? { opacity: 0, x: 4 } :
                        { opacity: 0, x: -4 }
  const show =
    side === 'top' || side === 'bottom'
      ? { opacity: 1, y: 0 }
      : { opacity: 1, x: 0 }
  return { hidden, show } as const
}

const POSITION: Record<Side, React.CSSProperties> = {
  top:    { bottom: '100%', left: '50%', transform: 'translateX(-50%)', marginBottom: OFFSET },
  bottom: { top:    '100%', left: '50%', transform: 'translateX(-50%)', marginTop:    OFFSET },
  left:   { right:  '100%', top:  '50%', transform: 'translateY(-50%)', marginRight:  OFFSET },
  right:  { left:   '100%', top:  '50%', transform: 'translateY(-50%)', marginLeft:   OFFSET },
}

export function Tooltip({ content, children, side = 'top', delay = 600, className }: TooltipProps) {
  const [visible, setVisible] = useState(false)
  const timerRef              = useRef<ReturnType<typeof setTimeout> | null>(null)
  const variants              = sideVariants(side)

  const show = useCallback(() => {
    timerRef.current = setTimeout(() => setVisible(true), delay)
  }, [delay])

  const hide = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    setVisible(false)
  }, [])

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      <AnimatePresence>
        {visible && (
          <motion.span
            role="tooltip"
            variants={variants}
            initial="hidden"
            animate="show"
            exit="hidden"
            transition={{ duration: 0.14, ease: 'easeOut' }}
            style={{ ...POSITION[side], zIndex: 50 }}
            className={cn(
              'pointer-events-none absolute whitespace-nowrap rounded-lg px-2.5 py-1.5',
              'bg-[var(--surface-inv,#0f172a)] text-[var(--text-inv,#f1f5f9)]',
              'text-[11px] font-medium shadow-lg border border-white/10',
              className,
            )}
          >
            {content}
          </motion.span>
        )}
      </AnimatePresence>
    </span>
  )
}
