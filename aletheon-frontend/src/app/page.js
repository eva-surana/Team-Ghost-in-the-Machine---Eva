'use client'
import DropZone from '../components/DropZone'
import RecentDocumentsList from '../components/RecentDocumentsList'

export default function Home() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-[#fafafa]">
      {/* Animated background elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-indigo-200/30 blur-[120px] animate-pulse" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-emerald-200/30 blur-[120px] animate-pulse delay-700" />
      </div>

      <main className="relative z-10 max-w-3xl mx-auto pt-24 px-6 pb-20">
        <div className="flex flex-col items-center text-center space-y-6 mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white border border-gray-200 shadow-sm">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-600">v1.0.0 Now Live</span>
          </div>
          
          <div className="space-y-2">
            <h1 className="text-5xl font-bold tracking-tight text-gray-900">Aletheon</h1>
            <p className="text-lg text-gray-500 max-w-md">Precision document verification and automated research extraction for professional workflows.</p>
          </div>
        </div>
        
        <div className="group relative bg-white/60 backdrop-blur-xl rounded-3xl border border-white/80 shadow-[0_8px_40px_-12px_rgba(0,0,0,0.1)] p-1 transition-all duration-300 hover:shadow-[0_8px_40px_-8px_rgba(0,0,0,0.15)]">
          <div className="p-8">
            <DropZone />
          </div>
        </div>
        
        <div className="mt-16">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-6 px-1">Recent Activity</h2>
          <RecentDocumentsList />
        </div>
      </main>
    </div>
  )
}
