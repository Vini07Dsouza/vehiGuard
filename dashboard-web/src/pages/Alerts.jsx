import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import Badge from '../components/Badge'
import Loader from '../components/Loader'
import { ago, fmtTime, nice } from '../format'
import { usePolling } from '../hooks'
import { ALERT_STATUSES, ALERT_TYPES, HEADLINES, SEVERITIES } from '../reasons'

function Select({ label, value, onChange, options, render = nice }) {
  return (
    <label>
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">All</option>
        {options.map((o) => (
          <option key={o.value ?? o} value={o.value ?? o}>
            {o.label ?? render(o)}
          </option>
        ))}
      </select>
    </label>
  )
}

export default function Alerts() {
  const [params, setParams] = useSearchParams()
  const [plate, setPlate] = useState(params.get('plate') || '')
  const filters = {
    status: params.get('status') || '',
    alert_type: params.get('alert_type') || '',
    severity: params.get('severity') || '',
    station_id: params.get('station_id') || '',
    plate: params.get('plate') || '',
    since: params.get('since') || '',
  }
  const set = (key, value) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const stations = usePolling(api.cameras)
  const stationOptions = useMemo(() => {
    const seen = new Map()
    for (const c of stations.data || []) seen.set(c.station_id, c.station)
    return [...seen].map(([value, label]) => ({ value, label }))
  }, [stations.data])

  const alerts = usePolling(
    () => api.alerts({ ...filters, since: filters.since ? new Date(filters.since).toISOString() : '', limit: 100 }),
    10000,
    [JSON.stringify(filters)],
  )

  return (
    <>
      <h1>Alerts</h1>
      <form
        className="filters card"
        onSubmit={(e) => {
          e.preventDefault()
          set('plate', plate.trim())
        }}
      >
        <Select label="Status" value={filters.status} onChange={(v) => set('status', v)} options={ALERT_STATUSES} />
        <Select
          label="Type"
          value={filters.alert_type}
          onChange={(v) => set('alert_type', v)}
          options={ALERT_TYPES.map((t) => ({ value: t, label: HEADLINES[t] }))}
        />
        <Select label="Severity" value={filters.severity} onChange={(v) => set('severity', v)} options={SEVERITIES} />
        <Select label="Station" value={filters.station_id} onChange={(v) => set('station_id', v)} options={stationOptions} />
        <label>
          From date
          <input type="date" value={filters.since} onChange={(e) => set('since', e.target.value)} />
        </label>
        <label>
          Plate starts with
          <input value={plate} onChange={(e) => setPlate(e.target.value)} placeholder="KA19" maxLength={15} />
        </label>
        <button type="submit">Search</button>
        <button type="button" className="secondary" onClick={() => { setPlate(''); setParams({}, { replace: true }) }}>
          Clear
        </button>
      </form>

      {alerts.error && <p className="banner">{alerts.error.message}</p>}
      {alerts.loading && !alerts.data && <Loader size="md" label="Loading alerts" />}
      <section className="card">
        {alerts.data?.length === 0 && <p className="muted">No alerts match these filters.</p>}
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Severity</th>
                <th>Alert</th>
                <th>Plate</th>
                <th>Status</th>
                <th>Camera</th>
                <th>Station</th>
                <th>When</th>
              </tr>
            </thead>
            <tbody>
              {(alerts.data || []).map((a) => (
                <tr key={a.alert_id}>
                  <td>
                    <Badge value={a.severity} />
                  </td>
                  <td>
                    <Link to={`/alerts/${a.alert_id}`}>{HEADLINES[a.alert_type] || nice(a.alert_type)}</Link>
                    {a.merged_count > 1 && <span className="muted"> ×{a.merged_count}</span>}
                  </td>
                  <td className="plate">{a.plate_no}</td>
                  <td>
                    <Badge value={a.status} />
                  </td>
                  <td>{a.camera_name}</td>
                  <td>{a.station_name}</td>
                  <td title={fmtTime(a.created_at)}>{ago(a.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}
