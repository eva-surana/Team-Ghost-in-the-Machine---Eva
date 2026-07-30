'use client'
import { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useRouter } from 'next/navigation'
import { FileText, ChevronRight, Clock } from 'lucide-react'
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
    <div className="mt-12">
      <h2 className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-6 px-2 flex items-center gap-2">
        <Clock className="w-3 h-3" />
        Recent documents
      </h2>
      <div className="bg-white/40 backdrop-blur-xl rounded-3xl border border-white/50 shadow-xl shadow-gray-200/20 overflow-hidden">
        {documents.map((doc, index) => (
          <div
            key={doc.documentId}
            onClick={() => router.push(`/document/${doc.documentId}`)}
            className={`
              group relative flex items-center justify-between p-5 cursor-pointer transition-all duration-300
              hover:bg-white/80 hover:shadow-lg hover:shadow-indigo-500/5 hover:-translate-y-px
              ${index !== documents.length - 1 ? 'border-b border-gray-100/60' : ''}
            `}
          >
            <div className="flex items-center space-x-5">
              <div className="relative p-3 bg-white rounded-2xl border border-gray-100 shadow-sm group-hover:scale-110 transition-transform duration-300">
                <FileText className="w-5 h-5 text-indigo-500" />
              </div>
              <div>
                <p className="text-sm font-semibold text-gray-900 group-hover:text-indigo-700 transition-colors">{doc.name}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-gradient-to-r from-indigo-500 to-violet-500 text-white shadow-sm">
                    {doc.fidelity}% Fidelity
                  </span>
                  <p className="text-[11px] text-gray-400">Last updated recently</p>
                </div>
              </div>
            </div>
            <div className="w-8 h-8 rounded-full bg-gray-50 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all duration-300 -translate-x-2 group-hover:translate-x-0">
              <ChevronRight className="w-4 h-4 text-indigo-600" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
