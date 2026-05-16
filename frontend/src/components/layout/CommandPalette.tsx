import { useEffect, useRef, useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import {
  Search, LayoutDashboard, ClipboardList, BarChart3, BookOpen,
  FileText, Settings, Users, Brain, Activity, Zap, ArrowRight,
  Clock, X, Command,
} from 'lucide-react'
import { useUIStore } from '@/store/uiStore'
import { usePermissions } from '@/hooks'
import { cn } from '@/lib/utils'
import { ROUTES } from '@/config/routes.config'

// ─── Types ────────────────────────────────────────────────────────────────────

type CommandCategory = 'navigation' | 'actions' | 'recent' | 'search'

interface CommandItem {
  id:          string
  category:    CommandCategory
  label:       string
  description?: string
  icon:        React.ElementType
  shortcut?:   string
  action:      () => void
  permission?: string
}

// ─── Static command registry ──────────────────────────────────────────────────

function useCommands(): CommandItem[] {
  const navigate = useNavigate()
  const { can } = usePermissions()
  const { setCommandOpen, setAIPanelOpen } = useUIStore()

  const close = () => setCommandOpen(false)

  const go = (path: string) => { navigate(path); close() }

  return useMemo(() => {
    const all: CommandItem[] = [
      // Navigation
      { id: 'nav-dashboard',  category: 'navigation', label: 'Dashboard',          icon: LayoutDashboard, shortcut: 'G D', action: () => go(ROUTES.DASHBOARD) },
      { id: 'nav-cases',      category: 'navigation', label: 'Case Queue',          icon: ClipboardList,  shortcut: 'G C', action: () => go(ROUTES.CASES) },
      { id: 'nav-analytics',  category: 'navigation', label: 'AI Analytics',        icon: BarChart3,      shortcut: 'G A', action: () => go(ROUTES.ANALYTICS),  permission: 'analytics:read' },
      { id: 'nav-policies',   category: 'navigation', label: 'Policies',            icon: BookOpen,                        action: () => go(ROUTES.POLICIES),   permission: 'policies:read' },
      { id: 'nav-audit',      category: 'navigation', label: 'Audit Log',           icon: FileText,       shortcut: 'G U', action: () => go(ROUTES.AUDIT),      permission: 'audit:read' },
      { id: 'nav-monitoring', category: 'navigation', label: 'System Monitoring',   icon: Activity,                        action: () => go(ROUTES.MONITORING) },
      { id: 'nav-users',      category: 'navigation', label: 'User Management',     icon: Users,                           action: () => go(ROUTES.USERS),      permission: 'admin:users' },
      { id: 'nav-settings',   category: 'navigation', label: 'Settings',            icon: Settings,       shortcut: 'G S', action: () => go(ROUTES.SETTINGS),   permission: 'admin:settings' },
      // Actions
      { id: 'act-ai-panel',   category: 'actions',    label: 'Open AI Assistant',   description: 'Chat with the PA Review AI', icon: Brain,  shortcut: '⌥A', action: () => { setAIPanelOpen(true); close() } },
      { id: 'act-new-case',   category: 'actions',    label: 'Submit New Case',     description: 'Start a new prior authorization', icon: Zap,   shortcut: '⌘N', action: () => { go(`${ROUTES.CASES}/new`) }, permission: 'cases:write' },
    ]
    return all.filter((c) => !c.permission || can(c.permission as any))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [can])
}

// ─── Component ────────────────────────────────────────────────────────────────

const CATEGORY_LABEL: Record<CommandCategory, string> = {
  navigation: 'Navigation',
  actions:    'Actions',
  recent:     'Recent',
  search:     'Results',
}

export function CommandPalette() {
  const { commandOpen, setCommandOpen } = useUIStore()
  const [query, setQuery]     = useState('')
  const [selected, setSelected] = useState(0)
  const inputRef              = useRef<HTMLInputElement>(null)
  const listRef               = useRef<HTMLDivElement>(null)
  const commands              = useCommands()

  // Global keyboard shortcut
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setCommandOpen(true)
      }
      if (e.key === 'Escape') setCommandOpen(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [setCommandOpen])

  // Focus input when opened
  useEffect(() => {
    if (commandOpen) {
      setQuery('')
      setSelected(0)
      setTimeout(() => inputRef.current?.focus(), 60)
    }
  }, [commandOpen])

  // Filter commands
  const filtered = useMemo(() => {
    if (!query.trim()) return commands
    const q = query.toLowerCase()
    return commands.filter(
      (c) => c.label.toLowerCase().includes(q) || c.description?.toLowerCase().includes(q)
    )
  }, [commands, query])

  // Group by category
  const grouped = useMemo(() => {
    const map = new Map<CommandCategory, CommandItem[]>()
    filtered.forEach((c) => {
      const group = map.get(c.category) ?? []
      group.push(c)
      map.set(c.category, group)
    })
    return map
  }, [filtered])

  const flatItems = useMemo(() => filtered, [filtered])

  // Keyboard navigation
  useEffect(() => {
    if (!commandOpen) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelected((i) => Math.min(i + 1, flatItems.length - 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelected((i) => Math.max(i - 1, 0))
      } else if (e.key === 'Enter') {
        e.preventDefault()
        flatItems[selected]?.action()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [commandOpen, flatItems, selected])

  // Scroll selected into view
  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-idx="${selected}"]`) as HTMLElement | null
    el?.scrollIntoView({ block: 'nearest' })
  }, [selected])

  let globalIdx = -1

  return (
    <AnimatePresence>
      {commandOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={() => setCommandOpen(false)}
            className="fixed inset-0 z-[80] bg-black/50 backdrop-blur-sm"
          />

          {/* Palette */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{ type: 'spring', stiffness: 500, damping: 35 }}
            className="fixed left-1/2 top-[20vh] -translate-x-1/2 z-[81] w-full max-w-xl shadow-card-xl"
            style={{ borderRadius: 16 }}
          >
            <div
              className="overflow-hidden rounded-2xl"
              style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
            >
              {/* Search input */}
              <div className="flex items-center gap-3 px-4 border-b border-[var(--border)]">
                <Command className="w-4 h-4 text-[var(--text-3)] flex-shrink-0" />
                <input
                  ref={inputRef}
                  value={query}
                  onChange={(e) => { setQuery(e.target.value); setSelected(0) }}
                  placeholder="Search commands, cases, settings…"
                  className="flex-1 h-14 bg-transparent text-[var(--text-1)] text-base outline-none placeholder:text-[var(--text-4)]"
                />
                {query && (
                  <button onClick={() => setQuery('')} className="text-[var(--text-3)] hover:text-[var(--text-2)]">
                    <X className="w-4 h-4" />
                  </button>
                )}
                <kbd className="text-xs font-mono text-[var(--text-4)] border border-[var(--border)] px-1.5 py-0.5 rounded">
                  ESC
                </kbd>
              </div>

              {/* Results */}
              <div ref={listRef} className="max-h-80 overflow-y-auto py-2">
                {filtered.length === 0 ? (
                  <div className="py-10 text-center text-sm text-[var(--text-3)]">
                    No results for "{query}"
                  </div>
                ) : (
                  Array.from(grouped.entries()).map(([category, items]) => (
                    <div key={category}>
                      <div className="px-4 py-1.5">
                        <span className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-4)]">
                          {CATEGORY_LABEL[category]}
                        </span>
                      </div>
                      {items.map((item) => {
                        const Icon = item.icon
                        globalIdx++
                        const idx = globalIdx
                        const isSelected = selected === idx

                        return (
                          <motion.button
                            key={item.id}
                            data-idx={idx}
                            onClick={item.action}
                            onMouseEnter={() => setSelected(idx)}
                            whileTap={{ scale: 0.98 }}
                            className={cn(
                              'w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors',
                              isSelected ? 'bg-cyan-500/10' : 'hover:bg-[var(--elevated)]',
                            )}
                          >
                            <div className={cn(
                              'w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0',
                              isSelected ? 'bg-cyan-500/20' : 'bg-[var(--elevated)]',
                            )}>
                              <Icon className={cn('w-3.5 h-3.5', isSelected ? 'text-cyan-400' : 'text-[var(--text-3)]')} />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className={cn('text-sm font-medium', isSelected ? 'text-cyan-400' : 'text-[var(--text-1)]')}>
                                {item.label}
                              </p>
                              {item.description && (
                                <p className="text-xs text-[var(--text-4)] truncate">{item.description}</p>
                              )}
                            </div>
                            {item.shortcut && (
                              <kbd className="text-[10px] font-mono text-[var(--text-4)] border border-[var(--border)] px-1.5 py-0.5 rounded flex-shrink-0">
                                {item.shortcut}
                              </kbd>
                            )}
                            {isSelected && <ArrowRight className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0" />}
                          </motion.button>
                        )
                      })}
                    </div>
                  ))
                )}
              </div>

              {/* Footer */}
              <div className="flex items-center gap-4 px-4 py-2.5 border-t border-[var(--border)]">
                {[['↑↓', 'navigate'], ['↵', 'select'], ['ESC', 'close']].map(([key, label]) => (
                  <span key={key} className="flex items-center gap-1.5 text-xs text-[var(--text-4)]">
                    <kbd className="font-mono border border-[var(--border)] px-1 py-0.5 rounded text-[10px]">{key}</kbd>
                    {label}
                  </span>
                ))}
                <span className="ml-auto text-xs text-[var(--text-4)]">{filtered.length} results</span>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
