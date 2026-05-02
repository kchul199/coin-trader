import client from '../client'

export interface UserProfile {
  id: string
  email: string
  is_active: boolean
  has_2fa: boolean
  created_at: string
}

export interface RegisterRequest {
  email: string
  password: string
}

export interface LoginRequest {
  email: string
  password: string
  totp_code?: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
}

export interface TotpSetupResponse {
  secret: string
  qr_uri: string
}

export const authApi = {
  register: (data: RegisterRequest) =>
    client.post<UserProfile>('/auth/register', data),
  login: (data: LoginRequest) =>
    client.post<TokenResponse>('/auth/login', data),
  getMe: (token?: string) =>
    client.get<UserProfile>('/auth/me', token
      ? { headers: { Authorization: `Bearer ${token}` } }
      : undefined),
  setup2fa: () =>
    client.post<TotpSetupResponse>('/auth/2fa/setup'),
  verify2fa: (totpCode: string) =>
    client.post('/auth/2fa/verify', { totp_code: totpCode }),
}
