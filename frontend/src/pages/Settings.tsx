export default function Settings() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100">설정</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="card">
          <h3 className="text-lg font-semibold text-slate-100 mb-4">
            API 키 관리
          </h3>
          <p className="text-slate-400 text-sm mb-4">
            거래소 API 키를 설정합니다.
          </p>
          <button className="btn-secondary w-full">API 키 설정</button>
        </div>

        <div className="card">
          <h3 className="text-lg font-semibold text-slate-100 mb-4">
            알림 설정
          </h3>
          <p className="text-slate-400 text-sm mb-4">
            거래 알림 설정을 관리합니다.
          </p>
          <button className="btn-secondary w-full">알림 설정</button>
        </div>

        <div className="card">
          <h3 className="text-lg font-semibold text-slate-100 mb-4">
            거래 설정
          </h3>
          <p className="text-slate-400 text-sm mb-4">
            거래 파라미터를 설정합니다.
          </p>
          <button className="btn-secondary w-full">거래 설정</button>
        </div>

        <div className="card">
          <h3 className="text-lg font-semibold text-slate-100 mb-4">
            계정 설정
          </h3>
          <p className="text-slate-400 text-sm mb-4">
            계정 정보를 수정합니다.
          </p>
          <button className="btn-secondary w-full">계정 설정</button>
        </div>
      </div>
    </div>
  )
}
