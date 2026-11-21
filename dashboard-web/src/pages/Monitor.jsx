import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import Badge from '../components/Badge'
import { ago, fmtTime, nice } from '../format'
import { usePolling } from '../hooks'

function Stat({ label, value, tone, to }) {
  const body = (
    <div className={`stat ${tone || ''}`}>
      <div className="stat-value">{value ?? '-'}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
  return to ? <Link to={to}>{body}</Link> : body
}

export default function Monitor() {
  const { can } = useAuth()
  const health = usePolling(api.health, 5000)
  const cameras = usePolling(api.cameras, 5000)
  const sightings = usePolling(() => api.sightings({ limit: 30 }), 3000)
  const h = health.data
  const down = [health, cameras, sightings].find((x) => x.error)?.error

  return (
    <>
      <h1>Live monitor</h1>
      {down && <p className="banner">Connection problem: {down.message}. Retrying…</p>}

      <section className="stats">
        <Stat
          label="Cameras online"
          value={h && `${h.cameras_online} / ${h.cameras_total}`}
          tone={h && h.cameras_online < h.cameras_total ? 'warn' : ''}
        />
        <Stat
          label="Open alerts"
          value={h?.open_alerts}
          tone={h?.open_alerts ? 'danger' : ''}
          to={can('VIEW_ALERTS') ? '/alerts?status=NEW' : undefined}
        />
        <Stat label="Open cases" value={h?.open_cases} to={can('VIEW_REPORTS') ? '/reports' : undefined} />
        <Stat
          label="Alert emails waiting"
          value={h?.outbox_waiting}
          tone={h?.outbox_failed ? 'danger' : ''}
        />
        <Stat label="Last sighting" value={h?.last_sighting_at ? ago(h.last_sighting_at) : 'none yet'} />
        <Stat label="Alert mode" value={h && nice(h.alert_mode)} />
      </section>
      {h?.outbox_failed > 0 && (
        <p className="banner">{h.outbox_failed} alert email(s) failed to send. Check the mail settings.</p>
      )}

      <section className="card">
        <h2>Cameras</h2>
        <table>
          <thead>
            <tr>
              <th>Camera</th>
              <th>Station</th>
              <th>Source</th>
              <th>Status</th>
              <th>Last frame</th>
            </tr>
          </thead>
          <tbody>
            {(cameras.data || []).map((c) => (
              <tr key={c.camera_id}>
                <td>
                  {c.name} <span className="muted">({c.camera_id})</span>
                </td>
                <td>{c.station}</td>
                <td>{nice(c.source_type)}</td>
                <td>
                  <Badge value={c.state} />
                </td>
                <td>{c.last_frame_at ? ago(c.last_frame_at) : 'never'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2>Latest sightings</h2>
        {sightings.data?.length === 0 && <p className="muted">No sightings yet.</p>}
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Plate</th>
                <th>Result</th>
                <th>Camera</th>
                <th>Vehicle</th>
                <th>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {(sightings.data || []).map((s) => (
                <tr key={s.sighting_id}>
                  <td title={fmtTime(s.observed_at)}>{ago(s.observed_at)}</td>
                  <td>
                    {s.plate_no ? (
                      <Link className="plate" to={`/plates/${s.plate_no}`}>
                        {s.plate_no}
                      </Link>
                    ) : (
                      <span className="muted">no plate</span>
                    )}
                  </td>
                  <td>
                    <Badge value={s.outcome} />
                  </td>
                  <td>{s.camera.name}</td>
                  <td>
                    {nice(s.vehicle_type)}
                    {s.colour_family !== 'UNKNOWN' && <span className="muted">, {nice(s.colour_family)}</span>}
                  </td>
                  <td>{s.plate_conf == null ? '-' : `${Math.round(s.plate_conf * 100)}%`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}
