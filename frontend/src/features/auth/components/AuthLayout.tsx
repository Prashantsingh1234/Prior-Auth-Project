import { motion } from 'framer-motion'
import { AnimatedLeftPanel } from './AnimatedLeftPanel'

interface AuthLayoutProps {
  children: React.ReactNode
  /** Optional back link for sub-pages (forgot password, OTP, etc.) */
  backHref?: string
  backLabel?: string
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="min-h-screen flex bg-[var(--bg)]">
      {/* Left panel — animated healthcare AI visuals */}
      <AnimatedLeftPanel />

      {/* Right panel — auth form */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4 }}
        className="flex-1 flex items-center justify-center p-8 lg:p-12 relative overflow-hidden"
      >
        {/* Subtle background mesh */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              'radial-gradient(ellipse at 80% 20%, rgba(14,165,233,0.04) 0%, transparent 50%), radial-gradient(ellipse at 20% 80%, rgba(139,92,246,0.04) 0%, transparent 50%)',
          }}
        />

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          className="relative w-full max-w-[400px]"
        >
          {children}
        </motion.div>
      </motion.div>
    </div>
  )
}
