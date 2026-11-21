import { useRef } from 'react'

// A thin-outlined pill. A soft light follows the pointer across it and the
// pill leans a few pixels towards the pointer ("magnetic").
export default function PillButton({ children, className = '', ...props }) {
  const ref = useRef(null)

  const onMove = (e) => {
    const el = ref.current
    if (!el || props.disabled) return
    const box = el.getBoundingClientRect()
    const x = e.clientX - box.left
    const y = e.clientY - box.top
    el.style.setProperty('--mx', `${x}px`)
    el.style.setProperty('--my', `${y}px`)
    el.style.transform = `translate(${((x - box.width / 2) / box.width) * 10}px, ${((y - box.height / 2) / box.height) * 8}px)`
  }
  const onLeave = () => {
    if (ref.current) ref.current.style.transform = ''
  }

  return (
    <button ref={ref} className={`pill ${className}`} onMouseMove={onMove} onMouseLeave={onLeave} {...props}>
      {children}
    </button>
  )
}
