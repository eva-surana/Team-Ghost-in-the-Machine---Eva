'use client'
import { useDispatch } from 'react-redux'
import { setActiveSpan, pinSpan } from '../store/groundingSlice'

const STATUS_MAP = {
  verified: {
    border: 'border-l-emerald-500 bg-slate-950/80 border-slate-800 hover:border-slate-700',
    tag: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    label: 'Verified',
  },
  partially_supported: {
    border: 'border-l-amber-500 bg-slate-950/80 border-slate-800 hover:border-slate-700',
    tag: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    label: 'Partial Support',
  },
  unsupported: {
    border: 'border-l-rose-500 bg-slate-950/80 border-slate-800 hover:border-slate-700',
    tag: 'text-rose-400 bg-rose-500/10 border-rose-500/20',
    label: 'Unsupported',
  },
}

export default function GroundedClaimChip({ claim }) {
  const dispatch = useDispatch()
  const statusConfig = STATUS_MAP[claim.verification_status] ?? STATUS_MAP.unsupported
  const primarySpan = claim.cited_spans?.[0]
  const primarySpanId = primarySpan?.source_id
  const confidencePct = claim.confidence ? Math.round(claim.confidence * 100) : null

  function handleHover() {
    if (primarySpanId) dispatch(setActiveSpan(primarySpanId))
  }

  function handleLeave() {
    dispatch(setActiveSpan(null))
  }

  function handleClick() {
    if (primarySpanId) dispatch(pinSpan(primarySpanId))
  }

  return (
    <div
      onMouseEnter={handleHover}
      onMouseLeave={handleLeave}
      onClick={handleClick}
      className={`p-3 rounded-lg border border-l-2 cursor-pointer transition-all ${statusConfig.border}`}
    >
      <p className="text-xs text-slate-200 leading-relaxed font-sans">
        "{claim.text}"
      </p>

      <div className="mt-2.5 flex items-center justify-between border-t border-slate-800/60 pt-2 text-[10px] font-mono">
        <div className="flex items-center gap-2">
          <span className={`px-1.5 py-0.5 rounded border uppercase tracking-wider font-semibold ${statusConfig.tag}`}>
            {statusConfig.label}
          </span>
          {primarySpan && (
            <span className="text-slate-400">
              p.{primarySpan.page} {primarySpan.section ? `· ${primarySpan.section}` : ''}
            </span>
          )}
        </div>

        {confidencePct !== null && (
          <span className="text-slate-400">
            {confidencePct}% conf
          </span>
        )}
      </div>
    </div>
  )
}
