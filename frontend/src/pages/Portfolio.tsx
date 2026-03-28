export default function Portfolio() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100">포트폴리오</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <p className="text-slate-400 text-sm">총 자산</p>
          <p className="text-2xl font-bold text-slate-100 mt-2">$0.00</p>
        </div>

        <div className="card">
          <p className="text-slate-400 text-sm">총 수익</p>
          <p className="text-2xl font-bold text-slate-100 mt-2">$0.00</p>
        </div>

        <div className="card">
          <p className="text-slate-400 text-sm">수익률</p>
          <p className="text-2xl font-bold text-slate-100 mt-2">0%</p>
        </div>
      </div>

      <div className="card">
        <h3 className="text-lg font-semibold text-slate-100 mb-4">자산 분배</h3>
        <p className="text-slate-400">포트폴리오 데이터 없음</p>
      </div>
    </div>
  )
}
