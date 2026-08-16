import Sidebar from "../components/Sidebar";

export default function PlansTasksPage() {
  return (
    <div className="min-h-screen bg-slate-50 flex font-sans text-slate-900 selection:bg-emerald-200">
      <Sidebar activePage="Plans & Tasks" />
      <div className="flex-1 md:ml-64 flex flex-col min-h-screen overflow-x-hidden p-8">
        <h1 className="text-2xl font-bold mb-6 text-slate-800">Plans & Tasks</h1>
        <div className="clean-card p-6">
          <p className="text-slate-600">Kế hoạch tưới tiêu tự động và các tác vụ cho kỹ sư hiện trường.</p>
        </div>
      </div>
    </div>
  );
}
