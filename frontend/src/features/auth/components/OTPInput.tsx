import { useRef, useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'

interface OTPInputProps {
  length?: number
  value?: string
  onChange?: (value: string) => void
  onComplete?: (value: string) => void
  disabled?: boolean
  error?: boolean
  autoFocus?: boolean
  className?: string
}

export function OTPInput({
  length = 6,
  value = '',
  onChange,
  onComplete,
  disabled = false,
  error = false,
  autoFocus = true,
  className,
}: OTPInputProps) {
  const [digits, setDigits] = useState<string[]>(() =>
    Array.from({ length }, (_, i) => value[i] ?? '')
  )
  const inputs = useRef<(HTMLInputElement | null)[]>([])

  // Sync external value
  useEffect(() => {
    setDigits(Array.from({ length }, (_, i) => value[i] ?? ''))
  }, [value, length])

  function focus(i: number) {
    inputs.current[i]?.focus()
  }

  function update(next: string[]) {
    setDigits(next)
    const joined = next.join('')
    onChange?.(joined)
    if (joined.length === length && next.every(Boolean)) {
      onComplete?.(joined)
    }
  }

  function handleChange(i: number, e: React.ChangeEvent<HTMLInputElement>) {
    const raw = e.target.value.replace(/\D/g, '')
    if (!raw) return

    if (raw.length > 1) {
      // Handle paste via input event (fallback)
      const pasted = raw.slice(0, length - i)
      const next = [...digits]
      pasted.split('').forEach((ch, j) => {
        if (i + j < length) next[i + j] = ch
      })
      update(next)
      focus(Math.min(i + pasted.length, length - 1))
      return
    }

    const next = [...digits]
    next[i] = raw
    update(next)
    if (i < length - 1) focus(i + 1)
  }

  function handleKeyDown(i: number, e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Backspace') {
      if (digits[i]) {
        const next = [...digits]
        next[i] = ''
        update(next)
      } else if (i > 0) {
        const next = [...digits]
        next[i - 1] = ''
        update(next)
        focus(i - 1)
      }
      e.preventDefault()
    } else if (e.key === 'ArrowLeft' && i > 0) {
      focus(i - 1)
      e.preventDefault()
    } else if (e.key === 'ArrowRight' && i < length - 1) {
      focus(i + 1)
      e.preventDefault()
    } else if (e.key === 'Delete') {
      const next = [...digits]
      next[i] = ''
      update(next)
    }
  }

  function handlePaste(e: React.ClipboardEvent) {
    e.preventDefault()
    const text = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, length)
    const next = Array.from({ length }, (_, i) => text[i] ?? '')
    update(next)
    focus(Math.min(text.length, length - 1))
  }

  function handleFocus(i: number) {
    inputs.current[i]?.select()
  }

  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      {Array.from({ length }, (_, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: i * 0.05, duration: 0.2 }}
          className="flex-1"
        >
          <input
            ref={(el) => { inputs.current[i] = el }}
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={1}
            value={digits[i]}
            disabled={disabled}
            autoFocus={autoFocus && i === 0}
            onChange={(e) => handleChange(i, e)}
            onKeyDown={(e) => handleKeyDown(i, e)}
            onPaste={handlePaste}
            onFocus={() => handleFocus(i)}
            className={cn(
              'w-full h-14 text-center text-xl font-bold rounded-xl border-2 outline-none transition-all',
              'bg-[var(--elevated)] text-[var(--text-1)]',
              'focus:border-cyan-500 focus:shadow-[0_0_0_3px_rgba(14,165,233,0.15)]',
              digits[i] && !error && 'border-cyan-500/50 bg-cyan-500/5',
              error
                ? 'border-red-500/50 bg-red-500/5 focus:border-red-500 focus:shadow-[0_0_0_3px_rgba(239,68,68,0.1)]'
                : 'border-[var(--border)] hover:border-[var(--border-strong)]',
              disabled && 'opacity-50 cursor-not-allowed',
            )}
            aria-label={`Digit ${i + 1} of ${length}`}
          />
        </motion.div>
      ))}
    </div>
  )
}
