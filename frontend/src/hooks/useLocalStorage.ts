import { useState, useCallback } from 'react'

export function useLocalStorage<T>(key: string, initialValue: T) {
  const [stored, setStored] = useState<T>(() => {
    try {
      const item = localStorage.getItem(key)
      return item ? JSON.parse(item) : initialValue
    } catch {
      return initialValue
    }
  })

  const setValue = useCallback((value: T | ((prev: T) => T)) => {
    try {
      const next = value instanceof Function ? value(stored) : value
      setStored(next)
      localStorage.setItem(key, JSON.stringify(next))
    } catch {
      // ignore write errors (private browsing, quota exceeded)
    }
  }, [key, stored])

  const remove = useCallback(() => {
    localStorage.removeItem(key)
    setStored(initialValue)
  }, [key, initialValue])

  return [stored, setValue, remove] as const
}