export const BREAKPOINTS = { sm: 640, md: 768, lg: 1024, xl: 1280, '2xl': 1536 } as const

export const TRANSITION = {
  fast:   { duration: 0.15 },
  base:   { duration: 0.2  },
  slow:   { duration: 0.3  },
  spring: { type: 'spring', stiffness: 400, damping: 30 },
} as const

export const TOAST_DURATION = {
  short:  2500,
  medium: 4000,
  long:   6000,
} as const

export const Z_INDEX = {
  dropdown:  1000,
  sticky:    1020,
  fixed:     1030,
  modal:     1040,
  popover:   1050,
  tooltip:   1060,
  toast:     1070,
} as const