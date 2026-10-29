import { useEffect } from 'react'

/** Feeds the mouse position to `.glow` elements (CSS vars --mouse-x/y) for the design's hover light. */
export function GlowTracker() {
  useEffect(() => {
    let frame = 0
    const onMove = (event: MouseEvent) => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const target = (event.target as Element | null)?.closest?.('.glow') as HTMLElement | null
        if (!target) return
        const rect = target.getBoundingClientRect()
        target.style.setProperty('--mouse-x', `${event.clientX - rect.left}px`)
        target.style.setProperty('--mouse-y', `${event.clientY - rect.top}px`)
      })
    }
    document.addEventListener('mousemove', onMove)
    return () => {
      document.removeEventListener('mousemove', onMove)
      cancelAnimationFrame(frame)
    }
  }, [])
  return null
}
