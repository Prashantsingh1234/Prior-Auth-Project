import { useEffect, useRef } from 'react'

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
  '[contenteditable="true"]',
].join(',')

function getFocusable(el: HTMLElement): HTMLElement[] {
  return Array.from(el.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (node) => !node.closest('[aria-hidden="true"]') && node.offsetParent !== null,
  )
}

export function useFocusTrap(
  containerRef: { current: HTMLElement | null },
  active: boolean,
): void {
  const savedFocus = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!active) return

    savedFocus.current = document.activeElement as HTMLElement

    const el = containerRef.current
    if (!el) return

    const t = setTimeout(() => {
      getFocusable(el)[0]?.focus()
    }, 50)

    function onKey(e: KeyboardEvent) {
      if (e.key !== 'Tab') return
      const elements = getFocusable(el!)
      if (elements.length === 0) { e.preventDefault(); return }
      const first = elements[0]
      const last  = elements[elements.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault(); last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault(); first.focus()
      }
    }

    document.addEventListener('keydown', onKey)
    return () => {
      clearTimeout(t)
      document.removeEventListener('keydown', onKey)
      savedFocus.current?.focus()
    }
  }, [active, containerRef])
}
