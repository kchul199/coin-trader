import { create } from 'zustand'
import client from '@/api/client'

interface User {
  id: string
  email: string
  is_active: boolean
  has_2fa: boolean
  created_at: string
}

interface AuthState {
  token: string | null
  user: User | null
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  setUser: (user: User | null) => void
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('token'),
  user: null,
  isAuthenticated: !!localStorage.getItem('token'),

  login: async (email: string, password: string) => {
    try {
      const response = await client.post('/auth/login', { email, password })
      const { access_token } = response.data
      localStorage.setItem('token', access_token)

      let user: User | null = null
      try {
        const meResponse = await client.get('/auth/me', {
          headers: { Authorization: `Bearer ${access_token}` },
        })
        user = meResponse.data
      } catch (profileError) {
        console.warn('Failed to fetch user profile after login:', profileError)
      }

      set({
        token: access_token,
        user,
        isAuthenticated: true,
      })
    } catch (error) {
      console.error('Login failed:', error)
      throw error
    }
  },

  logout: () => {
    localStorage.removeItem('token')
    set({
      token: null,
      user: null,
      isAuthenticated: false,
    })
  },

  setUser: (user) => {
    set({ user })
  },
}))
