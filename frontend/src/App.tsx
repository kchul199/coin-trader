import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from '@/components/common/Layout'
import Dashboard from '@/pages/Dashboard'
import Login from '@/pages/Login'
import Chart from '@/pages/Chart'
import Strategies from '@/pages/Strategies'
import AiAdvisor from '@/pages/AiAdvisor'
import Orders from '@/pages/Orders'
import Portfolio from '@/pages/Portfolio'
import Backtest from '@/pages/Backtest'
import Settings from '@/pages/Settings'
import { useAuthStore } from '@/stores/authStore'

function ProtectedLayout() {
  const token = useAuthStore((state) => state.token)

  if (!token) {
    return <Navigate to="/login" replace />
  }

  return <Layout />
}

function PublicAuthPage() {
  const token = useAuthStore((state) => state.token)

  if (token) {
    return <Navigate to="/" replace />
  }

  return <Login />
}

export default function App() {
  const token = useAuthStore((state) => state.token)
  const user = useAuthStore((state) => state.user)
  const fetchMe = useAuthStore((state) => state.fetchMe)

  useEffect(() => {
    if (token && !user) {
      void fetchMe().catch((error) => {
        console.warn('Failed to hydrate user profile:', error)
      })
    }
  }, [fetchMe, token, user])

  return (
    <Routes>
      <Route path="/login" element={<PublicAuthPage />} />
      <Route path="/register" element={<PublicAuthPage />} />
      <Route element={<ProtectedLayout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/chart/:symbol" element={<Chart />} />
        <Route path="/strategies" element={<Strategies />} />
        <Route path="/ai-advisor" element={<AiAdvisor />} />
        <Route path="/orders" element={<Orders />} />
        <Route path="/portfolio" element={<Portfolio />} />
        <Route path="/backtest" element={<Backtest />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
