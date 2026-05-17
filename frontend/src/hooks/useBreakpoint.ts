import { useState, useEffect } from 'react'

const QUERIES = {
  sm:   '(min-width: 640px)',
  md:   '(min-width: 768px)',
  lg:   '(min-width: 1024px)',
  xl:   '(min-width: 1280px)',
  '2xl': '(min-width: 1536px)',
  '3xl': '(min-width: 1920px)',
} as const

type BP = keyof typeof QUERIES

export function useBreakpoint(bp: BP): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia(QUERIES[bp]).matches : false,
  )
  useEffect(() => {
    const mq = window.matchMedia(QUERIES[bp])
    setMatches(mq.matches)
    const handler = (e: MediaQueryListEvent) => setMatches(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [bp])
  return matches
}

export const useIsMobile   = () => !useBreakpoint('md')
export const useIsTablet   = () => {
  const md = useBreakpoint('md')
  const lg = useBreakpoint('lg')
  return md && !lg
}
export const useIsDesktop  = () => useBreakpoint('lg')
export const useIsUltrawide = () => useBreakpoint('2xl')
