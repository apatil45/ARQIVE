/**
 * Authentication context for managing user state
 */
import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { useRouter } from 'next/router'
import { login as apiLogin, setAuthToken, getAuthToken, verifyToken } from '@/api/client'

interface User {
  username: string
  role: string
}

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const router = useRouter()

  // Check for existing token on mount
  useEffect(() => {
    const checkToken = async () => {
      const token = getAuthToken()
      if (token) {
        try {
          // First try backend verification (more secure)
          const verification = await verifyToken(token)
          if (verification.valid) {
            setUser({
              username: verification.username,
              role: verification.role,
            })
            setIsAuthenticated(true)
            return
          } else {
            // Token invalid, clear it
            setAuthToken(null)
            setIsAuthenticated(false)
            return
          }
        } catch (e) {
          // Backend verification failed, try client-side decode as fallback
          try {
            const tokenParts = token.split('.')
            if (tokenParts.length === 3) {
              const payload = JSON.parse(atob(tokenParts[1]))
              // Check if token is expired
              const exp = payload.exp
              if (exp && exp * 1000 > Date.now()) {
                // Token is valid, restore user session
                setUser({
                  username: payload.sub,
                  role: payload.role,
                })
                setIsAuthenticated(true)
              } else {
                // Token expired
                setAuthToken(null)
                setIsAuthenticated(false)
              }
            } else {
              setAuthToken(null)
              setIsAuthenticated(false)
            }
          } catch (decodeError) {
            // Invalid token
            setAuthToken(null)
            setIsAuthenticated(false)
          }
        }
      }
    }
    checkToken()
  }, [])

  const login = async (username: string, password: string) => {
    const response = await apiLogin(username, password)
    setAuthToken(response.access_token)
    
    // Verify token with backend to get user info (secure)
    try {
      const verification = await verifyToken(response.access_token)
      if (verification.valid) {
        setUser({
          username: verification.username,
          role: verification.role,
        })
        setIsAuthenticated(true)
      } else {
        throw new Error(verification.error || 'Token verification failed')
      }
    } catch (e: any) {
      // Fallback to client-side decoding if verification fails
      const tokenParts = response.access_token.split('.')
      if (tokenParts.length === 3) {
        try {
          const payload = JSON.parse(atob(tokenParts[1]))
          setUser({
            username: payload.sub,
            role: payload.role,
          })
          setIsAuthenticated(true)
        } catch (decodeError) {
          throw new Error('Failed to decode token')
        }
      } else {
        throw new Error('Invalid token format')
      }
    }
  }

  const logout = () => {
    setAuthToken(null)
    setUser(null)
    setIsAuthenticated(false)
    router.push('/login')
  }

  return (
    <AuthContext.Provider value={{ user, isAuthenticated, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}


