import { useState } from 'react'
import { AlertCircle, Loader2 } from 'lucide-react'
import { emergencyApi } from '@/api/endpoints/emergency'
import { useNotificationStore } from '@/stores/notificationStore'
import { useStrategyStore } from '@/stores/strategyStore'

export default function EmergencyStopButton() {
  const [loading, setLoading] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const addNotification = useNotificationStore((s) => s.add)
  const fetchStrategies = useStrategyStore((s) => s.fetchStrategies)

  const handleClick = () => {
    setShowConfirm(true)
  }

  const handleConfirm = async () => {
    setShowConfirm(false)
    setLoading(true)
    try {
      await emergencyApi.stopAll('사용자 긴급 정지')
      addNotification({
        type: 'emergency_stop',
        title: '⚠️ 전체 긴급 정지',
        message: '모든 전략이 긴급 정지되었습니다.',
      })
      await fetchStrategies()
    } catch (err: any) {
      addNotification({
        type: 'error',
        title: '긴급 정지 실패',
        message: err?.response?.data?.detail || '긴급 정지 중 오류가 발생했습니다.',
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <button
        onClick={handleClick}
        disabled={loading}
        className="flex items-center gap-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold py-2 px-4 rounded-lg transition-colors"
        title="전체 긴급 정지"
      >
        {loading ? <Loader2 size={18} className="animate-spin" /> : <AlertCircle size={18} />}
        <span className="hidden sm:inline">긴급 정지</span>
      </button>

      {/* 확인 모달 */}
      {showConfirm && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-[100] p-4">
          <div className="bg-gray-900 border border-red-700 rounded-xl p-6 max-w-sm w-full shadow-2xl">
            <div className="flex items-center gap-3 mb-4">
              <AlertCircle size={28} className="text-red-500 flex-shrink-0" />
              <div>
                <h3 className="text-lg font-bold text-white">전체 긴급 정지</h3>
                <p className="text-sm text-gray-400 mt-0.5">모든 전략과 주문이 즉시 정지됩니다</p>
              </div>
            </div>
            <p className="text-sm text-gray-300 mb-6">
              모든 활성 전략이 비활성화되고 미체결 주문이 취소됩니다.
              이 작업은 되돌릴 수 없습니다.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowConfirm(false)}
                className="flex-1 py-2.5 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-medium text-sm"
              >
                취소
              </button>
              <button
                onClick={handleConfirm}
                className="flex-1 py-2.5 bg-red-600 hover:bg-red-500 text-white rounded-lg font-bold text-sm"
              >
                긴급 정지 실행
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
