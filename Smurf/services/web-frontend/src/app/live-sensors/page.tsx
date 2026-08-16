import Sidebar from "../components/Sidebar";

export default function LiveSensorsPage() {
  return (
    <div className="min-h-screen bg-slate-50 flex font-sans text-slate-900 selection:bg-emerald-200">
      <Sidebar activePage="Live Sensors" />
      <div className="flex-1 md:ml-64 flex flex-col min-h-screen overflow-x-hidden p-8">
        <h1 className="text-2xl font-bold mb-6 text-slate-800">Live Sensors</h1>
        <div className="clean-card p-6">
          <p className="text-slate-600">Dữ liệu Live Sensors (Đất, Nước, Khí hậu...) sẽ được hiển thị và cập nhật theo thời gian thực tại đây.</p>
        </div>
      </div>
    </div>
  );
}
