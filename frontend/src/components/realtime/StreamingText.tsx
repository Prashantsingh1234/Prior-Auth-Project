import { useEffect, useRef } from 'react'
import { motion } from 'framer-motion'

// ─── Streaming text with cursor ───────────────────────────────────────────────

interface StreamingTextProps {
  text:         string
  className?:   string
  cursorColor?: string
  showCursor?:  boolean
  autoScroll?:  boolean
}

export function StreamingText({
  text,
  className    = 'text-[11px] leading-relaxed font-mono text-[var(--text-2)]',
  cursorColor  = '#8b5cf6',
  showCursor   = true,
  autoScroll   = true,
}: StreamingTextProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [text, autoScroll])

  return (
    <div ref={containerRef} className={className} style={{ wordBreak: 'break-word' }}>
      {text}
      {showCursor && (
        <motion.span
          className="inline-block w-0.5 h-[1.1em] ml-0.5 align-text-bottom"
          style={{ background: cursorColor }}
          animate={{ opacity: [1, 0, 1] }}
          transition={{ duration: 0.7, repeat: Infinity }}
        />
      )}
    </div>
  )
}

// ─── Word-by-word reveal ──────────────────────────────────────────────────────

interface WordRevealProps {
  words:      string[]
  className?: string
}

export function WordReveal({ words, className = 'text-sm text-[var(--text-1)]' }: WordRevealProps) {
  return (
    <span className={className}>
      {words.map((word, i) => (
        <motion.span
          key={i}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.05, duration: 0.2 }}
        >
          {word}{' '}
        </motion.span>
      ))}
    </span>
  )
}
