'use client'
import { FileText } from 'lucide-react'
import ResearchDNACard from './ResearchDNACard'
import DocumentAnalysisTools from './DocumentAnalysisTools'

export default function DocumentInsightsPanel({ documentId }) {
  return (
    <div className="flex flex-col h-full bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 bg-slate-950/80 flex-shrink-0">
        <div className="flex items-center gap-2">
          <FileText className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-300">
            Document Insights
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        <ResearchDNACard documentId={documentId} />
        <div className="border-t border-slate-800 pt-4">
          <DocumentAnalysisTools documentId={documentId} />
        </div>
      </div>
    </div>
  )
}
