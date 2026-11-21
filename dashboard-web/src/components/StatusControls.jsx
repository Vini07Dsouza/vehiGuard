import { useState } from 'react'
import { nice } from '../format'

// Move an alert or a report to its next status. A note is required for every
// change; the choices are only the moves the server allows from here.
export default function StatusControls({ allowed, onSubmit, withLocation = false }) {
  const [status, setStatus] = useState('')
  const [note, setNote] = useState('')
  const [location, setLocation] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  if (!allowed || allowed.length === 0) {
    return <p className="muted">This is final: no further status changes are possible.</p>
  }

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await onSubmit(status || allowed[0], note.trim(), location.trim())
      setStatus('')
      setNote('')
      setLocation('')
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="stack" onSubmit={submit}>
      <label>
        Move to
        <select value={status || allowed[0]} onChange={(e) => setStatus(e.target.value)}>
          {allowed.map((s) => (
            <option key={s} value={s}>
              {nice(s)}
            </option>
          ))}
        </select>
      </label>
      <label>
        Note (required)
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={1000}
          rows={2}
          required
          placeholder="What happened, or why you are changing the status"
        />
      </label>
      {withLocation && (
        <label>
          Location (optional)
          <input value={location} onChange={(e) => setLocation(e.target.value)} maxLength={200} />
        </label>
      )}
      {error && <p className="error">{error}</p>}
      <button type="submit" disabled={busy || !note.trim()}>
        {busy ? 'Saving…' : 'Save status change'}
      </button>
    </form>
  )
}
