import { create } from 'zustand'

export type NotificationType = 'order_filled' | 'order_failed' | 'order_created' | 'emergency_stop' | 'ai_advice' | 'info' | 'error'

export interface Notification {
  id: string
  type: NotificationType
  title: string
  message: string
  strategyId?: string
  timestamp: number
  read: boolean
}

interface NotificationStore {
  notifications: Notification[]
  unreadCount: number
  add: (n: Omit<Notification, 'id' | 'timestamp' | 'read'>) => void
  markRead: (id: string) => void
  markAllRead: () => void
  remove: (id: string) => void
  clear: () => void
}

export const useNotificationStore = create<NotificationStore>((set) => ({
  notifications: [],
  unreadCount: 0,

  add: (n) => {
    const notification: Notification = {
      ...n,
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      timestamp: Date.now(),
      read: false,
    }
    set((s) => ({
      notifications: [notification, ...s.notifications].slice(0, 100), // 최대 100개 유지
      unreadCount: s.unreadCount + 1,
    }))
  },

  markRead: (id) =>
    set((s) => ({
      notifications: s.notifications.map((n) =>
        n.id === id ? { ...n, read: true } : n
      ),
      unreadCount: Math.max(0, s.unreadCount - 1),
    })),

  markAllRead: () =>
    set((s) => ({
      notifications: s.notifications.map((n) => ({ ...n, read: true })),
      unreadCount: 0,
    })),

  remove: (id) =>
    set((s) => {
      const n = s.notifications.find((x) => x.id === id)
      return {
        notifications: s.notifications.filter((x) => x.id !== id),
        unreadCount: n && !n.read ? Math.max(0, s.unreadCount - 1) : s.unreadCount,
      }
    }),

  clear: () => set({ notifications: [], unreadCount: 0 }),
}))
