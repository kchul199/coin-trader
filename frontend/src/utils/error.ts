import { axios } from '@/api/client'

function extractAxiosDetail(data: unknown): string | undefined {
  if (typeof data === 'string') {
    return data
  }

  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = data.detail
    if (typeof detail === 'string') {
      return detail
    }
  }

  return undefined
}

export function getErrorMessage(
  error: unknown,
  fallback = '요청 처리 중 오류가 발생했습니다.',
) {
  if (axios.isAxiosError(error)) {
    return extractAxiosDetail(error.response?.data) || error.message || fallback
  }

  if (error instanceof Error) {
    return error.message || fallback
  }

  return fallback
}
