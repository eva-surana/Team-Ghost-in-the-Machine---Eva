'use client'
import { useState } from 'react'
import { useSelector } from 'react-redux'

export default function DocumentFidelityBadge() {
  const fidelity = useSelector((state) => state.document.fidelity)
  const [expanded, setExpanded] = useState(false)

  if (!fidelity) return null

  return (
    <div className="relative inline-block text-right font-mono">
      <button
        onClick={() => setExpanded((e) => !e)}
        className="flex items-center space-x-1.5 bg-slate-900 text-emerald-400 px-2.5 py-1 rounded text-xs font-medium border border-slate-800 hover:border-slate-700 transition-colors cursor-pointer"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
        <span>Fidelity: {fidelity.verified}%</span>
      </button>

      {expanded && (
        <div className="absolute right-0 top-full mt-1.5 w-44 bg-slate-900 border border-slate-800 rounded-lg shadow-xl p-3 z-30 text-left text-xs space-y-1.5 font-mono">
          <div className="flex justify-between items-center text-slate-300">
            <span className="text-emerald-400">Verified</span>
            <span>{fidelity.verified}%</span>
          </div>
          <div className="flex justify-between items-center text-slate-300">
            <span className="text-amber-400">Partial</span>
            <span>{fidelity.partial}%</span>
          </div>
          <div className="flex justify-between items-center text-slate-300">
            <span className="text-rose-400">Unsupported</span>
            <span>{fidelity.unsupported}%</span>
          </div>
        </div>
      )}
    </div>
  )
}
