export function fmtTime(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString(undefined, {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function ago(iso) {
  if (!iso) return '-'
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000))
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return `${Math.floor(s / 86400)} d ago`
}

// "STOLEN_VEHICLE" -> "Stolen vehicle"
export function nice(code) {
  if (!code) return '-'
  const text = String(code).toLowerCase().replaceAll('_', ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export function duration(seconds) {
  if (seconds == null) return '-'
  if (seconds < 1) return 'under a second'
  if (seconds < 90) return `${Math.round(seconds)} seconds`
  if (seconds < 5400) return `${(seconds / 60).toFixed(1)} minutes`
  return `${(seconds / 3600).toFixed(1)} hours`
}
