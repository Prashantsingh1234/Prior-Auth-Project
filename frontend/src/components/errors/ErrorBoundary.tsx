import React from 'react'

type FallbackRender = (error: Error, reset: () => void) => React.ReactNode

interface Props {
  children:  React.ReactNode
  fallback?: React.ReactNode | FallbackRender
  onError?:  (error: Error, info: React.ErrorInfo) => void
}

interface State { error: Error | null }

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    this.props.onError?.(error, info)
    // eslint-disable-next-line no-console
    if ((import.meta as any).env?.DEV) console.error('[ErrorBoundary]', error, info)
  }

  reset = () => this.setState({ error: null })

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    const { fallback } = this.props
    if (typeof fallback === 'function') return (fallback as FallbackRender)(error, this.reset)
    if (fallback) return fallback
    return <DefaultFallback error={error} reset={this.reset} />
  }
}

// ─── Minimal default (consumers should supply their own) ──────────────────────

function DefaultFallback({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 p-8 text-center">
      <p className="text-sm font-semibold text-[var(--text-1)]">Something went wrong</p>
      <p className="text-xs text-[var(--text-3)] max-w-sm">{error.message}</p>
      <button
        onClick={reset}
        className="text-xs text-cyan-400 hover:text-cyan-300 underline underline-offset-2"
      >
        Try again
      </button>
    </div>
  )
}
