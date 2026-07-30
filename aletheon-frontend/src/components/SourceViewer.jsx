'use client'
import { useSelector } from 'react-redux'
import { useEffect, useRef, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

export default function SourceViewer({ fileUrl }) {
  const activeSpanId = useSelector((state) => state.grounding.activeSpanId)
  const ingestionStatus = useSelector((state) => state.document.ingestionStatus)
  const [numPages, setNumPages] = useState(null)
  const pageRefs = useRef({})

  useEffect(() => {
    if (!activeSpanId) return
    const pageMatch = /^p(\d+)/.exec(activeSpanId)
    const pageNum = pageMatch ? Number(pageMatch[1]) : null
    if (pageNum && pageRefs.current[pageNum]) {
      pageRefs.current[pageNum].scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [activeSpanId])

  if (ingestionStatus !== 'completed') {
    return (
      <div className="bg-gray-100/50 h-full flex flex-col items-center justify-center text-center px-8 space-y-6">
        <div className="relative w-16 h-16">
          <div className="w-16 h-16 border-4 border-gray-200 rounded-full absolute" />
          <div className="w-16 h-16 border-4 border-indigo-400 border-t-transparent rounded-full animate-spin absolute" />
        </div>
        <div className="space-y-1.5">
          <p className="text-sm font-medium text-gray-700">Processing document…</p>
          <p className="text-xs text-gray-400">Parsing pages, extracting spans &amp; building the index.</p>
          <p className="text-xs text-gray-400">This may take a moment for large PDFs.</p>
        </div>
        <div className="flex space-x-1.5">
          <span className="w-2 h-2 bg-indigo-300 rounded-full animate-bounce [animation-delay:0ms]" />
          <span className="w-2 h-2 bg-indigo-300 rounded-full animate-bounce [animation-delay:150ms]" />
          <span className="w-2 h-2 bg-indigo-300 rounded-full animate-bounce [animation-delay:300ms]" />
        </div>
      </div>
    )
  }

  return (
    <div className="bg-gray-100/50 p-8 h-full overflow-y-auto flex justify-center">
      <Document 
        file={fileUrl} 
        onLoadSuccess={({ numPages }) => setNumPages(numPages)}
        className="space-y-8 flex flex-col items-center"
      >
        {Array.from({ length: numPages ?? 0 }, (_, i) => i + 1).map((pageNum) => {
          // Check if this page should be highlighted based on activeSpanId
          const isHighlighted = activeSpanId && activeSpanId.startsWith(`p${pageNum}`)
          
          return (
            <div
              key={pageNum}
              ref={(el) => {
                pageRefs.current[pageNum] = el
              }}
              className={`
                bg-white shadow-md transition-all duration-300 relative
                ${isHighlighted ? 'scale-[1.01] shadow-lg ring-2 ring-amber-400' : ''}
              `}
            >
              {isHighlighted && (
                <div className="absolute inset-0 bg-amber-300/10 pointer-events-none z-10 transition-colors duration-300" />
              )}
              <Page pageNumber={pageNum} width={650} renderTextLayer={true} renderAnnotationLayer={true} className="overflow-hidden" />
            </div>
          )
        })}
      </Document>
    </div>
  )
}
