import type { Config } from 'tailwindcss'
import { fontFamily } from 'tailwindcss/defaultTheme'

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {

      // ─── Fonts ──────────────────────────────────────────────────────────────
      fontFamily: {
        sans:    ['Inter var', 'Inter', ...fontFamily.sans],
        display: ['Geist', 'Geist Fallback', ...fontFamily.sans],
        heading: ['Manrope', ...fontFamily.sans],
        mono:    ['Geist Mono', 'JetBrains Mono', ...fontFamily.mono],
        clinical:['Geist Mono', 'Courier New', 'monospace'],
      },

      // ─── Font sizes ──────────────────────────────────────────────────────────
      fontSize: {
        '2xs':   ['10px', { lineHeight: '14px', letterSpacing: '0.04em' }],
        'xs':    ['11px', { lineHeight: '16px' }],
        'sm':    ['13px', { lineHeight: '20px' }],
        'base':  ['14px', { lineHeight: '22px' }],
        'md':    ['15px', { lineHeight: '24px' }],
        'lg':    ['16px', { lineHeight: '26px' }],
        'xl':    ['18px', { lineHeight: '28px' }],
        '2xl':   ['22px', { lineHeight: '30px' }],
        '3xl':   ['28px', { lineHeight: '36px' }],
        '4xl':   ['36px', { lineHeight: '44px' }],
        '5xl':   ['48px', { lineHeight: '56px', letterSpacing: '-0.02em' }],
        '6xl':   ['60px', { lineHeight: '68px', letterSpacing: '-0.03em' }],
        'metric': ['42px', { lineHeight: '1', letterSpacing: '-0.03em', fontFeatureSettings: '"tnum"' }],
      },

      // ─── Colors ──────────────────────────────────────────────────────────────
      colors: {

        // Deep Navy — primary brand identity
        navy: {
          950: '#020817',
          900: '#0a0f1e',
          850: '#0d1424',
          800: '#0f172a',
          750: '#111827',
          700: '#1a2540',
          600: '#1e3a6e',
          500: '#1d4ed8',
          400: '#3b82f6',
          300: '#60a5fa',
          200: '#93c5fd',
          100: '#dbeafe',
          50:  '#eff6ff',
        },

        // Healthcare Cyan — clinical accent
        cyan: {
          950: '#083344',
          900: '#0c4a6e',
          800: '#075985',
          700: '#0369a1',
          600: '#0284c7',
          500: '#0ea5e9',
          400: '#38bdf8',
          300: '#7dd3fc',
          200: '#bae6fd',
          100: '#e0f2fe',
          50:  '#f0f9ff',
        },

        // AI Purple — intelligence accent
        ai: {
          950: '#1e0042',
          900: '#2e1065',
          800: '#3b0764',
          700: '#4c1d95',
          600: '#5b21b6',
          500: '#7c3aed',
          400: '#8b5cf6',
          300: '#a78bfa',
          200: '#c4b5fd',
          100: '#ede9fe',
          50:  '#f5f3ff',
        },

        // Enterprise Slate — neutral foundation
        slate: {
          1000: '#020617',
          950:  '#0a0f1e',
          900:  '#0f172a',
          800:  '#1e293b',
          750:  '#243044',
          700:  '#334155',
          600:  '#475569',
          500:  '#64748b',
          400:  '#94a3b8',
          300:  '#cbd5e1',
          200:  '#e2e8f0',
          100:  '#f1f5f9',
          50:   '#f8fafc',
        },

        // Status semantic colors — healthcare decision palette
        approve:  {
          DEFAULT: '#10b981',
          dark:    '#059669',
          light:   '#34d399',
          muted:   '#d1fae5',
          surface: 'rgba(16,185,129,0.08)',
          border:  'rgba(16,185,129,0.2)',
          glow:    'rgba(16,185,129,0.35)',
        },
        deny: {
          DEFAULT: '#ef4444',
          dark:    '#dc2626',
          light:   '#f87171',
          muted:   '#fee2e2',
          surface: 'rgba(239,68,68,0.08)',
          border:  'rgba(239,68,68,0.2)',
          glow:    'rgba(239,68,68,0.35)',
        },
        pend: {
          DEFAULT: '#f59e0b',
          dark:    '#d97706',
          light:   '#fbbf24',
          muted:   '#fef3c7',
          surface: 'rgba(245,158,11,0.08)',
          border:  'rgba(245,158,11,0.2)',
          glow:    'rgba(245,158,11,0.35)',
        },
        review: {
          DEFAULT: '#3b82f6',
          dark:    '#2563eb',
          light:   '#60a5fa',
          muted:   '#dbeafe',
          surface: 'rgba(59,130,246,0.08)',
          border:  'rgba(59,130,246,0.2)',
          glow:    'rgba(59,130,246,0.35)',
        },
        escalate: {
          DEFAULT: '#8b5cf6',
          dark:    '#7c3aed',
          light:   '#a78bfa',
          muted:   '#ede9fe',
          surface: 'rgba(139,92,246,0.08)',
          border:  'rgba(139,92,246,0.2)',
          glow:    'rgba(139,92,246,0.35)',
        },

        // AI confidence heatmap
        confidence: {
          critical: '#ef4444',
          low:      '#f97316',
          medium:   '#f59e0b',
          good:     '#84cc16',
          high:     '#10b981',
          perfect:  '#06d6a0',
        },
      },

      // ─── Spacing ─────────────────────────────────────────────────────────────
      spacing: {
        '4.5': '1.125rem',
        '13':  '3.25rem',
        '15':  '3.75rem',
        '18':  '4.5rem',
        '22':  '5.5rem',
        '26':  '6.5rem',
        '30':  '7.5rem',
      },

      // ─── Border radius ───────────────────────────────────────────────────────
      borderRadius: {
        '4xl': '2rem',
        '5xl': '2.5rem',
      },

      // ─── Shadows ─────────────────────────────────────────────────────────────
      boxShadow: {
        // Glass morphism layers
        'glass':    '0 4px 24px -4px rgba(0,0,0,0.12), 0 0 0 1px rgba(255,255,255,0.06) inset',
        'glass-md': '0 8px 40px -6px rgba(0,0,0,0.18), 0 0 0 1px rgba(255,255,255,0.08) inset',
        'glass-lg': '0 16px 64px -8px rgba(0,0,0,0.24), 0 0 0 1px rgba(255,255,255,0.10) inset',

        // Cards
        'card':    '0 1px 4px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)',
        'card-md': '0 2px 8px rgba(0,0,0,0.08), 0 8px 32px rgba(0,0,0,0.06)',
        'card-lg': '0 4px 16px rgba(0,0,0,0.10), 0 16px 56px rgba(0,0,0,0.08)',
        'card-xl': '0 8px 32px rgba(0,0,0,0.12), 0 32px 80px rgba(0,0,0,0.10)',

        // Glow — decision semantic
        'glow-navy':    '0 0 24px -4px rgba(59,130,246,0.4)',
        'glow-cyan':    '0 0 24px -4px rgba(14,165,233,0.4)',
        'glow-ai':      '0 0 24px -4px rgba(139,92,246,0.45)',
        'glow-approve': '0 0 24px -4px rgba(16,185,129,0.45)',
        'glow-deny':    '0 0 24px -4px rgba(239,68,68,0.45)',
        'glow-pend':    '0 0 20px -4px rgba(245,158,11,0.4)',
        'glow-escalate':'0 0 24px -4px rgba(139,92,246,0.45)',

        // Elevation
        'elevation-1': '0 1px 2px rgba(0,0,0,0.05)',
        'elevation-2': '0 2px 8px rgba(0,0,0,0.08)',
        'elevation-3': '0 4px 16px rgba(0,0,0,0.10)',
        'elevation-4': '0 8px 32px rgba(0,0,0,0.14)',
        'elevation-5': '0 20px 60px rgba(0,0,0,0.18)',
      },

      // ─── Backdrop blur ───────────────────────────────────────────────────────
      backdropBlur: {
        xs: '2px',
        sm: '4px',
        md: '8px',
        lg: '16px',
        xl: '24px',
        '2xl': '40px',
        '3xl': '64px',
      },

      // ─── Animations ──────────────────────────────────────────────────────────
      animation: {
        // Entry
        'fade-in':       'fadeIn 0.2s ease-out',
        'fade-in-up':    'fadeInUp 0.3s cubic-bezier(0.16,1,0.3,1)',
        'fade-in-down':  'fadeInDown 0.25s cubic-bezier(0.16,1,0.3,1)',
        'slide-in-left': 'slideInLeft 0.3s cubic-bezier(0.16,1,0.3,1)',
        'scale-in':      'scaleIn 0.2s cubic-bezier(0.16,1,0.3,1)',
        'bounce-in':     'bounceIn 0.5s cubic-bezier(0.34,1.56,0.64,1)',

        // Loops
        'pulse-slow':    'pulse 3s ease-in-out infinite',
        'pulse-glow':    'pulseGlow 2.5s ease-in-out infinite',
        'ping-slow':     'ping 2.5s ease-in-out infinite',
        'shimmer':       'shimmer 1.8s linear infinite',
        'spin-slow':     'spin 4s linear infinite',
        'float':         'float 6s ease-in-out infinite',
        'border-glow':   'borderGlow 3s ease-in-out infinite',

        // Confidence bar
        'fill':          'fill 0.8s cubic-bezier(0.34,1,0.64,1)',
      },
      keyframes: {
        fadeIn:      { from: { opacity: '0' }, to: { opacity: '1' } },
        fadeInUp:    { from: { opacity: '0', transform: 'translateY(12px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        fadeInDown:  { from: { opacity: '0', transform: 'translateY(-8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        slideInLeft: { from: { opacity: '0', transform: 'translateX(-16px)' }, to: { opacity: '1', transform: 'translateX(0)' } },
        scaleIn:     { from: { opacity: '0', transform: 'scale(0.94)' }, to: { opacity: '1', transform: 'scale(1)' } },
        bounceIn: {
          '0%':   { opacity: '0', transform: 'scale(0.8)' },
          '60%':  { opacity: '1', transform: 'scale(1.04)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        pulseGlow: {
          '0%,100%': { opacity: '0.6', transform: 'scale(1)' },
          '50%':     { opacity: '1',   transform: 'scale(1.08)' },
        },
        float: {
          '0%,100%': { transform: 'translateY(0)' },
          '50%':     { transform: 'translateY(-8px)' },
        },
        borderGlow: {
          '0%,100%': { boxShadow: '0 0 4px rgba(99,102,241,0.3)' },
          '50%':     { boxShadow: '0 0 20px rgba(99,102,241,0.7), 0 0 40px rgba(139,92,246,0.3)' },
        },
        fill: {
          from: { width: '0%' },
          to:   { width: 'var(--fill-target)' },
        },
      },

      // ─── Background images ───────────────────────────────────────────────────
      backgroundImage: {
        'gradient-radial':      'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic':       'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
        'gradient-mesh':        'radial-gradient(at 40% 20%, hsla(228,97%,60%,0.12) 0, transparent 50%), radial-gradient(at 80% 0%, hsla(270,97%,70%,0.08) 0, transparent 50%), radial-gradient(at 0% 50%, hsla(200,97%,55%,0.08) 0, transparent 50%)',
        'shimmer':              'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.06) 50%, transparent 100%)',
        'grid-pattern':         'linear-gradient(var(--grid-color) 1px, transparent 1px), linear-gradient(90deg, var(--grid-color) 1px, transparent 1px)',
        'noise':                "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.03'/%3E%3C/svg%3E\")",
      },
    },
  },
  plugins: [],
} satisfies Config