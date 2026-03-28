import { AlertCircle } from 'lucide-react'

interface EmergencyStopButtonProps {
  onClick?: () => void
  disabled?: boolean
}

export default function EmergencyStopButton({
  onClick,
  disabled = false,
}: EmergencyStopButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="flex items-center gap-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold py-2 px-4 rounded-lg transition-colors"
      title="긴급 정지"
    >
      <AlertCircle size={20} />
      <span>긴급 정지</span>
    </button>
  )
}
