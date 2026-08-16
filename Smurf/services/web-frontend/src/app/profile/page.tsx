import Sidebar from "../components/Sidebar";

export default function ProfilePage() {
  return (
    <div className="min-h-screen bg-slate-50 flex font-sans text-slate-900 selection:bg-emerald-200">
      <Sidebar activePage="" />
      <div className="flex-1 md:ml-64 flex flex-col min-h-screen overflow-x-hidden p-8">
        <h1 className="text-2xl font-bold mb-6 text-slate-800">User Profile</h1>
        <div className="clean-card p-6 flex items-center gap-6">
          <div className="w-24 h-24 rounded-full bg-slate-300 flex items-center justify-center text-slate-600 font-bold text-3xl border-4 border-white shadow-md">
            FM
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-800">Farm Manager</h2>
            <p className="text-emerald-600 font-medium">Administrator</p>
            <p className="text-slate-500 text-sm mt-2">manager@smartfarm.local</p>
          </div>
        </div>
      </div>
    </div>
  );
}
