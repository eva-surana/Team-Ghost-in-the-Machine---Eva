'use client'
import { useEffect, useState } from 'react'
import { getResearchDNA } from '../lib/api'
import GroundedClaimChip from './GroundedClaimChip'
import SimilarPapersSection from './SimilarPapersSection'
import { Loader2 } from 'lucide-react'

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
      <div className="flex items-center gap-2 p-4 text-xs text-slate-400 font-mono">
        <Loader2 className="w-4 h-4 animate-spin text-slate-400" />
        <span>Extracting Research Facets…</span>
      </div>
    )
  }

  if (!dna) return null

  return (
    <div className="space-y-3.5">
      <div>
        <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-1.5 font-bold">
          Problem Statement
        </div>
        <GroundedClaimChip claim={dna.problem} />
      </div>

      <div>
        <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-1.5 font-bold">
          Research Gap
        </div>
        <GroundedClaimChip claim={dna.gap} />
      </div>

      <div>
        <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-1.5 font-bold">
          Methodology
        </div>
        <GroundedClaimChip claim={dna.method} />
      </div>

      <div>
        <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-1.5 font-bold">
          Core Contribution
        </div>
        <GroundedClaimChip claim={dna.contribution} />
      </div>

      <div className="pt-3 border-t border-slate-800">
        <SimilarPapersSection documentId={documentId} />
      </div>
    </div>
  )
}
