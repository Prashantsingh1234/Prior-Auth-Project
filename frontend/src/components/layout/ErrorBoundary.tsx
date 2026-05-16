import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

interface Props {
  children:  ReactNode
  fallback?: ReactNode
  onError?:  (error: Error, info: ErrorInfo) => void
}

interface State {
  hasError: boolean
  error:    Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', error, info)
    this.props.onError?.(error, info)
  }

  reset = () => this.setState({ hasError: false, error: null })

  render() {
    if (!this.state.hasError) return this.props.children
    if (this.props.fallback)  return this.props.fallback

    return (
      <div className="flex flex-col items-center justify-center min-h-64 p-8 text-center">
        <div className="w-14 h-14 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
          <AlertTriangle className="w-7 h-7 text-red-400" />
        </div>
        <h2 className="text-lg font-semibold text-[var(--text-1)]">Something went wrong</h2>
        <p className="text-sm text-[var(--text-3)] mt-1 max-w-sm">
          {this.state.error?.message ?? 'An unexpected error occurred in this section.'}
        </p>
        <button
          onClick={this.reset}
          className="btn btn-ghost mt-4 flex items-center gap-2 text-sm"
        >
          <RefreshCw className="w-4 h-4" /> Try again
        </button>
      </div>
    )
  }
}