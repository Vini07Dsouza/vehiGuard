import { useEffect, useRef } from 'react'

// A small dot with a thin ring that trails it, as on cosmicenterprises.co.
// The ring grows over anything clickable and shrinks while pressed. Over text
// fields the normal text cursor is used instead. Only for devices with a real
// mouse; touch screens never see it.
const CLICKABLE = 'a, button, [role="button"], summary, label, .chip, tbody tr'
const TEXT_FIELD = 'input, textarea, select, [contenteditable="true"]'

export default function CustomCursor() {
  const dot = useRef(null)
  const ring = useRef(null)

  useEffect(() => {
    if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) return undefined
    const root = document.documentElement
    root.classList.add('has-cursor')
    const target = { x: -100, y: -100 }
    const pos = { x: -100, y: -100 }
    let ringScale = 1
    let wantScale = 1
    let dotScale = 1
    let raf = 0

    const setVisible = (on) => root.classList.toggle('cursor-visible', on)
    const onMove = (e) => {
      target.x = e.clientX
      target.y = e.clientY
      const el = e.target instanceof Element ? e.target : null
      const typing = Boolean(el?.closest(TEXT_FIELD))
      setVisible(!typing)
      wantScale = el?.closest(CLICKABLE) ? 1.7 : 1
      dotScale = wantScale > 1 ? 0.5 : 1
    }
    const onDown = () => {
      wantScale = 0.75
    }
    const onUp = () => {
      wantScale = 1
    }
    const onLeave = () => setVisible(false)

    const frame = () => {
      pos.x += (target.x - pos.x) * 0.18
      pos.y += (target.y - pos.y) * 0.18
      ringScale += (wantScale - ringScale) * 0.14
      if (dot.current) {
        // the dot sticks to the pointer; only the ring lags behind
        dot.current.style.transform = `translate3d(${target.x}px, ${target.y}px, 0) scale(${dotScale})`
      }
      if (ring.current) {
        ring.current.style.transform = `translate3d(${pos.x}px, ${pos.y}px, 0) scale(${ringScale})`
      }
      raf = requestAnimationFrame(frame)
    }

    window.addEventListener('pointermove', onMove, { passive: true })
    window.addEventListener('pointerdown', onDown)
    window.addEventListener('pointerup', onUp)
    document.addEventListener('mouseleave', onLeave)
    raf = requestAnimationFrame(frame)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerdown', onDown)
      window.removeEventListener('pointerup', onUp)
      document.removeEventListener('mouseleave', onLeave)
      root.classList.remove('has-cursor', 'cursor-visible')
    }
  }, [])

  return (
    <>
      <div ref={ring} className="cursor-ring" aria-hidden="true" />
      <div ref={dot} className="cursor-dot" aria-hidden="true" />
    </>
  )
}
