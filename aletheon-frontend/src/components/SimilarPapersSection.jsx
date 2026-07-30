'use client'
import { useEffect, useState } from 'react'
import { getSimilarPapers } from '../lib/api'

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
      <div className="mt-6 pt-6 border-t border-gray-100">
        <h3 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-4 ml-1">Similar Papers in Corpus</h3>
        <div className="animate-pulse space-y-3">
          <div className="h-16 bg-gray-50 rounded-xl border border-gray-100"></div>
          <div className="h-16 bg-gray-50 rounded-xl border border-gray-100"></div>
        </div>
      </div>
    )
  }

  if (error || !papers || papers.length === 0) {
    return null // Optionally handle error or empty state silently if not found
  }

  return (
    <div className="mt-6 pt-6 border-t border-gray-100">
      <h3 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-4 ml-1">Similar Papers in Corpus</h3>
      <div className="space-y-3">
        {papers.map((paper, i) => (
          <div key={i} className="p-4 bg-white border border-gray-100 rounded-xl shadow-sm hover:border-indigo-100 hover:shadow-md transition-all">
            <h4 className="text-sm font-medium text-gray-900 mb-2">{paper.title}</h4>
            <div className="flex items-center space-x-3">
              <span className="text-[11px] font-medium text-emerald-600 bg-emerald-50 px-2 py-1 rounded border border-emerald-100">
                {Math.round(paper.similarity_score * 100)}% Match
              </span>
              <span className="text-[12px] text-gray-500 truncate flex-1">
                Matched on: {paper.matched_on.join(', ')}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
