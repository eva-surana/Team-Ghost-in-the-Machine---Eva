'use client'
import DropZone from '../components/DropZone'
import RecentDocumentsList from '../components/RecentDocumentsList'
import { ShieldCheck, Lock, FileSearch, Layers } from 'lucide-react'

export default function Home() {
  return (
    <div className="relative min-h-screen bg-[#090D16] text-slate-100 font-sans selection:bg-indigo-500/20 selection:text-indigo-300">
      <div 
        className="absolute inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage: `radial-gradient(#94A3B8 1px, transparent 1px)`,
          backgroundSize: '24px 24px'
        }}
      />

      <main className="relative z-10 max-w-4xl mx-auto pt-20 px-6 pb-24">
        <div className="flex flex-col items-center text-center space-y-6 mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900 border border-slate-800 text-[11px] font-mono text-slate-400">
            <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />
            <span>Air-Gapped Document Engine</span>
          </div>

          <div className="space-y-3 max-w-2xl">
            <h1 className="text-4xl sm:text-5xl font-bold tracking-tight text-slate-100">
              Aletheon <span className="text-slate-400 font-normal">Research Engine</span>
            </h1>
            <p className="text-sm sm:text-base text-slate-400 leading-relaxed max-w-lg mx-auto">
              Precision document extraction, verbatim provenance mapping, and deterministic verification for research workflows.
            </p>
          </div>

          <div className="flex flex-wrap justify-center gap-2.5 pt-1">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 text-xs text-slate-300">
              <ShieldCheck className="w-3.5 h-3.5 text-slate-400" />
              <span>Verbatim Citation</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 text-xs text-slate-300">
              <Lock className="w-3.5 h-3.5 text-slate-400" />
              <span>Zero External Network</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 text-xs text-slate-300">
              <Layers className="w-3.5 h-3.5 text-slate-400" />
              <span>Micro-Span Grounding</span>
            </div>
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-2xl backdrop-blur-sm">
          <DropZone />
        </div>

        <div className="mt-14">
          <div className="flex items-center justify-between mb-4 px-1">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <FileSearch className="w-3.5 h-3.5 text-slate-500" />
              Processed Documents
            </h2>
          </div>
          <RecentDocumentsList />
        </div>
      </main>
    </div>
  )
}
