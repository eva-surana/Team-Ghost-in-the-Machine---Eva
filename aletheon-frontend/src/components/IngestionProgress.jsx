'use client'
import { useSelector } from 'react-redux'

const STAGES = ['parsing', 'ocr', 'embedding', 'extraction', 'ready']

export default function IngestionProgress() {
  const status = useSelector((state) => state.document.ingestionStatus)
  const currentIndex = STAGES.indexOf(status)

  if (status === 'idle' || status === 'ready') return null

  return (
    <div className="flex items-center px-6 py-2.5 border-b border-gray-100 bg-white shadow-sm">
      <div className="flex items-center space-x-1">
        {STAGES.map((stage, i) => {
          const isCompleted = i <= currentIndex
          return (
            <div key={stage} className="flex items-center">
              <div
                className={`w-2 h-2 rounded-full transition-colors duration-300 ${
                  isCompleted ? 'bg-gray-800' : 'bg-gray-200'
                }`}
                title={stage}
              />
              {i < STAGES.length - 1 && (
                <div
                  className={`w-6 h-[1px] mx-1 transition-colors duration-300 ${
                    i < currentIndex ? 'bg-gray-800' : 'bg-gray-200'
                  }`}
                />
              )}
            </div>
          )
        })}
      </div>
      <span className="text-[11px] font-medium text-gray-500 ml-4 uppercase tracking-wider">
        {status}...
      </span>
    </div>
  )
}
