import { useEffect, useState } from 'react'

function StatusRow({ label, value }) {
  const ok = value === 'ok'
  return (
    <div className="row">
      <span>{label}</span>
      <span className={ok ? 'ok' : 'bad'}>{ok ? 'OK' : value}</span>
    </div>
  )
}

export default function App() {
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)

  const load = () =>
    fetch('/api/health')
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then(setHealth)
      .catch((err) => setError(err.message))

  const check = () => {
    setError(null)
    setHealth(null)
    load()
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <main>
      <h1>VehiGuard Console</h1>
      <p className="muted">Phase 0 skeleton: system status</p>
      <section className="card">
        {error && <StatusRow label="API" value={`not reachable (${error})`} />}
        {!error && !health && <p className="muted">Checking…</p>}
        {health && (
          <>
            <StatusRow label="API" value={health.api} />
            <StatusRow label="Database" value={health.database} />
          </>
        )}
        <button onClick={check}>Check again</button>
      </section>
    </main>
  )
}
