import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, getToken, setToken, setUnauthorizedHandler } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(Boolean(getToken()))

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(logout) // an expired token signs the user out
    if (!getToken()) return
    api
      .me()
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setLoading(false))
  }, [logout])

  const login = useCallback(async (username, password) => {
    const reply = await api.login(username, password)
    setToken(reply.access_token)
    setUser(await api.me())
  }, [])

  const value = useMemo(
    () => ({
      user,
      loading,
      login,
      logout,
      // the server decides what each role may do; the screens only follow it
      can: (permission) => Boolean(user?.permissions?.includes(permission)),
    }),
    [user, loading, login, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}
