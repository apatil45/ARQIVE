import { useEffect } from 'react'
import { useRouter } from 'next/router'
import { useAuth } from '@/context/AuthContext'

export default function Home() {
  const router = useRouter()
  const { isAuthenticated } = useAuth()

  useEffect(() => {
    if (isAuthenticated) {
      router.push('/chat')
    } else {
      router.push('/login')
    }
  }, [isAuthenticated, router])

  return <div>Loading...</div>
}


