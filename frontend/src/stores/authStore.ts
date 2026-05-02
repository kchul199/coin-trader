import { create } from 'zustand'
import { authApi, type UserProfile } from '@/api/endpoints/auth'

interface LoginInput {
  email: string
  password: string
  totpCode?: string
}

interface AuthState {
  token: string | null
  user: UserProfile | null
  isAuthenticated: boolean
  login: (input: LoginInput) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  fetchMe: () => Promise<UserProfile | null>
  logout: () => void
  setUser: (user: UserProfile | null) => void
}

async function loadUserProfile(accessToken: string) {
  const response = await authApi.getMe(accessToken)
  return response.data
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: localStorage.getItem('token'),
  user: null,
  isAuthenticated: !!localStorage.getItem('token'),

  login: async ({ email, password, totpCode }: LoginInput) => {
    try {
      const response = await authApi.login({
        email,
        password,
        totp_code: totpCode || undefined,
      })
      const { access_token } = response.data
      localStorage.setItem('token', access_token)

      let user: UserProfile | null = null
      try {
        user = await loadUserProfile(access_token)
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

  register: async (email: string, password: string) => {
    try {
      await authApi.register({ email, password })
      await get().login({ email, password })
    } catch (error) {
      console.error('Registration failed:', error)
      throw error
    }
  },

  fetchMe: async () => {
    const token = get().token
    if (!token) {
      set({
        user: null,
        isAuthenticated: false,
      })
      return null
    }

    const user = await loadUserProfile(token)
    set({
      token,
      user,
      isAuthenticated: true,
    })
    return user
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
    set({
      user,
      isAuthenticated: !!get().token,
    })
  },
}))
