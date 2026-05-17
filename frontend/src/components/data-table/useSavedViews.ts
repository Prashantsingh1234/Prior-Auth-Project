import { useState, useCallback } from 'react'
import type { SavedView } from './types'

export function useSavedViews(tableId: string, systemViews: Omit<SavedView, 'id' | 'createdAt'>[] = []) {
  const key = `pa-table-views-${tableId}`

  const [userViews, setUserViews] = useState<SavedView[]>(() => {
    try { return JSON.parse(localStorage.getItem(key) ?? '[]') }
    catch { return [] }
  })

  const builtinViews: SavedView[] = systemViews.map((v, i) => ({
    ...v,
    id:        `system-${i}`,
    createdAt: '2024-01-01T00:00:00Z',
    isSystem:  true,
  }))

  const views = [...builtinViews, ...userViews]

  const save = useCallback((name: string, state: Omit<SavedView, 'id' | 'name' | 'createdAt' | 'isSystem'>) => {
    const view: SavedView = {
      ...state,
      id:        crypto.randomUUID(),
      name:      name.trim(),
      createdAt: new Date().toISOString(),
    }
    setUserViews((prev) => {
      const filtered = prev.filter((v) => v.name !== name.trim())
      const next     = [...filtered, view]
      localStorage.setItem(key, JSON.stringify(next))
      return next
    })
    return view
  }, [key])

  const remove = useCallback((id: string) => {
    setUserViews((prev) => {
      const next = prev.filter((v) => v.id !== id)
      localStorage.setItem(key, JSON.stringify(next))
      return next
    })
  }, [key])

  return { views, save, remove }
}
