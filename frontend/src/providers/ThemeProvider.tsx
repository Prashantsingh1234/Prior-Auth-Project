import { useEffect } from 'react'
import { useUIStore } from '@/store'

interface Props { children: React.ReactNode }

export function ThemeProvider({ children }: Props) {
  const { theme, applyTheme } = useUIStore()
  useEffect(() => { applyTheme() }, [theme, applyTheme])

  // React to system theme changes when theme === 'system'
  useEffect(() => {
    if (theme !== 'system') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => applyTheme()
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [theme, applyTheme])

  return <>{children}</>
}