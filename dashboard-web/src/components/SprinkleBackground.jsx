import { useEffect, useRef } from 'react'

// A field of small coloured dashes arranged in a burst around the middle of
// the screen. It is driven ONLY by scrolling: nothing is shown while the page
// is still. When you scroll (or turn the wheel, or swipe) the dashes fade in
// and move with the scroll, near ones faster than far ones, and fly outwards
// with the scroll speed. A moment after you stop they fade away again.
// There is no idle drift and no mouse-following.

// Colour around the burst, by angle in degrees (0 = right, 90 = down):
// yellow, brown and pink, with a little cream and peach.
const STOPS = [
  [0, [250, 204, 21]],
  [45, [244, 114, 182]],
  [90, [196, 132, 72]],
  [125, [253, 224, 71]],
  [160, [236, 72, 153]],
  [200, [176, 112, 60]],
  [250, [254, 243, 199]],
  [300, [251, 164, 200]],
  [335, [251, 146, 60]],
  [360, [250, 204, 21]],
]
const NEUTRAL = [214, 200, 176]
const HOLD_MS = 450 // how long after the last scroll input the dashes stay

function colourAt(deg) {
  for (let i = 1; i < STOPS.length; i++) {
    const [d1, c1] = STOPS[i]
    if (deg <= d1) {
      const [d0, c0] = STOPS[i - 1]
      const k = (deg - d0) / (d1 - d0)
      return c0.map((v, j) => Math.round(v + (c1[j] - v) * k))
    }
  }
  return STOPS[0][1]
}

function makeParticles(count) {
  const list = []
  for (let i = 0; i < count; i++) {
    const a = Math.random() * Math.PI * 2
    const deg = (((a * 180) / Math.PI + (Math.random() - 0.5) * 30) % 360 + 360) % 360
    const rgb = Math.random() < 0.3 ? NEUTRAL : colourAt(deg)
    const alpha = 0.35 + Math.random() * 0.65
    list.push({
      a,
      u: Math.pow(Math.random(), 1.5), // more dashes near the inner ring
      z: 0.35 + Math.random() * 0.85, // depth: nearer dashes move more
      len: 6 + Math.random() * 8,
      w: 1.6 + Math.random() * 1.3,
      color: `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${alpha.toFixed(2)})`,
    })
  }
  return list
}

export default function SprinkleBackground() {
  const canvasRef = useRef(null)

  useEffect(() => {
    // Users who asked for less motion get no animation at all.
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return undefined

    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    let w = 0
    let h = 0
    let particles = []
    let visible = 0 // 0 = hidden, 1 = fully shown
    let energy = 0 // scroll speed: pushes the burst outwards
    let impulse = 0 // wheel turns, even when the page cannot scroll further
    let shift = 0 // smoothed scroll distance: the dashes move with this
    let lastScrollY = window.scrollY
    let lastInput = -Infinity
    let touchY = null
    let drawn = false
    let raf = 0
    let last = performance.now()

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      w = window.innerWidth
      h = window.innerHeight
      canvas.width = Math.round(w * dpr)
      canvas.height = Math.round(h * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.lineCap = 'round'
      const count = Math.max(260, Math.min(700, Math.round((w * h) / 2200)))
      particles = makeParticles(count)
    }

    const draw = () => {
      ctx.clearRect(0, 0, w, h)
      ctx.globalAlpha = visible
      const hole = Math.min(w, h) * 0.3
      const span = Math.hypot(w, h) * 0.55 - hole
      const cx = w * 0.5
      const cy = h * 0.46
      for (const p of particles) {
        const r = hole + span * p.u + energy * (30 + p.u * 170) * p.z
        const cos = Math.cos(p.a)
        const sin = Math.sin(p.a)
        const x = cx + cos * r
        const y = cy + sin * r - shift * 0.45 * p.z // moves with the scroll
        if (x < -20 || x > w + 20 || y < -20 || y > h + 20) continue
        const half = (p.len + energy * 8 * p.z) / 2
        ctx.strokeStyle = p.color
        ctx.lineWidth = p.w
        ctx.beginPath()
        ctx.moveTo(x - cos * half, y - sin * half)
        ctx.lineTo(x + cos * half, y + sin * half)
        ctx.stroke()
      }
      drawn = true
    }

    const frame = (now) => {
      const dt = Math.min(0.05, (now - last) / 1000)
      last = now
      const active = now - lastInput < HOLD_MS
      // appear quickly with the scroll, fade away gently after it stops
      visible += ((active ? 1 : 0) - visible) * Math.min(1, dt * (active ? 14 : 4))
      energy *= Math.exp(-dt * 3)
      impulse *= Math.exp(-dt * 2.5)
      shift += (window.scrollY + impulse - shift) * Math.min(1, dt * 10)
      if (visible > 0.01) draw()
      else if (drawn) {
        ctx.clearRect(0, 0, w, h)
        drawn = false
      }
      raf = requestAnimationFrame(frame)
    }

    const poke = (speed) => {
      lastInput = performance.now()
      energy = Math.min(2.2, energy + speed)
    }
    const onScroll = () => {
      const dy = window.scrollY - lastScrollY
      lastScrollY = window.scrollY
      poke(Math.abs(dy) * 0.006)
    }
    const onWheel = (e) => {
      impulse += Math.max(-400, Math.min(400, e.deltaY))
      poke(Math.abs(e.deltaY) * 0.004)
    }
    const onTouchStart = (e) => {
      touchY = e.touches[0].clientY
    }
    const onTouchMove = (e) => {
      const y = e.touches[0].clientY
      if (touchY != null) {
        impulse -= (y - touchY) * 2
        poke(Math.abs(y - touchY) * 0.01)
      }
      touchY = y
    }

    resize()
    window.addEventListener('resize', resize)
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('wheel', onWheel, { passive: true })
    window.addEventListener('touchstart', onTouchStart, { passive: true })
    window.addEventListener('touchmove', onTouchMove, { passive: true })
    raf = requestAnimationFrame(frame)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('wheel', onWheel)
      window.removeEventListener('touchstart', onTouchStart)
      window.removeEventListener('touchmove', onTouchMove)
    }
  }, [])

  return <canvas ref={canvasRef} className="sprinkles" aria-hidden="true" />
}
