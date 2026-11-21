import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import Loader from '../components/Loader'
import PillButton from '../components/PillButton'
import Reveal from '../components/Reveal'
import SprinkleBackground from '../components/SprinkleBackground'

function Logo() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" aria-hidden="true">
      <defs>
        <linearGradient id="vg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#6ee7b7" />
          <stop offset="0.55" stopColor="#fde047" />
          <stop offset="1" stopColor="#f9a8d4" />
        </linearGradient>
      </defs>
      <path d="M12 2 4 5v6c0 5 3.4 9.3 8 11 4.6-1.7 8-6 8-11V5l-8-3Z" fill="url(#vg)" />
      <path d="m8.5 12 2.5 2.5 4.5-5" fill="none" stroke="#06130e" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

// The headline: every word rises out of its own mask, one after the other.
const HEADLINE = [
  ['Catch', ''],
  ['stolen', ''],
  ['and', ''],
  ['cloned', ''],
  ['vehicles', ''],
  ['before', 'w-yellow'],
  ['they', 'w-peach'],
  ['vanish', 'w-pink'],
]

const FEATURES = [
  {
    title: 'Reads every plate',
    text: 'Phone cameras and AI find the number plate, read it, and only accept a reading that several frames agree on.',
  },
  {
    title: 'Catches cloned plates',
    text: 'The same plate at two cameras too far apart for the time between them is flagged as a suspected clone, with both vehicles side by side.',
  },
  {
    title: 'Follows each case to recovery',
    text: 'Alerts reach the nearest station. Officers acknowledge, investigate and close them, and every step is kept in an audit trail.',
  },
]

export default function Login() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to={location.state?.from || '/monitor'} replace />

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(username.trim(), password)
      navigate(location.state?.from || '/monitor', { replace: true })
    } catch (e) {
      setError(
        e.status === 401
          ? 'Wrong username or password'
          : e.status === 502 || e.status === 0
            ? 'The VehiGuard server is not running. Start the backend, then try again.'
            : e.message,
      )
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <SprinkleBackground />
      <header className="auth-top">
        <span className="auth-brand">
          <Logo /> VehiGuard
        </span>
      </header>

      <main className="auth-hero">
        <p className="auth-eyebrow">Stolen and cloned vehicle detection</p>
        <h1 aria-label={HEADLINE.map(([w]) => w).join(' ')}>
          {HEADLINE.map(([word, tone], i) => (
            <span key={word} aria-hidden="true">
              <span className="word">
                <span className={`word-in ${tone}`} style={{ '--d': `${250 + i * 85}ms` }}>
                  {word}
                </span>
              </span>{' '}
            </span>
          ))}
        </h1>

        <form className="auth-card" onSubmit={submit}>
          <h2>Sign in</h2>
          <label>
            Username
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              required
            />
          </label>
          <label>
            Password
            <span className="pw">
              <input
                type={show ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
              <button type="button" className="ghost" onClick={() => setShow(!show)} aria-pressed={show}>
                {show ? 'Hide' : 'Show'}
              </button>
            </span>
          </label>
          {error && <p className="auth-error">{error}</p>}
          <PillButton type="submit" className="auth-submit" disabled={busy}>
            <span>
              {busy && <Loader size="sm" label="Signing in" />} {busy ? 'Signing in' : 'Sign in'}
            </span>
          </PillButton>
          <p className="auth-note">Accounts are created by an administrator.</p>
        </form>

        <a className="scroll-cue" href="#features">
          Scroll to begin
          <i />
        </a>
      </main>

      <section id="features" className="auth-features">
        {FEATURES.map((f, i) => (
          <Reveal as="article" key={f.title} delay={i * 130}>
            <h3>{f.title}</h3>
            <p>{f.text}</p>
          </Reveal>
        ))}
      </section>
      <footer className="auth-foot">VehiGuard · a final-year project prototype · all owners and cases shown are fictional</footer>
    </div>
  )
}
