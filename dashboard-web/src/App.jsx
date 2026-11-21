import { lazy, Suspense } from 'react'
import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth'
import Loader from './components/Loader'
import Login from './pages/Login'

// Each page loads on demand, so opening one shows the badge until it is ready.
const Monitor = lazy(() => import('./pages/Monitor'))
const Alerts = lazy(() => import('./pages/Alerts'))
const AlertDetail = lazy(() => import('./pages/AlertDetail'))
const Plates = lazy(() => import('./pages/Plates'))
const Reports = lazy(() => import('./pages/Reports'))

// Menu entries: each shows only when the server says this role may use it.
const MENU = [
  { to: '/monitor', label: 'Live monitor', permission: 'VIEW_SIGHTINGS' },
  { to: '/alerts', label: 'Alerts', permission: 'VIEW_ALERTS' },
  { to: '/plates', label: 'Plates', permission: 'VIEW_SIGHTINGS' },
  { to: '/reports', label: 'Cases', permission: 'VIEW_REPORTS' },
]

function Shell({ children }) {
  const { user, logout, can } = useAuth()
  return (
    <>
      <header className="topbar">
        <strong className="brand">VehiGuard</strong>
        <nav>
          {MENU.filter((m) => can(m.permission)).map((m) => (
            <NavLink key={m.to} to={m.to} className={({ isActive }) => (isActive ? 'active' : '')}>
              {m.label}
            </NavLink>
          ))}
        </nav>
        <div className="who">
          {user.username} <span className="muted">({user.role.toLowerCase().replaceAll('_', ' ')})</span>
          <button className="secondary" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>
      <main className="page">{children}</main>
    </>
  )
}

// Signed-in users only, and only for pages their role may use.
function Guard({ permission, children }) {
  const { user, loading, can } = useAuth()
  const location = useLocation()
  if (loading) return <Loader label="Checking your session" />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  return (
    <Shell>
      {permission && !can(permission) ? (
        <p className="banner">Your role is not allowed to open this page.</p>
      ) : (
        <Suspense fallback={<Loader label="Loading page" />}>{children}</Suspense>
      )}
    </Shell>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/monitor" element={<Guard permission="VIEW_SIGHTINGS"><Monitor /></Guard>} />
      <Route path="/alerts" element={<Guard permission="VIEW_ALERTS"><Alerts /></Guard>} />
      <Route path="/alerts/:id" element={<Guard permission="VIEW_ALERTS"><AlertDetail /></Guard>} />
      <Route path="/plates" element={<Guard permission="VIEW_SIGHTINGS"><Plates /></Guard>} />
      <Route path="/plates/:plate" element={<Guard permission="VIEW_SIGHTINGS"><Plates /></Guard>} />
      <Route path="/reports" element={<Guard permission="VIEW_REPORTS"><Reports /></Guard>} />
      <Route path="*" element={<Navigate to="/monitor" replace />} />
    </Routes>
  )
}
