import { useState } from 'react'
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import {
  Menu,
  X,
  Home,
  TrendingUp,
  Zap,
  Brain,
  ShoppingCart,
  Briefcase,
  BarChart3,
  Settings,
  LogOut,
} from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import EmergencyStopButton from './EmergencyStopButton'

const navItems = [
  { path: '/', label: '대시보드', icon: Home },
  { path: '/chart/BTC', label: '차트', icon: TrendingUp },
  { path: '/strategies', label: '전략', icon: Zap },
  { path: '/ai-advisor', label: 'AI 자문', icon: Brain },
  { path: '/orders', label: '주문', icon: ShoppingCart },
  { path: '/portfolio', label: '포트폴리오', icon: Briefcase },
  { path: '/backtest', label: '백테스트', icon: BarChart3 },
  { path: '/settings', label: '설정', icon: Settings },
]

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen bg-slate-950">
      {/* Sidebar */}
      <aside
        className={`${
          sidebarOpen ? 'w-64' : 'w-20'
        } bg-slate-900 border-r border-slate-800 transition-all duration-300 flex flex-col`}
      >
        {/* Logo */}
        <div className="h-16 flex items-center justify-between px-4 border-b border-slate-800">
          {sidebarOpen && (
            <h1 className="text-xl font-bold text-blue-400">CoinTrader</h1>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-1 hover:bg-slate-800 rounded"
          >
            {sidebarOpen ? (
              <X size={20} className="text-slate-400" />
            ) : (
              <Menu size={20} className="text-slate-400" />
            )}
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-6 space-y-2 overflow-y-auto">
          {navItems.map(({ path, label, icon: Icon }) => (
            <Link
              key={path}
              to={path}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                location.pathname === path
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-300 hover:bg-slate-800'
              }`}
              title={label}
            >
              <Icon size={20} />
              {sidebarOpen && <span>{label}</span>}
            </Link>
          ))}
        </nav>

        {/* User Section */}
        <div className="border-t border-slate-800 p-4 space-y-3">
          {sidebarOpen && user && (
            <div className="text-sm">
              <p className="text-slate-400">로그인 사용자</p>
              <p className="text-slate-100 font-medium truncate">{user.email}</p>
            </div>
          )}
          <button
            onClick={handleLogout}
            className={`flex items-center gap-3 w-full px-4 py-2 text-slate-300 hover:bg-slate-800 rounded-lg transition-colors ${
              !sidebarOpen && 'justify-center'
            }`}
            title="로그아웃"
          >
            <LogOut size={20} />
            {sidebarOpen && <span>로그아웃</span>}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="h-16 bg-slate-900 border-b border-slate-800 px-8 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-100">
            {navItems.find((item) => item.path === location.pathname)?.label ||
              ''}
          </h2>
          <EmergencyStopButton />
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
