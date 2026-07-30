'use client'
import { useDispatch } from 'react-redux'
import { setActiveSpan, pinSpan } from '../store/groundingSlice'

const STATUS_STYLES = {
  verified: { border: 'border-l-emerald-500', label: 'text-emerald-600', text: 'Verified' },
  partially_supported: {
    border: 'border-l-amber-500',
    label: 'text-amber-600',
    text: 'Partially supported',
  },
  unsupported: { border: 'border-l-rose-500', label: 'text-rose-600', text: 'Unsupported' },
}

export default function GroundedClaimChip({ claim }) {
  const dispatch = useDispatch()
  const style = STATUS_STYLES[claim.verification_status] ?? STATUS_STYLES.unsupported
  const primarySpanId = claim.cited_spans?.[0]?.source_id

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
      className={`mb-2 p-3 bg-gray-50 border-l-[3px] rounded-r-xl cursor-default transition-colors duration-150 ease-in-out ${style.border} hover:bg-gray-100/70`}
    >
      <p className="text-xs text-gray-700 leading-relaxed">{claim.text}</p>
      <div className={`mt-2 text-[10px] font-semibold uppercase tracking-wider ${style.label}`}>
        {style.text}
      </div>
    </div>
  )
}
