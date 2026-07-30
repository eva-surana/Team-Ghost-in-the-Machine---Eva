'use client'
import { use } from 'react'
import Link from 'next/link'
import IngestionProgress from '../../../components/IngestionProgress'
import DocumentFidelityBadge from '../../../components/DocumentFidelityBadge'
import SourceViewer from '../../../components/SourceViewer'
import QAChatPanel from '../../../components/QAChatPanel'
import DocumentInsightsPanel from '../../../components/DocumentInsightsPanel'
import { useDocumentStatus } from '../../../lib/useDocumentStatus'

export default function DocumentWorkspace({ params }) {
  const { id: documentId } = use(params)
  useDocumentStatus(documentId)

  return (
    <main className="h-screen flex flex-col bg-gray-50 overflow-hidden">
      {/* Header */}
      <header className="flex-shrink-0 border-b border-gray-100 px-6 py-3 flex justify-between items-center bg-white/90 backdrop-blur-sm z-20 shadow-[0_1px_0_rgba(0,0,0,0.04)]">
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="w-6 h-6 rounded-md bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-sm group-hover:scale-105 transition-transform">
            <span className="text-white text-[10px] font-bold">A</span>
          </div>
          <span className="text-[13px] font-bold tracking-wide text-gray-800 group-hover:text-indigo-700 transition-colors uppercase">Aletheon</span>
        </Link>
        <DocumentFidelityBadge />
      </header>

      {/* Stepper */}
      <IngestionProgress />

      {/* Main Workspace — 3 columns */}
      <div className="flex-1 flex overflow-hidden">

        {/* Column 1: PDF Viewer (40%) */}
        <div className="w-[40%] flex flex-col border-r border-gray-100 bg-white">
          <SourceViewer fileUrl={`/api/documents/${documentId}/file`} />
        </div>

        {/* Column 2: Q&A (30%) */}
        <div className="w-[30%] flex flex-col border-r border-gray-100 bg-gray-50/50 py-2 pl-2 pr-1">
          <QAChatPanel documentId={documentId} />
        </div>

        {/* Column 3: Document Insights (30%) */}
        <div className="w-[30%] flex flex-col bg-gray-50/50 py-2 pl-1 pr-2">
          <DocumentInsightsPanel documentId={documentId} />
        </div>

      </div>
    </main>
  )
}
