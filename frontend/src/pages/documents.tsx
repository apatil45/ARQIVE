import { useState, useEffect } from 'react'
import { useRouter } from 'next/router'
import { useAuth } from '@/context/AuthContext'
import { getDocuments } from '@/api/client'
import styles from '@/styles/Documents.module.css'

export default function Documents() {
  const [documents, setDocuments] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const { isAuthenticated } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login')
      return
    }
    loadDocuments()
  }, [isAuthenticated, router])

  const loadDocuments = async () => {
    try {
      setLoading(true)
      const result = await getDocuments()
      setDocuments(result.documents || [])
    } catch (error) {
      console.error('Failed to load documents:', error)
    } finally {
      setLoading(false)
    }
  }

  if (!isAuthenticated) {
    return null
  }

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1>Documents</h1>
        <button onClick={() => router.push('/chat')} className={styles.button}>
          Back to Chat
        </button>
      </header>

      <div className={styles.documentsList}>
        {loading ? (
          <p>Loading documents...</p>
        ) : documents.length === 0 ? (
          <p>No documents uploaded yet.</p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Filename</th>
                <th>Type</th>
                <th>Uploaded By</th>
                <th>Uploaded At</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id}>
                  <td>{doc.filename}</td>
                  <td>{doc.file_type}</td>
                  <td>{doc.uploaded_by}</td>
                  <td>{new Date(doc.uploaded_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}


