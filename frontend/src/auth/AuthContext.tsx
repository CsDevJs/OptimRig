import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api, ApiError, setAuthToken } from '../api/client'
import type { User } from '../api/types'

interface AuthState {
  user: User | null
  /** True until a stored token has been checked against the server. */
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)
const TOKEN_KEY = 'pc-configurator-token'

function storedToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

function storeToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    // Storage blocked (private mode): the login still works for this tab.
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(() => storedToken() !== null)

  const logout = useCallback(() => {
    setAuthToken(null)
    storeToken(null)
    setUser(null)
  }, [])

  useEffect(() => {
    const token = storedToken()
    if (!token) return
    setAuthToken(token)
    api.me()
      .then(setUser)
      .catch((error) => {
        // Expired or invalid token: start logged out.
        if (error instanceof ApiError && error.status === 401) logout()
      })
      .finally(() => setLoading(false))
  }, [logout])

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await api.login(email, password)
    setAuthToken(access_token)
    storeToken(access_token)
    setUser(await api.me())
  }, [])

  const register = useCallback(async (email: string, password: string) => {
    await api.register(email, password)
    await login(email, password)
  }, [login])

  const value = useMemo(() => ({ user, loading, login, register, logout }), [user, loading, login, register, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
