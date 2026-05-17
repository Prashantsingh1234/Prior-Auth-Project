import { motion } from 'framer-motion'

interface AIPulseProps {
  size?:  number
  color?: string
  rings?: number
}

export function AIPulse({ size = 8, color = '#10b981', rings = 3 }: AIPulseProps) {
  return (
    <span className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      {Array.from({ length: rings }).map((_, i) => (
        <motion.span
          key={i}
          className="absolute inset-0 rounded-full"
          style={{ borderWidth: 1.5, borderStyle: 'solid', borderColor: color }}
          initial={{ opacity: 0.7, scale: 1 }}
          animate={{ opacity: 0, scale: 2.8 + i * 0.6 }}
          transition={{
            duration: 1.8,
            repeat: Infinity,
            delay: i * 0.5,
            ease: 'easeOut',
          }}
        />
      ))}
      <span
        className="relative rounded-full"
        style={{ width: size, height: size, background: color }}
      />
    </span>
  )
}
