import { useEffect, useRef, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, ClipboardList, BarChart3, FileText,
  X, Plus, ChevronLeft, ChevronRight,
} from 'lucide-react'
import { useUIStore, type WorkspaceTab } from '@/store/uiStore'
import { cn } from '@/lib/utils'

const TAB_ICONS: Record<WorkspaceTab['type'], React.ElementType> = {
  dashboard: LayoutDashboard,
  case:      FileText,
  review:    FileText,
  analytics: BarChart3,
  page:      ClipboardList,
}

const STATUS_DOT: Record<string, string> = {
  APPROVED:     'bg-emerald-400',
  DENIED:       'bg-red-400',
  PENDED:       'bg-amber-400',
  UNDER_REVIEW: 'bg-cyan-400',
  ESCALATED:    'bg-violet-400',
}

export function WorkspaceTabs() {
  const { workspaceTabs, activeTabId, setActiveTab, removeTab } = useUIStore()
  const navigate   = useNavigate()
  const location   = useLocation()
  const scrollRef  = useRef<HTMLDivElement>(null)

  // Sync active tab with current path
  useEffect(() => {
    const match = workspaceTabs.find((t) => t.path === location.pathname)
    if (match && match.id !== activeTabId) setActiveTab(match.id)
  }, [location.pathname, workspaceTabs, activeTabId, setActiveTab])

  function handleTabClick(tab: WorkspaceTab) {
    setActiveTab(tab.id)
    navigate(tab.path)
  }

  function handleClose(e: React.MouseEvent, tab: WorkspaceTab) {
    e.stopPropagation()
    const idx  = workspaceTabs.findIndex((t) => t.id === tab.id)
    const next = workspaceTabs[idx - 1] ?? workspaceTabs[idx + 1]
    removeTab(tab.id)
    if (tab.id === activeTabId && next) {
      navigate(next.path)
    }
  }

  // Arrow key navigation within tablist
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    const activeIdx = workspaceTabs.findIndex((t) => t.id === activeTabId)
    if (e.key === 'ArrowRight') {
      e.preventDefault()
      const next = workspaceTabs[activeIdx + 1]
      if (next) { setActiveTab(next.id); navigate(next.path) }
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault()
      const prev = workspaceTabs[activeIdx - 1]
      if (prev) { setActiveTab(prev.id); navigate(prev.path) }
    } else if (e.key === 'Home') {
      e.preventDefault()
      const first = workspaceTabs[0]
      if (first) { setActiveTab(first.id); navigate(first.path) }
    } else if (e.key === 'End') {
      e.preventDefault()
      const last = workspaceTabs[workspaceTabs.length - 1]
      if (last) { setActiveTab(last.id); navigate(last.path) }
    }
  }, [workspaceTabs, activeTabId, setActiveTab, navigate])

  function scrollLeft()  { scrollRef.current?.scrollBy({ left: -120, behavior: 'smooth' }) }
  function scrollRight() { scrollRef.current?.scrollBy({ left: 120,  behavior: 'smooth' }) }

  if (workspaceTabs.length === 0) return null

  return (
    <div
      className="flex items-center border-b border-[var(--border)] flex-shrink-0 h-9 overflow-x-auto"
      style={{ background: 'var(--surface)', scrollbarWidth: 'none' }}
    >
      {/* Scroll left */}
      {workspaceTabs.length > 4 && (
        <button
          onClick={scrollLeft}
          aria-label="Scroll tabs left"
          className="px-1.5 text-[var(--text-4)] hover:text-[var(--text-2)] flex-shrink-0"
        >
          <ChevronLeft className="w-3.5 h-3.5" />
        </button>
      )}

      {/* Tabs */}
      <div
        ref={scrollRef}
        role="tablist"
        aria-label="Open tabs"
        onKeyDown={handleKeyDown}
        className="flex items-end flex-1 overflow-x-auto overflow-y-hidden scrollbar-none"
        style={{ scrollbarWidth: 'none' }}
      >
        <AnimatePresence initial={false}>
          {workspaceTabs.map((tab) => {
            const Icon     = TAB_ICONS[tab.type] ?? FileText
            const isActive = tab.id === activeTabId
            const dotColor = tab.status ? STATUS_DOT[tab.status] : null

            return (
              <motion.button
                key={tab.id}
                layout
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: 'auto' }}
                exit={{ opacity: 0, width: 0 }}
                transition={{ duration: 0.15 }}
                role="tab"
                aria-selected={isActive}
                aria-controls="main-content"
                tabIndex={isActive ? 0 : -1}
                onClick={() => handleTabClick(tab)}
                className={cn(
                  'group relative flex items-center gap-1.5 px-3 h-9 text-xs font-medium whitespace-nowrap',
                  'border-r border-[var(--border)] transition-colors flex-shrink-0 min-w-0 max-w-[180px]',
                  isActive
                    ? 'text-[var(--text-1)] bg-[var(--bg)]'
                    : 'text-[var(--text-3)] hover:text-[var(--text-2)] hover:bg-[var(--elevated)]',
                )}
              >
                {/* Active indicator */}
                {isActive && (
                  <motion.div
                    layoutId="tab-indicator"
                    className="absolute bottom-0 left-0 right-0 h-0.5 bg-cyan-500 rounded-t-full"
                    style={{ boxShadow: '0 0 6px rgba(14,165,233,0.5)' }}
                  />
                )}

                <Icon className={cn('w-3 h-3 flex-shrink-0', isActive ? 'text-cyan-400' : '')} aria-hidden="true" />

                <span className="truncate">{tab.title}</span>

                {dotColor && (
                  <span className={cn('w-1.5 h-1.5 rounded-full flex-shrink-0', dotColor)} aria-hidden="true" />
                )}

                {tab.closeable && (
                  <button
                    onClick={(e) => handleClose(e, tab)}
                    aria-label={`Close ${tab.title} tab`}
                    tabIndex={0}
                    className={cn(
                      'ml-0.5 p-0.5 rounded transition-all flex-shrink-0',
                      isActive
                        ? 'opacity-60 hover:opacity-100 hover:bg-[var(--border)]'
                        : 'opacity-0 group-hover:opacity-60 hover:!opacity-100 hover:bg-[var(--border)]',
                      'focus-visible:opacity-100',
                    )}
                  >
                    <X className="w-2.5 h-2.5" aria-hidden="true" />
                  </button>
                )}
              </motion.button>
            )
          })}
        </AnimatePresence>
      </div>

      {/* Scroll right */}
      {workspaceTabs.length > 4 && (
        <button
          onClick={scrollRight}
          aria-label="Scroll tabs right"
          className="px-1.5 text-[var(--text-4)] hover:text-[var(--text-2)] flex-shrink-0"
        >
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      )}

      {/* New tab button */}
      <button
        className="px-2 py-1 mx-1 text-[var(--text-4)] hover:text-[var(--text-2)] flex-shrink-0 rounded hover:bg-[var(--elevated)] transition-colors"
        aria-label="New tab"
      >
        <Plus className="w-3.5 h-3.5" aria-hidden="true" />
      </button>
    </div>
  )
}
