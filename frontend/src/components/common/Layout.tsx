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
  Bell,
  CheckCheck,
} from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { useNotificationStore } from '@/stores/notificationStore'
import { DEFAULT_CHART_SYMBOLS } from '@/utils/market'
import EmergencyStopButton from './EmergencyStopButton'

const navItems = [
  { path: '/', label: '대시보드', icon: Home },
  { path: `/chart/${DEFAULT_CHART_SYMBOLS[0]}`, label: '차트', icon: TrendingUp },
  { path: '/strategies', label: '전략', icon: Zap },
  { path: '/ai-advisor', label: 'AI 자문', icon: Brain },
  { path: '/orders', label: '주문', icon: ShoppingCart },
  { path: '/portfolio', label: '포트폴리오', icon: Briefcase },
  { path: '/backtest', label: '백테스트', icon: BarChart3 },
  { path: '/settings', label: '설정', icon: Settings },
]

function NotificationPanel() {
  const [open, setOpen] = useState(false)
  const { notifications, unreadCount, markAllRead, remove } = useNotificationStore()

  const TYPE_COLORS: Record<string, string> = {
    order_filled: 'border-emerald-600',
    order_created: 'border-blue-600',
    order_failed: 'border-red-600',
    emergency_stop: 'border-red-600',
    ai_advice: 'border-purple-600',
    error: 'border-red-600',
    info: 'border-gray-600',
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="relative p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
      >
        <Bell size={20} />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-[10px] rounded-full flex items-center justify-center font-bold">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-10 z-50 w-80 bg-gray-900 border border-gray-700 rounded-xl shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
              <span className="text-sm font-semibold text-white">알림</span>
              {unreadCount > 0 && (
                <button onClick={markAllRead} className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300">
                  <CheckCheck size={12} />
                  모두 읽음
                </button>
              )}
            </div>
            <div className="max-h-80 overflow-y-auto">
              {notifications.length === 0 ? (
                <div className="px-4 py-8 text-center text-gray-500 text-sm">알림이 없습니다.</div>
              ) : (
                notifications.slice(0, 20).map((n) => (
                  <div
                    key={n.id}
                    className={`px-4 py-3 border-l-2 ${TYPE_COLORS[n.type] || 'border-gray-700'} ${!n.read ? 'bg-gray-800/60' : ''} hover:bg-gray-800`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-white truncate">{n.title}</p>
                        <p className="text-xs text-gray-400 mt-0.5 line-clamp-2">{n.message}</p>
                      </div>
                      <button onClick={() => remove(n.id)} className="text-gray-600 hover:text-gray-400 text-xs flex-shrink-0">✕</button>
                    </div>
                    <p className="text-xs text-gray-600 mt-1">{new Date(n.timestamp).toLocaleTimeString('ko-KR')}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

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
          <div className="flex items-center gap-2">
            <NotificationPanel />
            <EmergencyStopButton />
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
