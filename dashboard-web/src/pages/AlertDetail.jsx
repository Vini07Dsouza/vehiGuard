import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import Badge from '../components/Badge'
import EvidenceImage from '../components/EvidenceImage'
import JourneyMap from '../components/JourneyMap'
import Loader from '../components/Loader'
import StatusControls from '../components/StatusControls'
import { duration, fmtTime, nice } from '../format'
import { usePolling } from '../hooks'
import { HEADLINES, reasonText } from '../reasons'

const pick = (list, kind) => (list || []).find((e) => e.kind === kind)
const UNCLEAR = ['UNKNOWN', 'OTHER']
const differs = (a, b) => a && b && !UNCLEAR.includes(a) && !UNCLEAR.includes(b) && a !== b

// A speed above what any road vehicle can reach reads better as a plain statement.
function speedText(kmh) {
  if (!kmh) return 'That needs no time at all'
  if (kmh > 1000) return 'That is faster than any road vehicle can travel'
  return `That needs about ${Math.round(kmh)} km/h`
}

function EvidencePair({ title, subtitle, evidence }) {
  return (
    <div className="evidence-set">
      <h3>{title}</h3>
      <p className="muted">{subtitle}</p>
      <div className="evidence-pair">
        <EvidenceImage item={pick(evidence, 'VEHICLE_FRAME')} label="Vehicle" />
        <EvidenceImage item={pick(evidence, 'PLATE_CROP')} label="Plate" />
      </div>
    </div>
  )
}

function Looks({ a }) {
  // registry / earlier sighting / this sighting, with differences marked
  const rows = [
    ['Registry', a.registry],
    ['Earlier sighting', a.earlier_sighting],
    ['This sighting', { vehicle_type: a.vehicle_type, colour_family: a.colour_family }],
  ].filter(([, v]) => v)
  const now = { vehicle_type: a.vehicle_type, colour_family: a.colour_family }
  return (
    <table>
      <thead>
        <tr>
          <th />
          <th>Type</th>
          <th>Colour</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([label, v]) => (
          <tr key={label}>
            <td>{label}</td>
            <td className={label !== 'This sighting' && differs(v.vehicle_type, now.vehicle_type) ? 'diff' : ''}>
              {nice(v.vehicle_type)}
            </td>
            <td className={label !== 'This sighting' && differs(v.colour_family, now.colour_family) ? 'diff' : ''}>
              {nice(v.colour_family)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function AlertDetail() {
  const { id } = useParams()
  const { can } = useAuth()
  const { data: a, error, reload } = usePolling(() => api.alert(id), 10000, [id])

  if (error && !a) {
    return (
      <>
        <p className="banner">{error.status === 404 ? 'This alert does not exist.' : error.message}</p>
        <Link to="/alerts">Back to alerts</Link>
      </>
    )
  }
  if (!a) return <Loader size="md" label="Loading alert" />

  const j = a.journey
  const earlier = a.earlier_sighting
  const points = [
    ...(earlier ? [{ lat: earlier.camera.lat, lon: earlier.camera.lon, label: earlier.camera.name }] : []),
    { lat: a.camera.lat, lon: a.camera.lon, label: a.camera.name },
  ]

  return (
    <>
      <p>
        <Link to="/alerts">← Alerts</Link>
      </p>
      <header className="detail-head">
        <div>
          <h1>{HEADLINES[a.type] || nice(a.type)}</h1>
          <p>
            <Link className="plate big" to={`/plates/${a.plate}`}>
              {a.plate}
            </Link>{' '}
            seen at {a.camera.name} · {fmtTime(a.observed_at)}
          </p>
        </div>
        <div className="badges">
          <Badge value={a.severity} />
          <Badge value={a.status} />
        </div>
      </header>
      <p className="muted">
        This alert is a lead, not a verdict. Check the evidence before acting.
        {a.merged_count > 1 && ` The vehicle was seen ${a.merged_count} times; repeats are merged here.`}
      </p>

      <section className="card">
        <h2>Why this alert was raised</h2>
        <ul>
          {a.reason_codes.map((code) => (
            <li key={code}>{reasonText(code)}</li>
          ))}
        </ul>
        {j && (
          <p className="journey-text">
            <strong>
              {j.from_camera} → {j.to_camera}:
            </strong>{' '}
            {j.distance_km.toFixed(1)} km in {duration(j.gap_s)}.{' '}
            {speedText(j.required_speed_kmh)}
            ; in that time a vehicle could cover at most {j.limit_km.toFixed(2)} km.
          </p>
        )}
      </section>

      <div className="two-col">
        <section className="card">
          <h2>{j ? 'Journey' : 'Where it was seen'}</h2>
          <JourneyMap points={points} impossible={Boolean(j?.impossible)} />
        </section>
        <section className="card">
          <h2>What the vehicle looks like</h2>
          <Looks a={a} />
          <p className="muted">
            Plate read with {a.scores?.plate_confidence == null ? '-' : Math.round(a.scores.plate_confidence * 100)}%
            confidence. Differences are marked; an unclear colour or type is never counted as a difference.
          </p>
          {a.report && (
            <p>
              Linked case: {nice(a.report.type)} report <strong>{a.report.fir_ref}</strong>, now{' '}
              <Badge value={a.report.status} />
            </p>
          )}
        </section>
      </div>

      <section className="card">
        <h2>Evidence</h2>
        <div className={earlier ? 'two-col' : ''}>
          {earlier && (
            <EvidencePair
              title="Earlier sighting"
              subtitle={`${earlier.camera.name} · ${fmtTime(earlier.observed_at)}`}
              evidence={earlier.evidence}
            />
          )}
          <EvidencePair
            title={earlier ? 'This sighting' : 'Sighting'}
            subtitle={`${a.camera.name} · ${fmtTime(a.observed_at)}`}
            evidence={a.evidence}
          />
        </div>
      </section>

      <div className="two-col">
        <section className="card">
          <h2>Status</h2>
          {can('CHANGE_ALERT_STATUS') ? (
            <StatusControls
              allowed={a.allowed_next_statuses}
              onSubmit={async (status, note) => {
                await api.setAlertStatus(a.alert_id, status, note)
                await reload()
              }}
            />
          ) : (
            <p className="muted">Only police officers can change the status of an alert.</p>
          )}
        </section>
        <section className="card">
          <h2>History</h2>
          {a.history.length === 0 && <p className="muted">No changes yet.</p>}
          <ol className="history">
            {a.history.map((h) => (
              <li key={h.ts}>
                <Badge value={h.to} /> <span className="muted">{fmtTime(h.ts)}</span>
                <div>{h.note}</div>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </>
  )
}
