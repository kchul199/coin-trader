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

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Layout />}>
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
