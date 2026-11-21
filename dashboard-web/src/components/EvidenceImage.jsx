import { useEffect, useState } from 'react'
import { api } from '../api'
import Loader from './Loader'

// Evidence is only served to signed-in users, so the image is fetched with the
// token and shown from memory (an <img src> cannot send the token).
export default function EvidenceImage({ item, label }) {
  const [src, setSrc] = useState(null)
  const [problem, setProblem] = useState(null)
  const id = item?.evidence_id
  const purged = item?.purged

  useEffect(() => {
    if (!id || purged) return undefined
    let url = null
    let cancelled = false
    api
      .evidenceImage(id)
      .then((blob) => {
        if (cancelled) return
        url = URL.createObjectURL(blob)
        setSrc(url)
      })
      .catch((e) => !cancelled && setProblem(e.status === 410 ? 'Removed (retention)' : 'Not available'))
    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [id, purged])

  let body
  if (!item) body = <div className="evidence-empty">No image</div>
  else if (purged || problem) body = <div className="evidence-empty">{purged ? 'Removed (retention)' : problem}</div>
  else if (!src) {
    body = (
      <div className="evidence-empty">
        <Loader size="sm" label="Loading image" />
      </div>
    )
  }
  else body = <img src={src} alt={label} />
  return (
    <figure className="evidence">
      {body}
      <figcaption>{label}</figcaption>
    </figure>
  )
}
