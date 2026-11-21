import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import Badge from '../components/Badge'
import Loader from '../components/Loader'
import StatusControls from '../components/StatusControls'
import { fmtTime, nice } from '../format'
import { usePolling } from '../hooks'
import { RECOVERY_STATUSES } from '../reasons'

function NewReport({ onCreated }) {
  const empty = { plate_no: '', report_type: 'STOLEN', fir_ref: '', reported_place: '' }
  const [form, setForm] = useState(empty)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const field = (key) => ({
    value: form[key],
    onChange: (e) => setForm({ ...form, [key]: e.target.value }),
  })

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.createReport({ ...form, plate_no: form.plate_no.replace(/[^a-z0-9]/gi, '') })
      setForm(empty)
      onCreated()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card filters" onSubmit={submit}>
      <label>
        Plate (must be in the registry)
        <input {...field('plate_no')} maxLength={12} required />
      </label>
      <label>
        Type
        <select {...field('report_type')}>
          <option value="STOLEN">Stolen</option>
          <option value="MISSING">Missing</option>
        </select>
      </label>
      <label>
        FIR reference
        <input {...field('fir_ref')} maxLength={50} required />
      </label>
      <label>
        Reported at (place)
        <input {...field('reported_place')} maxLength={200} required />
      </label>
      <button type="submit" disabled={busy}>
        {busy ? 'Saving…' : 'File report'}
      </button>
      {error && <p className="error full">{error}</p>}
    </form>
  )
}

function Detail({ id, canChange, onChanged }) {
  const { data: r, reload } = usePolling(() => api.report(id), 0, [id])
  if (!r) return <Loader size="md" label="Loading case" />
  return (
    <div className="two-col">
      <div>
        <h3>Change status</h3>
        {canChange ? (
          <StatusControls
            withLocation
            allowed={r.allowed_next}
            onSubmit={async (status, note, location) => {
              await api.setReportStatus(r.report_id, status, note, location)
              await reload()
              onChanged()
            }}
          />
        ) : (
          <p className="muted">Only police officers can change the status of a case.</p>
        )}
      </div>
      <div>
        <h3>History</h3>
        {r.history.length === 0 && <p className="muted">No changes yet.</p>}
        <ol className="history">
          {r.history.map((h) => (
            <li key={h.ts}>
              <Badge value={h.to} /> <span className="muted">{fmtTime(h.ts)}</span>
              {h.location && <span className="muted"> · {h.location}</span>}
              <div>{h.note}</div>
            </li>
          ))}
        </ol>
      </div>
    </div>
  )
}

export default function Reports() {
  const { can } = useAuth()
  const [status, setStatus] = useState('')
  const [open, setOpen] = useState(null)
  const reports = usePolling(() => api.reports({ status, limit: 100 }), 10000, [status])
  const stats = usePolling(api.reportStats, 10000)

  return (
    <>
      <h1>Stolen and missing vehicles</h1>
      {stats.data && (
        <section className="stats">
          {RECOVERY_STATUSES.map((s) => (
            <div key={s} className="stat">
              <div className="stat-value">{stats.data.by_status[s] ?? 0}</div>
              <div className="stat-label">{nice(s)}</div>
            </div>
          ))}
          <div className="stat">
            <div className="stat-value">
              {stats.data.median_hours_to_detection == null ? '-' : `${stats.data.median_hours_to_detection} h`}
            </div>
            <div className="stat-label">Typical time to detection</div>
          </div>
        </section>
      )}

      {can('CREATE_REPORT') && <NewReport onCreated={() => { reports.reload(); stats.reload() }} />}

      <section className="card">
        <div className="chips">
          {['', ...RECOVERY_STATUSES].map((s) => (
            <button key={s || 'all'} className={status === s ? 'chip on' : 'chip'} onClick={() => setStatus(s)}>
              {s ? nice(s) : 'All'}
            </button>
          ))}
        </div>
        {reports.error && <p className="banner">{reports.error.message}</p>}
        {reports.loading && !reports.data && <Loader size="md" label="Loading cases" />}
        {reports.data?.length === 0 && <p className="muted">No reports in this state.</p>}
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Plate</th>
                <th>Type</th>
                <th>FIR</th>
                <th>Place</th>
                <th>Status</th>
                <th>Reported</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {(reports.data || []).flatMap((r) => [
                <tr key={r.report_id}>
                  <td>
                    <Link className="plate" to={`/plates/${r.plate_no}`}>
                      {r.plate_no}
                    </Link>
                  </td>
                  <td>{nice(r.report_type)}</td>
                  <td>{r.fir_ref}</td>
                  <td>{r.reported_place}</td>
                  <td>
                    <Badge value={r.recovery_status} />
                  </td>
                  <td>{fmtTime(r.reported_at)}</td>
                  <td>
                    <button className="secondary" onClick={() => setOpen(open === r.report_id ? null : r.report_id)}>
                      {open === r.report_id ? 'Close' : 'Open'}
                    </button>
                  </td>
                </tr>,
                open === r.report_id && (
                  <tr key={`${r.report_id}-detail`} className="detail-row">
                    <td colSpan={7}>
                      <Detail
                        id={r.report_id}
                        canChange={can('CHANGE_RECOVERY_STATUS')}
                        onChanged={() => { reports.reload(); stats.reload() }}
                      />
                    </td>
                  </tr>
                ),
              ])}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}
