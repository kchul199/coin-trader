export default function Backtest() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100">백테스트</h2>
      </div>

      <div className="card">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              거래쌍
            </label>
            <select className="input w-full">
              <option>선택...</option>
              <option>BTC/USDT</option>
              <option>ETH/USDT</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                시작일
              </label>
              <input type="date" className="input w-full" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                종료일
              </label>
              <input type="date" className="input w-full" />
            </div>
          </div>

          <button className="btn-primary w-full">백테스트 실행</button>
        </div>
      </div>

      <div className="card">
        <h3 className="text-lg font-semibold text-slate-100 mb-4">결과</h3>
        <p className="text-slate-400">백테스트 결과가 없습니다.</p>
      </div>
    </div>
  )
}
