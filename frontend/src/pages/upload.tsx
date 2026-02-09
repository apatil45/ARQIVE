import { useState } from 'react'
import { useRouter } from 'next/router'
import { useAuth } from '@/context/AuthContext'
import { uploadDocument } from '@/api/client'
import styles from '@/styles/Upload.module.css'

export default function Upload() {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const { isAuthenticated } = useAuth()
  const router = useRouter()

  if (!isAuthenticated) {
    router.push('/login')
    return null
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0]
      const fileSizeMB = selectedFile.size / 1024 / 1024
      const maxSizeMB = 50 // Should match backend MAX_FILE_SIZE_MB
      
      // Validate file type
      const allowedTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain']
      if (!allowedTypes.includes(selectedFile.type)) {
        setError('Invalid file type. Please select a PDF, DOCX, or TXT file.')
        setFile(null)
        return
      }
      
      // Validate file size
      if (fileSizeMB > maxSizeMB) {
        setError(`File size (${fileSizeMB.toFixed(2)}MB) exceeds maximum allowed size of ${maxSizeMB}MB`)
        setFile(null)
        return
      }
      
      setFile(selectedFile)
      setError('')
      setMessage('')
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) {
      setError('Please select a file')
      return
    }

    setUploading(true)
    setError('')
    setMessage('')

    try {
      const result = await uploadDocument(file)
      setMessage(`Document "${result.filename}" uploaded successfully!`)
      setFile(null)
      // Reset file input
      const fileInput = document.getElementById('file-input') as HTMLInputElement
      if (fileInput) fileInput.value = ''
    } catch (err: any) {
      setError(err.message || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1>Upload Document</h1>
        <button onClick={() => router.push('/chat')} className={styles.button}>
          Back to Chat
        </button>
      </header>

      <div className={styles.uploadBox}>
        <form onSubmit={handleSubmit}>
          <div className={styles.formGroup}>
            <label htmlFor="file-input">Select Document (PDF, DOCX, TXT)</label>
            <input
              id="file-input"
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={handleFileChange}
              disabled={uploading}
            />
            {file && (
              <p className={styles.fileInfo}>
                Selected: {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB)
              </p>
            )}
          </div>

          {error && <div className={styles.error}>{error}</div>}
          {message && <div className={styles.success}>{message}</div>}

          <button
            type="submit"
            disabled={!file || uploading}
            className={styles.submitButton}
          >
            {uploading ? 'Uploading...' : 'Upload Document'}
          </button>
        </form>
      </div>
    </div>
  )
}


