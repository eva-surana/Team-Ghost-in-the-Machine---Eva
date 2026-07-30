'use client'
import { useState } from 'react'
import { useSelector } from 'react-redux'

export default function DocumentFidelityBadge() {
  const fidelity = useSelector((state) => state.document.fidelity)
  const [expanded, setExpanded] = useState(false)

  if (!fidelity) return null

  return (
    <div className="relative inline-block text-right">
      <button
        onClick={() => setExpanded((e) => !e)}
        className="flex items-center space-x-2 bg-emerald-50 text-emerald-700 px-3 py-1 rounded-full text-xs font-medium border border-emerald-100 shadow-sm hover:bg-emerald-100 transition-colors cursor-pointer"
      >
        <span>{fidelity.verified}% source fidelity</span>
      </button>

      {expanded && (
        <div className="absolute right-0 top-full mt-2 w-48 bg-white border border-gray-100 rounded-lg shadow-sm p-3 z-20 text-left">
          <div className="text-xs space-y-2">
            <div className="flex justify-between">
              <span className="text-emerald-600 font-medium">Verified</span>
              <span className="text-gray-900">{fidelity.verified}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-amber-600 font-medium">Partial</span>
              <span className="text-gray-900">{fidelity.partial}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-rose-600 font-medium">Unsupported</span>
              <span className="text-gray-900">{fidelity.unsupported}%</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
