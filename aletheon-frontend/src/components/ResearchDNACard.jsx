'use client'
import { useEffect, useState } from 'react'
import { getResearchDNA } from '../lib/api'
import GroundedClaimChip from './GroundedClaimChip'
import SimilarPapersSection from './SimilarPapersSection'

export default function ResearchDNACard({ documentId }) {
  const [dna, setDna] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!documentId || documentId === 'undefined') return
    setLoading(true)

    let timeoutId
    function fetchDna() {
      getResearchDNA(documentId)
        .then((data) => {
          if (data && data.problem) {
            setDna(data)
            setLoading(false)
          } else {
            // Still processing (returned null for 202 status)
            timeoutId = setTimeout(fetchDna, 2000)
          }
        })
        .catch((err) => {
          console.error('Failed to load Research DNA', err)
          setLoading(false)
        })
    }

    fetchDna()

    return () => clearTimeout(timeoutId)
  }, [documentId])

  if (loading) {
    return (
      <div className="animate-pulse space-y-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i}>
            <div className="h-3 w-20 bg-gray-200 rounded mb-2"></div>
            <div className="h-20 bg-gray-100 rounded-lg"></div>
          </div>
        ))}
      </div>
    )
  }

  if (!dna) return null

  return (
    <div className="space-y-3">
      <div>
        <h3 className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest mb-2 bg-violet-50 text-violet-600 border border-violet-100">Problem</h3>
        <GroundedClaimChip claim={dna.problem} />
      </div>
      <div>
        <h3 className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest mb-2 bg-amber-50 text-amber-600 border border-amber-100">Gap</h3>
        <GroundedClaimChip claim={dna.gap} />
      </div>
      <div>
        <h3 className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest mb-2 bg-sky-50 text-sky-600 border border-sky-100">Method</h3>
        <GroundedClaimChip claim={dna.method} />
      </div>
      <div>
        <h3 className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest mb-2 bg-emerald-50 text-emerald-600 border border-emerald-100">Contribution</h3>
        <GroundedClaimChip claim={dna.contribution} />
      </div>

      <SimilarPapersSection documentId={documentId} />
    </div>
  )
}
