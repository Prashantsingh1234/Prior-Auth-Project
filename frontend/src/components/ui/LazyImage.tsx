import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'

interface LazyImageProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  src:          string
  alt:          string
  placeholder?: string
}

export function LazyImage({ src, alt, placeholder = '', className, ...props }: LazyImageProps) {
  const ref                   = useRef<HTMLImageElement>(null)
  const [visible, setVisible] = useState(false)
  const [loaded,  setLoaded]  = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setVisible(true); obs.disconnect() } },
      { rootMargin: '200px' },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  return (
    <img
      ref={ref}
      src={visible ? src : placeholder}
      alt={alt}
      onLoad={() => setLoaded(true)}
      className={cn('transition-opacity duration-300', loaded ? 'opacity-100' : 'opacity-0', className)}
      {...props}
    />
  )
}
