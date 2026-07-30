'use client'
import { Microscope } from 'lucide-react'
import ResearchDNACard from './ResearchDNACard'
import DocumentAnalysisTools from './DocumentAnalysisTools'

export default function DocumentInsightsPanel({ documentId }) {
  return (
    <div className="flex flex-col h-full bg-white/60 backdrop-blur-sm rounded-xl border border-white/60 shadow-sm overflow-hidden m-2 mt-0">
      {/* Panel label */}
      <div className="flex items-center gap-2 px-5 py-3 border-b border-gray-100/60 flex-shrink-0 bg-white/50">
        <Microscope className="w-3.5 h-3.5 text-violet-400" />
        <span className="text-[11px] font-bold uppercase tracking-widest text-gray-500">Document Insights</span>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto p-5 space-y-6">
        <ResearchDNACard documentId={documentId} />
        <div className="border-t border-gray-100 pt-5">
          <DocumentAnalysisTools documentId={documentId} />
        </div>
      </div>
    </div>
  )
}
