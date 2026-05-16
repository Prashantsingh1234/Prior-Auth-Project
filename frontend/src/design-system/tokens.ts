/**
 * Design Tokens — single source of truth for the design system.
 * Import from here, not hardcoded hex values.
 */

// ─── Typography ───────────────────────────────────────────────────────────────

export const FONT = {
  sans:     "'Inter var', 'Inter', system-ui, sans-serif",
  display:  "'Geist', 'Inter var', sans-serif",
  heading:  "'Manrope', sans-serif",
  mono:     "'Geist Mono', 'JetBrains Mono', monospace",
  clinical: "'Geist Mono', 'Courier New', monospace",
} as const

export const TYPE_SCALE = {
  display:    { size: '48px', weight: 800, lineHeight: 1.05, tracking: '-0.03em', font: 'display' },
  displaySm:  { size: '36px', weight: 700, lineHeight: 1.10, tracking: '-0.02em', font: 'display' },
  h1:         { size: '28px', weight: 700, lineHeight: 1.20, tracking: '-0.015em', font: 'heading' },
  h2:         { size: '22px', weight: 600, lineHeight: 1.25, tracking: '-0.01em', font: 'heading' },
  h3:         { size: '18px', weight: 600, lineHeight: 1.30, tracking: '0',       font: 'heading' },
  h4:         { size: '15px', weight: 600, lineHeight: 1.40, tracking: '0',       font: 'heading' },
  metric:     { size: '42px', weight: 700, lineHeight: 1.00, tracking: '-0.03em', font: 'display', tabular: true },
  metricSm:   { size: '28px', weight: 700, lineHeight: 1.00, tracking: '-0.02em', font: 'display', tabular: true },
  bodyLg:     { size: '15px', weight: 400, lineHeight: 1.65, tracking: '0',       font: 'sans' },
  body:       { size: '14px', weight: 400, lineHeight: 1.60, tracking: '0',       font: 'sans' },
  bodySm:     { size: '13px', weight: 400, lineHeight: 1.55, tracking: '0',       font: 'sans' },
  aiReasoning:{ size: '14px', weight: 400, lineHeight: 1.65, tracking: '0.005em', font: 'sans',  italic: true },
  evidence:   { size: '13px', weight: 400, lineHeight: 1.60, tracking: '0',       font: 'clinical' },
  comment:    { size: '14px', weight: 400, lineHeight: 1.70, tracking: '0',       font: 'sans' },
  audit:      { size: '11px', weight: 400, lineHeight: 1.50, tracking: '0.02em',  font: 'mono' },
  label:      { size: '11px', weight: 700, lineHeight: 1.00, tracking: '0.08em',  font: 'heading', uppercase: true },
  caption:    { size: '12px', weight: 400, lineHeight: 1.40, tracking: '0',       font: 'sans' },
  code:       { size: '12px', weight: 400, lineHeight: 1.50, tracking: '0',       font: 'mono' },
} as const

// ─── Color palette ────────────────────────────────────────────────────────────

export const COLOR = {
  // Deep Navy
  navy: {
    950: '#020817', 900: '#0a0f1e', 850: '#0d1424', 800: '#0f172a',
    700: '#1a2540', 600: '#1e3a6e', 500: '#1d4ed8', 400: '#3b82f6',
    300: '#60a5fa', 200: '#93c5fd', 100: '#dbeafe', 50: '#eff6ff',
  },

  // Healthcare Cyan
  cyan: {
    900: '#0c4a6e', 800: '#075985', 700: '#0369a1', 600: '#0284c7',
    500: '#0ea5e9', 400: '#38bdf8', 300: '#7dd3fc', 200: '#bae6fd',
    100: '#e0f2fe', 50: '#f0f9ff',
  },

  // AI Purple
  ai: {
    900: '#2e1065', 800: '#3b0764', 700: '#4c1d95', 600: '#5b21b6',
    500: '#7c3aed', 400: '#8b5cf6', 300: '#a78bfa', 200: '#c4b5fd',
    100: '#ede9fe', 50: '#f5f3ff',
  },

  // Enterprise Slate
  slate: {
    1000: '#020617', 950: '#0a0f1e', 900: '#0f172a', 800: '#1e293b',
    700: '#334155', 600: '#475569', 500: '#64748b', 400: '#94a3b8',
    300: '#cbd5e1', 200: '#e2e8f0', 100: '#f1f5f9', 50: '#f8fafc',
  },
} as const

// ─── Status semantic tokens ───────────────────────────────────────────────────

export const STATUS = {
  approve: {
    color:   '#10b981',
    dark:    '#059669',
    light:   '#34d399',
    surface: 'rgba(16,185,129,0.08)',
    border:  'rgba(16,185,129,0.2)',
    glow:    'rgba(16,185,129,0.35)',
    text:    'text-emerald-400',
    bg:      'bg-emerald-500/10',
    ring:    'ring-emerald-500',
  },
  deny: {
    color:   '#ef4444',
    dark:    '#dc2626',
    light:   '#f87171',
    surface: 'rgba(239,68,68,0.08)',
    border:  'rgba(239,68,68,0.2)',
    glow:    'rgba(239,68,68,0.35)',
    text:    'text-red-400',
    bg:      'bg-red-500/10',
    ring:    'ring-red-500',
  },
  pend: {
    color:   '#f59e0b',
    dark:    '#d97706',
    light:   '#fbbf24',
    surface: 'rgba(245,158,11,0.08)',
    border:  'rgba(245,158,11,0.2)',
    glow:    'rgba(245,158,11,0.35)',
    text:    'text-amber-400',
    bg:      'bg-amber-500/10',
    ring:    'ring-amber-500',
  },
  review: {
    color:   '#3b82f6',
    dark:    '#2563eb',
    light:   '#60a5fa',
    surface: 'rgba(59,130,246,0.08)',
    border:  'rgba(59,130,246,0.2)',
    glow:    'rgba(59,130,246,0.35)',
    text:    'text-blue-400',
    bg:      'bg-blue-500/10',
    ring:    'ring-blue-500',
  },
  escalate: {
    color:   '#8b5cf6',
    dark:    '#7c3aed',
    light:   '#a78bfa',
    surface: 'rgba(139,92,246,0.08)',
    border:  'rgba(139,92,246,0.2)',
    glow:    'rgba(139,92,246,0.35)',
    text:    'text-violet-400',
    bg:      'bg-violet-500/10',
    ring:    'ring-violet-500',
  },
} as const

// ─── AI Confidence heatmap ────────────────────────────────────────────────────

export const CONFIDENCE_HEATMAP = [
  { min: 0,    max: 0.59, label: 'Critical', color: '#ef4444', glow: 'rgba(239,68,68,0.4)',   css: 'conf-critical', tw: 'text-red-400',    bg: 'bg-red-500/10' },
  { min: 0.60, max: 0.69, label: 'Low',      color: '#f97316', glow: 'rgba(249,115,22,0.35)', css: 'conf-low',      tw: 'text-orange-400', bg: 'bg-orange-500/10' },
  { min: 0.70, max: 0.79, label: 'Medium',   color: '#f59e0b', glow: 'rgba(245,158,11,0.35)', css: 'conf-medium',   tw: 'text-amber-400',  bg: 'bg-amber-500/10' },
  { min: 0.80, max: 0.89, label: 'Good',     color: '#84cc16', glow: 'rgba(132,204,22,0.35)', css: 'conf-good',     tw: 'text-lime-400',   bg: 'bg-lime-500/10' },
  { min: 0.90, max: 0.94, label: 'High',     color: '#10b981', glow: 'rgba(16,185,129,0.4)',  css: 'conf-high',     tw: 'text-emerald-400',bg: 'bg-emerald-500/10' },
  { min: 0.95, max: 1.00, label: 'Perfect',  color: '#06d6a0', glow: 'rgba(6,214,160,0.45)',  css: 'conf-perfect',  tw: 'text-teal-400',   bg: 'bg-teal-500/10' },
] as const

export type ConfidenceLevel = (typeof CONFIDENCE_HEATMAP)[number]['label']

export function getConfidenceToken(score: number) {
  return CONFIDENCE_HEATMAP.find((b) => score >= b.min && score <= b.max)
    ?? CONFIDENCE_HEATMAP[0]
}

// ─── Spacing & radius ──────────────────────────────────────────────────────────

export const RADIUS = {
  sm:   '6px',
  md:   '8px',
  lg:   '12px',
  xl:   '16px',
  '2xl':'20px',
  '3xl':'24px',
  full: '9999px',
} as const

// ─── Shadow ───────────────────────────────────────────────────────────────────

export const SHADOW = {
  glass:    '0 8px 32px rgba(0,0,0,0.12), 0 0 0 1px rgba(255,255,255,0.06) inset',
  card:     '0 1px 4px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)',
  cardMd:   '0 2px 8px rgba(0,0,0,0.08), 0 8px 32px rgba(0,0,0,0.06)',
  cardLg:   '0 4px 16px rgba(0,0,0,0.10), 0 16px 56px rgba(0,0,0,0.08)',
  glowAi:   '0 0 24px -4px rgba(139,92,246,0.45)',
  glowCyan: '0 0 24px -4px rgba(14,165,233,0.4)',
} as const

// ─── Transition ───────────────────────────────────────────────────────────────

export const EASE = {
  fast:   '0.15s cubic-bezier(0.4,0,0.2,1)',
  base:   '0.2s cubic-bezier(0.4,0,0.2,1)',
  slow:   '0.3s cubic-bezier(0.16,1,0.3,1)',
  spring: '0.5s cubic-bezier(0.34,1.56,0.64,1)',
} as const