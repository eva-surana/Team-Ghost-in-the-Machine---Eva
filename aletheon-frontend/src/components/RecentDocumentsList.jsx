'use client'
import { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useRouter } from 'next/navigation'
import { FileText, ChevronRight, Clock, ShieldCheck } from 'lucide-react'
import { getRecentDocuments } from '../lib/api'
import { recentDocumentsLoaded } from '../store/documentSlice'

export default function RecentDocumentsList() {
  const dispatch = useDispatch()
  const router = useRouter()
  const documents = useSelector((state) => state.document.recentDocuments)

  useEffect(() => {
    getRecentDocuments()
      .then((docs) => dispatch(recentDocumentsLoaded(docs)))
      .catch(() => dispatch(recentDocumentsLoaded([])))
  }, [dispatch])

  if (documents.length === 0) return null

  return (
    <div className="mt-8">
      <div className="glass-panel rounded-2xl border border-slate-800/80 overflow-hidden shadow-2xl">
        {documents.map((doc, index) => (
          <div
            key={doc.documentId}
            onClick={() => router.push(`/document/${doc.documentId}`)}
            className={`
              group relative flex items-center justify-between p-4 sm:p-5 cursor-pointer transition-all duration-300
              hover:bg-slate-800/60 hover:border-indigo-500/20
              ${index !== documents.length - 1 ? 'border-b border-slate-800/60' : ''}
            `}
          >
            <div className="flex items-center space-x-4">
              <div className="relative p-3 bg-slate-900/80 rounded-xl border border-slate-700/60 text-indigo-400 group-hover:scale-105 group-hover:border-indigo-500/40 transition-transform duration-300">
                <FileText className="w-5 h-5" />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-100 group-hover:text-indigo-300 transition-colors">
                  {doc.name}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <ShieldCheck className="w-3 h-3" />
                    {doc.fidelity}% Verified
                  </span>
                  <span className="text-[11px] text-slate-500">Document ID: {doc.documentId?.slice(0, 8)}</span>
                </div>
              </div>
            </div>
            <div className="w-8 h-8 rounded-lg bg-slate-800/80 border border-slate-700/60 flex items-center justify-center text-slate-400 group-hover:text-indigo-300 group-hover:bg-indigo-500/20 transition-all duration-300">
              <ChevronRight className="w-4 h-4" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
