'use client'
import { useEffect, useState } from 'react'
import { getSimilarPapers } from '../lib/api'
import { BookOpen, Sparkles, Loader2 } from 'lucide-react'

export default function SimilarPapersSection({ documentId }) {
  const [loading, setLoading] = useState(true)
  const [papers, setPapers] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!documentId || documentId === 'undefined') return
    setLoading(true)

    let timeoutId
    function fetchPapers() {
      getSimilarPapers(documentId)
        .then((data) => {
          if (data) {
            setPapers(data)
            setLoading(false)
          } else {
            timeoutId = setTimeout(fetchPapers, 2000)
          }
        })
        .catch((err) => {
          console.error('Failed to load similar papers', err)
          setError('Failed to load similar papers')
          setLoading(false)
        })
    }

    fetchPapers()

    return () => clearTimeout(timeoutId)
  }, [documentId])

  if (loading) {
    return (
      <div className="mt-4 pt-4 border-t border-slate-800/80">
        <h3 className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-3 flex items-center gap-1.5">
          <BookOpen className="w-3.5 h-3.5 text-indigo-400" />
          Related Papers in Corpus
        </h3>
        <div className="flex items-center gap-2 text-xs text-slate-400 py-3">
          <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
          <span>Searching local corpus index…</span>
        </div>
      </div>
    )
  }

  if (error || !papers || papers.length === 0) {
    return null
  }

  return (
    <div className="mt-4 pt-4 border-t border-slate-800/80">
      <h3 className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-3 flex items-center gap-1.5">
        <BookOpen className="w-3.5 h-3.5 text-indigo-400" />
        Related Papers in Corpus
      </h3>
      <div className="space-y-2.5">
        {papers.map((paper, i) => (
          <div key={i} className="p-3.5 bg-slate-900/80 border border-slate-800 rounded-xl hover:border-indigo-500/30 transition-all">
            <h4 className="text-xs font-bold text-slate-100 mb-1.5">{paper.title}</h4>
            <div className="flex items-center space-x-3">
              <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                {Math.round(paper.similarity_score * 100)}% Similarity
              </span>
              <span className="text-[11px] text-slate-400 truncate flex-1">
                Matched on: {paper.matched_on?.join(', ') || 'Corpus indexing'}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
