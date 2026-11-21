import { useEffect } from 'react'
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

function FitTo({ points }) {
  const map = useMap()
  useEffect(() => {
    if (points.length === 1) map.setView(points[0], 14)
    else if (points.length > 1) map.fitBounds(points, { padding: [40, 40] })
  }, [map, points])
  return null
}

// Cameras as numbered dots; a line joins them in order (the journey).
// `points`: [{ lat, lon, label }]. `impossible` draws the line in red.
export default function JourneyMap({ points, impossible = false, height = 280 }) {
  const coords = points.map((p) => [p.lat, p.lon])
  return (
    <MapContainer
      className="map"
      style={{ height }}
      center={coords[0] || [12.97, 77.59]}
      zoom={12}
      scrollWheelZoom={false}
    >
      <TileLayer
        attribution="&copy; OpenStreetMap contributors"
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {coords.length > 1 && (
        <Polyline
          positions={coords}
          pathOptions={{ color: impossible ? '#b42318' : '#1d4ed8', dashArray: '8 6', weight: 4 }}
        />
      )}
      {points.map((p, i) => (
        <CircleMarker
          key={`${p.label}-${i}`}
          center={[p.lat, p.lon]}
          radius={9}
          pathOptions={{ color: '#fff', weight: 2, fillColor: '#1d4ed8', fillOpacity: 1 }}
        >
          <Tooltip permanent direction="top" offset={[0, -8]}>
            {points.length > 1 ? `${i + 1}. ` : ''}
            {p.label}
          </Tooltip>
        </CircleMarker>
      ))}
      <FitTo points={coords} />
    </MapContainer>
  )
}
