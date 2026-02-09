/**
 * API client for ARQIVE backend
 */
import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Get token from localStorage (persists across page refreshes)
const TOKEN_KEY = 'arqive_auth_token'

export const setAuthToken = (token: string | null) => {
  if (typeof window !== 'undefined') {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token)
    } else {
      localStorage.removeItem(TOKEN_KEY)
    }
  }
  // Also keep in memory for immediate access
  authToken = token
}

// Keep in-memory cache for performance
let authToken: string | null = null

export const getAuthToken = (): string | null => {
  // Check memory first
  if (authToken) {
    return authToken
  }
  // Fallback to localStorage
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem(TOKEN_KEY)
    if (token) {
      authToken = token
      return token
    }
  }
  return null
}

// Axios instance with auth interceptor
const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add token to requests
apiClient.interceptors.request.use((config: any) => {
  if (authToken) {
    config.headers.Authorization = `Bearer ${authToken}`
  }
  return config
})

// Handle auth errors
apiClient.interceptors.response.use(
  (response: any) => response,
  (error: any) => {
    if (error.response?.status === 401) {
      // Token expired or invalid
      setAuthToken(null)
      if (typeof window !== 'undefined') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

// Auth endpoints
export const login = async (username: string, password: string) => {
  const formData = new URLSearchParams()
  formData.append('username', username)
  formData.append('password', password)
  
  const response = await axios.post(`${API_URL}/auth/login`, formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  })
  
  const token = response.data.access_token
  setAuthToken(token)
  return response.data
}

export const verifyToken = async (token: string) => {
  const formData = new URLSearchParams()
  formData.append('token', token)
  
  const response = await axios.post(`${API_URL}/auth/verify`, formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  })
  
  return response.data
}

// Document endpoints
export const uploadDocument = async (file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await apiClient.post('/documents/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  
  return response.data
}

export const getDocuments = async () => {
  const response = await apiClient.get('/documents/list')
  return response.data
}

// Query endpoint
export const queryDocuments = async (query: string, maxResults: number = 5) => {
  const response = await apiClient.post('/query', {
    query,
    max_results: maxResults,
  })
  return response.data
}

// Admin endpoints
export const getUsers = async () => {
  const response = await apiClient.get('/admin/users')
  return response.data
}

// Query history endpoints
export const getQueryHistory = async (limit: number = 50, skip: number = 0) => {
  const response = await apiClient.get('/query/history', {
    params: { limit, skip }
  })
  return response.data
}

export const deleteQueryHistory = async (historyId?: number) => {
  const response = await apiClient.delete('/query/history', {
    params: historyId ? { history_id: historyId } : {}
  })
  return response.data
}

// Document preview endpoint
export const getDocumentPreview = async (documentId: string, maxChunks: number = 5) => {
  const response = await apiClient.get(`/documents/${documentId}/preview`, {
    params: { max_chunks: maxChunks }
  })
  return response.data
}
