interface LiveRegionProps {
  message:     string
  politeness?: 'polite' | 'assertive'
  atomic?:     boolean
}

export function LiveRegion({ message, politeness = 'polite', atomic = true }: LiveRegionProps) {
  return (
    <div role="status" aria-live={politeness} aria-atomic={atomic} className="sr-only">
      {message}
    </div>
  )
}
