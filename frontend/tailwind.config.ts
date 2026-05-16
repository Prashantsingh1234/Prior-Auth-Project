import type { Config } from 'tailwindcss'

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Brand — clinical blue
        brand: {
          50:  '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe',
          300: '#93c5fd', 400: '#60a5fa', 500: '#3b82f6',
          600: '#2563eb', 700: '#1d4ed8', 800: '#1e40af', 900: '#1e3a8a',
          950: '#172554',
        },
        // Decision semantics
        approve:  { light: '#dcfce7', DEFAULT: '#16a34a', dark: '#15803d', muted: '#f0fdf4' },
        deny:     { light: '#fee2e2', DEFAULT: '#dc2626', dark: '#b91c1c', muted: '#fef2f2' },
        pend:     { light: '#fef3c7', DEFAULT: '#d97706', dark: '#b45309', muted: '#fffbeb' },
        escalate: { light: '#ede9fe', DEFAULT: '#7c3aed', dark: '#6d28d9', muted: '#f5f3ff' },
        // Dark surfaces
        dark: {
          bg:        '#0a0f1e',
          surface:   '#0f172a',
          elevated:  '#1e293b',
          border:    '#1e293b',
          border2:   '#334155',
          text:      '#f1f5f9',
          muted:     '#94a3b8',
        },
      },
      fontFamily: {
        sans: ['Inter var', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      boxShadow: {
        glow:      '0 0 20px -5px rgb(59 130 246 / 0.4)',
        'glow-sm': '0 0 12px -3px rgb(59 130 246 / 0.3)',
        card:      '0 1px 3px rgb(0 0 0 / 0.08), 0 1px 2px -1px rgb(0 0 0 / 0.06)',
        'card-md': '0 4px 16px -2px rgb(0 0 0 / 0.10), 0 2px 8px -2px rgb(0 0 0 / 0.06)',
        'card-lg': '0 10px 40px -4px rgb(0 0 0 / 0.12), 0 4px 16px -4px rgb(0 0 0 / 0.08)',
        approve:   '0 0 16px -4px rgb(22 163 74 / 0.5)',
        deny:      '0 0 16px -4px rgb(220 38 38 / 0.5)',
      },
      animation: {
        'fade-in':     'fadeIn 0.25s ease-out',
        'slide-up':    'slideUp 0.3s cubic-bezier(0.16,1,0.3,1)',
        'slide-right': 'slideRight 0.3s cubic-bezier(0.16,1,0.3,1)',
        'scale-in':    'scaleIn 0.2s cubic-bezier(0.16,1,0.3,1)',
        'pulse-slow':  'pulse 3s ease-in-out infinite',
        'shimmer':     'shimmer 1.5s ease-in-out infinite',
        'bounce-in':   'bounceIn 0.5s cubic-bezier(0.34,1.56,0.64,1)',
        'spin-slow':   'spin 3s linear infinite',
        'ping-slow':   'ping 2s ease-in-out infinite',
      },
      keyframes: {
        fadeIn:    { from: { opacity: '0' }, to: { opacity: '1' } },
        slideUp:   { from: { transform: 'translateY(12px)', opacity: '0' }, to: { transform: 'translateY(0)', opacity: '1' } },
        slideRight:{ from: { transform: 'translateX(-12px)', opacity: '0' }, to: { transform: 'translateX(0)', opacity: '1' } },
        scaleIn:   { from: { transform: 'scale(0.95)', opacity: '0' }, to: { transform: 'scale(1)', opacity: '1' } },
        bounceIn:  { from: { transform: 'scale(0.7)', opacity: '0' }, to: { transform: 'scale(1)', opacity: '1' } },
        shimmer:   { '0%,100%': { opacity: '0.4' }, '50%': { opacity: '0.8' } },
      },
      backgroundImage: {
        'gradient-radial':   'radial-gradient(var(--tw-gradient-stops))',
        'gradient-mesh':     'radial-gradient(at 40% 20%, hsla(220,100%,74%,0.15) 0, transparent 50%), radial-gradient(at 80% 0%, hsla(245,100%,74%,0.1) 0, transparent 50%), radial-gradient(at 0% 50%, hsla(220,100%,60%,0.08) 0, transparent 50%)',
        'grid-pattern':      'linear-gradient(to right, rgb(99 102 241 / 0.05) 1px, transparent 1px), linear-gradient(to bottom, rgb(99 102 241 / 0.05) 1px, transparent 1px)',
      },
      transitionTimingFunction: {
        spring: 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
    },
  },
  plugins: [],
} satisfies Config