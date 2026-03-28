export default function Orders() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100">주문</h2>
      </div>

      <div className="card">
        <p className="text-slate-400">활성 주문이 없습니다.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card">
          <h3 className="text-lg font-semibold text-slate-100 mb-4">매수 주문</h3>
          <p className="text-slate-400">주문 데이터 없음</p>
        </div>

        <div className="card">
          <h3 className="text-lg font-semibold text-slate-100 mb-4">매도 주문</h3>
          <p className="text-slate-400">주문 데이터 없음</p>
        </div>
      </div>
    </div>
  )
}
