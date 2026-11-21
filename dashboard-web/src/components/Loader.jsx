// The turning police badge, used whenever something is loading.
//   size="lg"  the whole screen (a page or the session check)
//   size="md"  a block inside a page (a list, a detail view)
//   size="sm"  a tiny inline badge (a button, an image slot)
// The look lives in public/loader.css, which index.html loads, so the same
// badge also shows before the app has started.

function Badge() {
  return (
    <div className="vg-badge" aria-hidden="true">
      <span className="vg-ring">
        <i />
      </span>
      <div className="vg-coin">
        <img className="vg-face vg-front" src="/badge-front.svg" alt="" draggable="false" />
        <img className="vg-face vg-back" src="/badge-back.svg" alt="" draggable="false" />
      </div>
    </div>
  )
}

export default function Loader({ label = 'Loading', size = 'lg' }) {
  if (size === 'sm') {
    return (
      <span className="vg-inline" role="status" aria-label={label}>
        <Badge />
      </span>
    )
  }
  const body = (
    <>
      <Badge />
      <p className="vg-label">
        {label}
        <span className="vg-dots" />
      </p>
    </>
  )
  if (size === 'md') {
    return (
      <div className="vg-block" role="status" aria-live="polite">
        {body}
      </div>
    )
  }
  return (
    <div className="vg-screen" role="status" aria-live="polite">
      {body}
    </div>
  )
}
