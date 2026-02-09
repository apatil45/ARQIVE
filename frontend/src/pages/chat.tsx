import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { useRouter } from 'next/router'
import { useAuth } from '@/context/AuthContext'
import { queryDocuments, getDocuments, getAuthToken } from '@/api/client'
import styles from '@/styles/Chat.module.css'

interface Message {
  role: 'user' | 'assistant'
  content: string
  citations?: Array<{
    chunk_index: number
    document_id: string
    filename: string
    reference: string
  }>
  sources?: string[]
  error?: boolean
}

// Memoized message component to prevent unnecessary re-renders
const MessageItem = React.memo(({ msg, idx }: { msg: Message; idx: number }) => (
  <div key={idx} className={styles[msg.role]}>
    <div className={styles.messageContent}>{msg.content}</div>
    {msg.sources && msg.sources.length > 0 && (
      <div className={styles.sources}>
        Sources: {msg.sources.join(', ')}
      </div>
    )}
  </div>
))

MessageItem.displayName = 'MessageItem'

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [documents, setDocuments] = useState<any[]>([])
  const [streamingText, setStreamingText] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const streamingTextRef = useRef<string>('')
  const { isAuthenticated, user, logout } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login')
      return
    }
    loadDocuments()
  }, [isAuthenticated, router])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const loadDocuments = useCallback(async () => {
    try {
      const docs = await getDocuments()
      setDocuments(docs.documents || [])
    } catch (error) {
      console.error('Failed to load documents:', error)
    }
  }, [])
  
  // Note: Debounced input removed as it was unused
  // Can be re-added if implementing search-as-you-type feature

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    // Cancel any ongoing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    const userMessage: Message = { role: 'user', content: input }
    const queryText = input.trim()
    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)
    setStreamingText('')
    streamingTextRef.current = ''

    // Create new abort controller
    abortControllerRef.current = new AbortController()

    try {
      // Try streaming first
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const token = getAuthToken()
      
      const response = await fetch(`${API_URL}/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: JSON.stringify({
          query: queryText,
          max_results: 5,
          stream: true,
        }),
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let citations: any[] = []
      let sources: string[] = []
      streamingTextRef.current = '' // Reset streaming text

      if (reader) {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.trim() === '') continue // Skip empty lines
            if (line.startsWith('data: ')) {
              try {
                const jsonStr = line.slice(6).trim()
                if (!jsonStr) continue
                const data = JSON.parse(jsonStr)
                
                if (data.type === 'metadata') {
                  citations = data.citations || []
                  sources = data.sources || []
                  console.log('Received metadata:', { citations, sources })
                } else if (data.type === 'token') {
                  if (data.text) {
                    streamingTextRef.current += data.text
                    setStreamingText(streamingTextRef.current)
                  }
                } else if (data.type === 'done') {
                  // Finalize message
                  const finalText = streamingTextRef.current + (data.text || '')
                  if (finalText.trim()) {
                    const assistantMessage: Message = {
                      role: 'assistant',
                      content: finalText,
                      citations,
                      sources,
                    }
                    setMessages((prev) => [...prev, assistantMessage])
                  }
                  setStreamingText('')
                  streamingTextRef.current = ''
                  setLoading(false)
                  return
                } else if (data.type === 'error') {
                  console.error('Streaming error:', data.text)
                  throw new Error(data.text || 'Streaming error')
                }
              } catch (e: any) {
                // Log error but continue processing
                if (e.name !== 'SyntaxError') {
                  console.error('SSE parsing error:', e, 'Line:', line)
                }
              }
            }
          }
        }
      }
    } catch (error: any) {
      if (error.name === 'AbortError') {
        return // Request was cancelled
      }
      
      console.error('Streaming error:', error)
      
      // Fallback to non-streaming
      try {
        setLoading(true)
        const response = await queryDocuments(queryText)
        const assistantMessage: Message = {
          role: 'assistant',
          content: response.answer,
          citations: response.citations,
          sources: response.sources,
        }
        setMessages((prev) => [...prev, assistantMessage])
      } catch (fallbackError: any) {
        console.error('Fallback error:', fallbackError)
        const errorMessage: Message = {
          role: 'assistant',
          content: `Error: ${fallbackError.message || error.message || 'Failed to get response'}. Please check:\n- Backend is running\n- Ollama is running (if using RAG queries)\n- Network connection is stable`,
          error: true,
        }
        setMessages((prev) => [...prev, errorMessage])
      }
    } finally {
      setLoading(false)
      setStreamingText('')
      streamingTextRef.current = ''
      abortControllerRef.current = null
    }
  }, [input, loading])

  if (!isAuthenticated) {
    return null
  }

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1>ARQIVE Chat</h1>
        <div className={styles.headerActions}>
          <span className={styles.userInfo}>{user?.username} ({user?.role})</span>
          <button onClick={() => router.push('/upload')} className={styles.button}>
            Upload
          </button>
          <button onClick={() => router.push('/documents')} className={styles.button}>
            Documents
          </button>
          {user?.role === 'admin' && (
            <button onClick={() => router.push('/admin')} className={styles.button}>
              Admin
            </button>
          )}
          <button onClick={logout} className={styles.button}>
            Logout
          </button>
        </div>
      </header>

      <div className={styles.chatContainer}>
        <div className={styles.messages}>
          {messages.length === 0 && (
            <div className={styles.welcome}>
              <h2>Welcome to ARQIVE</h2>
              <p>Ask questions about your documents. {documents.length} document(s) available.</p>
            </div>
          )}
          {messages.map((msg, idx) => (
            <MessageItem key={idx} msg={msg} idx={idx} />
          ))}
          {loading && (
            <div className={styles.assistant}>
              <div className={styles.messageContent}>
                {streamingText || 'Thinking...'}
              </div>
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} className={styles.inputForm}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about your documents..."
            className={styles.input}
            disabled={loading}
          />
          <button type="submit" disabled={loading || !input.trim()} className={styles.sendButton}>
            Send
          </button>
        </form>
      </div>
    </div>
  )
}


