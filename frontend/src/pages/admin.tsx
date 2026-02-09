import { useState, useEffect } from 'react'
import { useRouter } from 'next/router'
import { useAuth } from '@/context/AuthContext'
import { getUsers } from '@/api/client'
import styles from '@/styles/Admin.module.css'

export default function Admin() {
  const [users, setUsers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const { isAuthenticated, user } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!isAuthenticated || user?.role !== 'admin') {
      router.push('/chat')
      return
    }
    loadUsers()
  }, [isAuthenticated, user, router])

  const loadUsers = async () => {
    try {
      setLoading(true)
      const result = await getUsers()
      setUsers(result.users || [])
    } catch (error) {
      console.error('Failed to load users:', error)
    } finally {
      setLoading(false)
    }
  }

  if (!isAuthenticated || user?.role !== 'admin') {
    return null
  }

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1>Admin Dashboard</h1>
        <button onClick={() => router.push('/chat')} className={styles.button}>
          Back to Chat
        </button>
      </header>

      <div className={styles.content}>
        <h2>Users</h2>
        {loading ? (
          <p>Loading users...</p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Username</th>
                <th>Role</th>
                <th>Email</th>
                <th>Full Name</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.username}>
                  <td>{u.username}</td>
                  <td>{u.role}</td>
                  <td>{u.email || '-'}</td>
                  <td>{u.full_name || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}


