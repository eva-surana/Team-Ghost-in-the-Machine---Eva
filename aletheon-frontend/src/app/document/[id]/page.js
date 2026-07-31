'use client'
import { use } from 'react'
import Link from 'next/link'
import IngestionProgress from '../../../components/IngestionProgress'
import DocumentFidelityBadge from '../../../components/DocumentFidelityBadge'
import SourceViewer from '../../../components/SourceViewer'
import QAChatPanel from '../../../components/QAChatPanel'
import DocumentInsightsPanel from '../../../components/DocumentInsightsPanel'
import { useDocumentStatus } from '../../../lib/useDocumentStatus'
import { ArrowLeft } from 'lucide-react'

export default function DocumentWorkspace({ params }) {
  const { id: documentId } = use(params)
  useDocumentStatus(documentId)

  return (
    <main className="h-screen flex flex-col bg-[#090D16] text-slate-100 overflow-hidden font-sans">
      <header className="flex-shrink-0 border-b border-slate-800 px-5 py-2.5 flex justify-between items-center bg-slate-950/90 z-20">
        <div className="flex items-center gap-3">
          <Link 
            href="/" 
            className="flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-slate-200 transition-colors bg-slate-900 border border-slate-800 px-2.5 py-1 rounded-md"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Documents</span>
          </Link>
          <div className="h-3.5 w-px bg-slate-800" />
          <Link href="/" className="flex items-center gap-2">
            <span className="text-xs font-bold tracking-widest text-slate-200 uppercase font-mono">
              Aletheon
            </span>
          </Link>
        </div>
        <DocumentFidelityBadge />
      </header>

      <IngestionProgress />

      <div className="flex-1 flex overflow-hidden">
        <div className="w-[40%] flex flex-col border-r border-slate-800 bg-slate-950/40">
          <SourceViewer fileUrl={`/api/documents/${documentId}/file`} />
        </div>

        <div className="w-[30%] flex flex-col border-r border-slate-800 bg-[#090D16] p-2">
          <QAChatPanel documentId={documentId} />
        </div>

        <div className="w-[30%] flex flex-col bg-[#090D16] p-2">
          <DocumentInsightsPanel documentId={documentId} />
        </div>
      </div>
    </main>
  )
}
