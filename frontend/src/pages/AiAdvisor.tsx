export default function AiAdvisor() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100">AI 자문</h2>
      </div>

      <div className="card">
        <div className="space-y-4">
          <div className="bg-slate-800 rounded-lg p-4">
            <p className="text-slate-300">AI 어드바이저에서 거래 권장사항을 받으세요.</p>
          </div>

          <div className="space-y-2">
            <input
              type="text"
              placeholder="질문을 입력하세요..."
              className="input w-full"
            />
            <button className="btn-primary">전송</button>
          </div>
        </div>
      </div>
    </div>
  )
}
