import Sidebar from "../components/Sidebar";

export default function SettingsPage() {
  return (
    <div className="min-h-screen bg-slate-50 flex font-sans text-slate-900 selection:bg-emerald-200">
      <Sidebar activePage="Settings" />
      <div className="flex-1 md:ml-64 flex flex-col min-h-screen overflow-x-hidden p-8 items-center justify-center">
        <div className="text-center w-full">
          <h1 className="text-3xl font-bold text-slate-800 mb-6">Settings</h1>
          <div className="clean-card p-12 max-w-lg mx-auto flex flex-col items-center border border-dashed border-slate-300 bg-slate-50/50">
            <span className="text-5xl mb-4 grayscale opacity-80">⚙️</span>
            <h2 className="text-xl font-semibold text-slate-700 mb-2">Tính năng sẽ phát triển sau</h2>
            <p className="text-slate-500 text-center text-sm leading-relaxed">
              Hệ thống cài đặt cấu hình trạm, ngưỡng cảm biến (thresholds), và thông số mô hình AI sẽ được ra mắt trong bản cập nhật sau.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
