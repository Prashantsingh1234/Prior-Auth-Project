import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Stethoscope, Shield, Brain, Activity, Heart, Lock } from 'lucide-react'

// ─── Neural network data ──────────────────────────────────────────────────────

const NODES = [
  { id: 0,  cx: 12,  cy: 18 },
  { id: 1,  cx: 38,  cy: 8  },
  { id: 2,  cx: 68,  cy: 12 },
  { id: 3,  cx: 88,  cy: 28 },
  { id: 4,  cx: 92,  cy: 52 },
  { id: 5,  cx: 78,  cy: 70 },
  { id: 6,  cx: 55,  cy: 78 },
  { id: 7,  cx: 30,  cy: 75 },
  { id: 8,  cx: 8,   cy: 58 },
  { id: 9,  cx: 5,   cy: 35 },
  { id: 10, cx: 45,  cy: 42 },
  { id: 11, cx: 68,  cy: 45 },
  { id: 12, cx: 25,  cy: 50 },
  { id: 13, cx: 55,  cy: 22 },
]

const EDGES = [
  [0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6], [6, 7], [7, 8], [8, 9], [9, 0],
  [1, 13], [13, 2], [13, 10], [10, 11], [11, 3], [11, 4], [10, 12], [12, 7], [12, 8],
  [10, 6], [0, 12], [2, 11], [5, 11],
]

// ─── Sub-components ───────────────────────────────────────────────────────────

function NeuralNetwork() {
  const [activeEdge, setActiveEdge] = useState(0)

  useEffect(() => {
    const t = setInterval(() => setActiveEdge((i) => (i + 1) % EDGES.length), 280)
    return () => clearInterval(t)
  }, [])

  return (
    <svg
      viewBox="0 0 100 90"
      className="absolute inset-0 w-full h-full pointer-events-none"
      style={{ opacity: 0.35 }}
    >
      {EDGES.map(([a, b], i) => {
        const na = NODES[a], nb = NODES[b]
        const isActive = activeEdge === i
        return (
          <motion.line
            key={i}
            x1={na.cx} y1={na.cy}
            x2={nb.cx} y2={nb.cy}
            stroke={isActive ? '#38bdf8' : '#1e3a6e'}
            strokeWidth={isActive ? 0.4 : 0.2}
            initial={false}
            animate={{ opacity: isActive ? [0.2, 1, 0.2] : 0.4 }}
            transition={{ duration: 0.56, ease: 'easeInOut' }}
          />
        )
      })}
      {NODES.map((n) => (
        <motion.circle
          key={n.id}
          cx={n.cx}
          cy={n.cy}
          r={1.2}
          fill="#38bdf8"
          animate={{ opacity: [0.4, 1, 0.4], r: [1.0, 1.5, 1.0] }}
          transition={{
            duration: 2 + (n.id % 3) * 0.7,
            repeat: Infinity,
            delay: (n.id * 0.23) % 2,
            ease: 'easeInOut',
          }}
        />
      ))}
    </svg>
  )
}

function BiometricScan() {
  return (
    <div className="relative flex items-center justify-center" style={{ width: 160, height: 160 }}>
      {/* Outer glow ring */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: 160, height: 160,
          background: 'radial-gradient(circle, rgba(14,165,233,0.06) 0%, transparent 70%)',
        }}
        animate={{ scale: [1, 1.1, 1], opacity: [0.5, 1, 0.5] }}
        transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Concentric pulse rings */}
      {[140, 112, 84, 56].map((size, i) => (
        <motion.div
          key={size}
          className="absolute rounded-full border"
          style={{
            width: size,
            height: size,
            borderColor: `rgba(14,165,233,${0.12 + i * 0.06})`,
          }}
          animate={{ scale: [1, 1.04, 1], opacity: [0.4, 0.9, 0.4] }}
          transition={{
            duration: 2.4,
            repeat: Infinity,
            delay: i * 0.4,
            ease: 'easeInOut',
          }}
        />
      ))}

      {/* Scan line */}
      <motion.div
        className="absolute w-full overflow-hidden rounded-full"
        style={{ height: 1, background: 'linear-gradient(90deg, transparent 0%, rgba(14,165,233,0.9) 50%, transparent 100%)' }}
        animate={{ y: [-70, 70] }}
        transition={{ duration: 2.2, repeat: Infinity, ease: 'linear', repeatType: 'reverse' }}
      />

      {/* Center icon */}
      <div className="relative z-10 flex flex-col items-center gap-1">
        <motion.div
          className="w-12 h-12 rounded-2xl flex items-center justify-center"
          style={{ background: 'rgba(14,165,233,0.15)', border: '1px solid rgba(14,165,233,0.3)' }}
          animate={{ boxShadow: ['0 0 0 0 rgba(14,165,233,0)', '0 0 24px 4px rgba(14,165,233,0.3)', '0 0 0 0 rgba(14,165,233,0)'] }}
          transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
        >
          <Lock className="w-6 h-6 text-cyan-400" />
        </motion.div>
        <motion.span
          className="text-[10px] font-medium tracking-widest uppercase"
          style={{ color: 'rgba(14,165,233,0.7)' }}
          animate={{ opacity: [0.5, 1, 0.5] }}
          transition={{ duration: 1.8, repeat: Infinity }}
        >
          Verified
        </motion.span>
      </div>
    </div>
  )
}

function AIPulseRings() {
  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
      {[280, 360, 440, 520].map((size, i) => (
        <motion.div
          key={size}
          className="absolute rounded-full"
          style={{
            width: size,
            height: size,
            border: `1px solid rgba(139,92,246,${0.04 - i * 0.008})`,
          }}
          animate={{ scale: [1, 1.02, 1], opacity: [0.3, 0.7, 0.3] }}
          transition={{ duration: 4 + i * 1.2, repeat: Infinity, delay: i * 0.8, ease: 'easeInOut' }}
        />
      ))}
    </div>
  )
}

function FloatingBlobs() {
  return (
    <>
      <motion.div
        className="absolute rounded-full pointer-events-none"
        style={{
          width: 400, height: 400,
          background: 'radial-gradient(circle, rgba(59,130,246,0.12) 0%, transparent 70%)',
          top: '-10%', left: '-15%',
          filter: 'blur(40px)',
        }}
        animate={{ x: [0, 30, 0], y: [0, 20, 0] }}
        transition={{ duration: 12, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        className="absolute rounded-full pointer-events-none"
        style={{
          width: 350, height: 350,
          background: 'radial-gradient(circle, rgba(139,92,246,0.1) 0%, transparent 70%)',
          bottom: '5%', right: '-10%',
          filter: 'blur(50px)',
        }}
        animate={{ x: [0, -25, 0], y: [0, -30, 0] }}
        transition={{ duration: 15, repeat: Infinity, ease: 'easeInOut', delay: 3 }}
      />
      <motion.div
        className="absolute rounded-full pointer-events-none"
        style={{
          width: 250, height: 250,
          background: 'radial-gradient(circle, rgba(14,165,233,0.08) 0%, transparent 70%)',
          top: '40%', right: '20%',
          filter: 'blur(35px)',
        }}
        animate={{ x: [0, 15, 0], y: [0, 25, 0] }}
        transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut', delay: 6 }}
      />
    </>
  )
}

const STATS = [
  { icon: Brain,    value: '94.2%', label: 'AI Accuracy',   delay: 0,   top: '18%', left: '5%'  },
  { icon: Activity, value: '3.5s',  label: 'Review Time',   delay: 0.4, top: '70%', right: '4%' },
  { icon: Heart,    value: '73%',   label: 'Time Saved',    delay: 0.8, bottom: '20%', left: '3%' },
  { icon: Shield,   value: 'SOC 2', label: 'Certified',     delay: 1.2, top: '12%', right: '6%' },
]

function FloatingStatCard({
  icon: Icon, value, label, delay, ...pos
}: (typeof STATS)[number]) {
  return (
    <motion.div
      className="absolute flex items-center gap-2 px-3 py-2 rounded-xl backdrop-blur-sm"
      style={{
        background: 'rgba(255,255,255,0.05)',
        border: '1px solid rgba(255,255,255,0.08)',
        ...pos as React.CSSProperties,
      }}
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{
        opacity: 1,
        scale: 1,
        y: [0, -6, 0],
      }}
      transition={{
        opacity: { duration: 0.4, delay: delay + 0.6 },
        scale:   { duration: 0.4, delay: delay + 0.6 },
        y:       { duration: 4 + delay, repeat: Infinity, ease: 'easeInOut', delay: delay + 1 },
      }}
    >
      <div className="w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0"
           style={{ background: 'rgba(14,165,233,0.2)' }}>
        <Icon className="w-3.5 h-3.5 text-cyan-400" />
      </div>
      <div>
        <p className="text-white text-xs font-bold leading-none">{value}</p>
        <p className="text-white/50 text-[10px] leading-none mt-0.5">{label}</p>
      </div>
    </motion.div>
  )
}

const TRUST_MARKS = ['HIPAA Compliant', 'SOC 2 Type II', 'HL7 FHIR', '256-bit AES']

// ─── Typing text effect ───────────────────────────────────────────────────────

const TAGLINES = [
  'AI-Powered Prior Authorization',
  'Evidence-Based Decision Support',
  'Intelligent Policy Matching',
  'Automated Clinical Review',
]

function TypingTagline() {
  const [idx, setIdx] = useState(0)
  const [displayed, setDisplayed] = useState('')
  const [phase, setPhase] = useState<'typing' | 'pausing' | 'erasing'>('typing')
  const target = TAGLINES[idx]

  useEffect(() => {
    let timeout: ReturnType<typeof setTimeout>
    if (phase === 'typing') {
      if (displayed.length < target.length) {
        timeout = setTimeout(() => setDisplayed(target.slice(0, displayed.length + 1)), 55)
      } else {
        timeout = setTimeout(() => setPhase('pausing'), 2000)
      }
    } else if (phase === 'pausing') {
      timeout = setTimeout(() => setPhase('erasing'), 400)
    } else {
      if (displayed.length > 0) {
        timeout = setTimeout(() => setDisplayed(displayed.slice(0, -1)), 30)
      } else {
        setIdx((i) => (i + 1) % TAGLINES.length)
        setPhase('typing')
      }
    }
    return () => clearTimeout(timeout)
  }, [displayed, phase, target])

  return (
    <span className="text-cyan-400">
      {displayed}
      <motion.span
        animate={{ opacity: [1, 0] }}
        transition={{ duration: 0.5, repeat: Infinity, repeatType: 'reverse' }}
        className="inline-block w-0.5 h-5 bg-cyan-400 ml-0.5 align-middle"
      />
    </span>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export function AnimatedLeftPanel() {
  return (
    <div
      className="relative hidden lg:flex flex-col w-[52%] overflow-hidden"
      style={{
        background: 'linear-gradient(145deg, #020817 0%, #0a0f1e 45%, #0d0a1e 100%)',
      }}
    >
      {/* Grid texture */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: 'linear-gradient(rgba(14,165,233,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(14,165,233,0.04) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />

      {/* Animated color blobs */}
      <FloatingBlobs />

      {/* AI pulse rings */}
      <AIPulseRings />

      {/* Neural network overlay */}
      <NeuralNetwork />

      {/* Floating stat cards */}
      {STATS.map((s) => (
        <FloatingStatCard key={s.label} {...s} />
      ))}

      {/* Main content */}
      <div className="relative z-10 flex flex-col h-full p-10">

        {/* Logo */}
        <motion.div
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="flex items-center gap-3"
        >
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center"
            style={{ background: 'rgba(14,165,233,0.2)', border: '1px solid rgba(14,165,233,0.3)' }}
          >
            <Stethoscope className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <p className="text-white font-bold text-base leading-none">PA Review Platform</p>
            <p className="text-white/40 text-xs mt-0.5">Healthcare AI — v2.4</p>
          </div>
        </motion.div>

        {/* Hero copy */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.15 }}
          className="mt-12"
        >
          <h1 className="text-4xl font-bold text-white leading-tight">
            <TypingTagline />
          </h1>
          <p className="text-white/50 mt-4 text-sm leading-relaxed max-w-xs">
            Reduce authorization turnaround from days to seconds. Evidence-based AI recommendations
            grounded in your payer policies and clinical guidelines.
          </p>
        </motion.div>

        {/* Biometric scan */}
        <motion.div
          initial={{ opacity: 0, scale: 0.85 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6, delay: 0.35 }}
          className="flex-1 flex items-center justify-center"
        >
          <BiometricScan />
        </motion.div>

        {/* Trust marks */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.6 }}
          className="flex flex-wrap gap-2"
        >
          {TRUST_MARKS.map((mark) => (
            <div
              key={mark}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs"
              style={{
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                color: 'rgba(255,255,255,0.5)',
              }}
            >
              <Shield className="w-3 h-3 text-cyan-500/60" />
              {mark}
            </div>
          ))}
        </motion.div>

        {/* PHI notice */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.8 }}
          className="mt-4 flex items-start gap-2 px-3 py-2.5 rounded-xl"
          style={{
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.06)',
          }}
        >
          <Shield className="w-3.5 h-3.5 text-cyan-500/50 mt-0.5 flex-shrink-0" />
          <p className="text-[11px] leading-relaxed" style={{ color: 'rgba(255,255,255,0.35)' }}>
            This system processes Protected Health Information (PHI). All access is logged
            and subject to HIPAA compliance requirements.
          </p>
        </motion.div>
      </div>
    </div>
  )
}
