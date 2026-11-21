import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import Badge from '../components/Badge'
import EvidenceImage from '../components/EvidenceImage'
import JourneyMap from '../components/JourneyMap'
import { ago, fmtTime, nice } from '../format'
import { usePolling } from '../hooks'
import { HEADLINES } from '../reasons'

function Search({ initial = '' }) {
  const [value, setValue] = useState(initial)
  const navigate = useNavigate()
  return (
    <form
      className="filters card"
      onSubmit={(e) => {
        e.preventDefault()
        const plate = value.replace(/[^a-z0-9]/gi, '').toUpperCase()
        if (plate) navigate(`/plates/${plate}`)
      }}
    >
      <label>
        Plate number
        <input value={value} onChange={(e) => setValue(e.target.value)} placeholder="KA19AB1234" maxLength={15} autoFocus />
      </label>
      <button type="submit">Show timeline</button>
    </form>
  )
}

function Recent() {
  const { data } = usePolling(() => api.sightings({ limit: 200 }), 10000)
  const seen = new Map()
  for (const s of data || []) if (s.plate_no && !seen.has(s.plate_no)) seen.set(s.plate_no, s)
  return (
    <section className="card">
      <h2>Recently seen plates</h2>
      {seen.size === 0 && <p className="muted">Nothing yet.</p>}
      <table>
        <tbody>
          {[...seen.values()].map((s) => (
            <tr key={s.plate_no}>
              <td>
                <Link className="plate" to={`/plates/${s.plate_no}`}>
                  {s.plate_no}
                </Link>
              </td>
              <td>
                <Badge value={s.outcome} />
              </td>
              <td>{s.camera.name}</td>
              <td>{ago(s.observed_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function Timeline({ plate }) {
  const { can } = useAuth()
  const { data, error } = usePolling(() => api.timeline(plate), 15000, [plate])
  if (error && !data) return <p className="banner">{error.message}</p>
  if (!data) return <p className="muted">Loading…</p>

  const points = data.sightings.map((s) => ({ lat: s.camera.lat, lon: s.camera.lon, label: s.camera.name }))
  const flagged = data.alerts.length > 0 || data.reports.length > 0
  return (
    <>
      <h1 className="plate big">{data.plate_no}</h1>
      <div className="two-col">
        <section className="card">
          <h2>Registry</h2>
          {data.registry ? (
            <p>
              {nice(data.registry.colour_family)} {data.registry.make} {data.registry.model} ({nice(data.registry.vehicle_type)})
              <br />
              <span className="muted">Owner: {data.registry.owner_name}</span>
            </p>
          ) : (
            <p className="muted">This plate is not in the vehicle registry.</p>
          )}
          {flagged && (
            <>
              {data.reports.map((r) => (
                <p key={r.report_id}>
                  {nice(r.report_type)} report <strong>{r.fir_ref}</strong> <Badge value={r.recovery_status} />
                </p>
              ))}
              {data.alerts.map((a) => (
                <p key={a.alert_id}>
                  <Link to={`/alerts/${a.alert_id}`}>{HEADLINES[a.alert_type] || nice(a.alert_type)}</Link>{' '}
                  <Badge value={a.severity} /> <Badge value={a.status} />
                </p>
              ))}
            </>
          )}
        </section>
        <section className="card">
          <h2>Route</h2>
          {points.length === 0 ? (
            <p className="muted">No sightings of this plate.</p>
          ) : (
            <JourneyMap points={points} height={220} />
          )}
        </section>
      </div>

      <section className="card">
        <h2>Sightings across cameras ({data.sightings.length})</h2>
        <ol className="timeline">
          {data.sightings.map((s) => (
            <li key={s.sighting_id}>
              {can('VIEW_ALERTS') && (
                <div className="thumb">
                  <EvidenceImage item={s.evidence.find((e) => e.kind === 'PLATE_CROP')} label="" />
                </div>
              )}
              <div>
                <strong>{s.camera.name}</strong> <Badge value={s.outcome} />
                <div className="muted">
                  {fmtTime(s.observed_at)} · {nice(s.vehicle_type)}
                  {s.colour_family !== 'UNKNOWN' && `, ${nice(s.colour_family)}`}
                  {s.plate_conf != null && ` · ${Math.round(s.plate_conf * 100)}% confidence`}
                </div>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </>
  )
}

export default function Plates() {
  const { plate } = useParams()
  return (
    <>
      {!plate && <h1>Plate search</h1>}
      <Search key={plate || 'new'} initial={plate || ''} />
      {plate ? <Timeline plate={plate} /> : <Recent />}
    </>
  )
}
