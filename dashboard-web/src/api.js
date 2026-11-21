// The only place that talks to the VehiGuard API (NFR-SEC-08).
// The sign-in token lives in sessionStorage: it is gone when the tab closes,
// and it is never put in a URL.

const TOKEN_KEY = 'vehiguard.token'

export function getToken() {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    /* storage blocked: the user simply signs in again */
  }
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

let onUnauthorized = () => {}
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

function errorMessage(body, fallback) {
  const detail = body?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((d) => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`).join('; ')
  }
  return fallback
}

function query(params) {
  const q = new URLSearchParams()
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== null && value !== '') q.set(key, value)
  }
  const text = q.toString()
  return text ? `?${text}` : ''
}

async function request(path, { method = 'GET', body, params, blob = false } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  let res
  try {
    res = await fetch(`/api/v1${path}${query(params)}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the VehiGuard server')
  }
  if (res.status === 401 && token) onUnauthorized()
  if (!res.ok) {
    let parsed = null
    try {
      parsed = await res.json()
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, errorMessage(parsed, `Request failed (${res.status})`))
  }
  return blob ? res.blob() : res.json()
}

export const api = {
  login: (username, password) =>
    request('/auth/login', { method: 'POST', body: { username, password } }),
  me: () => request('/me'),
  health: () => request('/system/health'),
  cameras: () => request('/cameras'),
  sightings: (params) => request('/sightings', { params }),
  timeline: (plate) => request(`/plates/${encodeURIComponent(plate)}/timeline`),
  alerts: (params) => request('/alerts', { params }),
  alert: (id) => request(`/alerts/${id}`),
  setAlertStatus: (id, status, note) =>
    request(`/alerts/${id}/status`, { method: 'POST', body: { status, note } }),
  reports: (params) => request('/reports', { params }),
  report: (id) => request(`/reports/${id}`),
  reportStats: () => request('/reports/stats'),
  createReport: (body) => request('/reports', { method: 'POST', body }),
  setReportStatus: (id, status, note, location) =>
    request(`/reports/${id}/status`, {
      method: 'POST',
      body: { status, note, location: location || null },
    }),
  evidenceImage: (id) => request(`/evidence/${id}/image`, { blob: true }),
}
