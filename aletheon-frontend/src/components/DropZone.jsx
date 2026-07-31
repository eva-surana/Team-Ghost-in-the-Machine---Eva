'use client'
import { useRef, useState } from 'react'
import { useDispatch } from 'react-redux'
import { useRouter } from 'next/navigation'
import { UploadCloud, Loader2, FileText } from 'lucide-react'
import { uploadDocument } from '../lib/api'
import { documentUploaded } from '../store/documentSlice'

export default function DropZone() {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const inputRef = useRef(null)
  const dispatch = useDispatch()
  const router = useRouter()

  async function handleFile(file) {
    if (!file || file.type !== 'application/pdf') return
    setUploading(true)
    try {
      const { documentId } = await uploadDocument(file)
      dispatch(documentUploaded({ documentId }))
      router.push(`/document/${documentId}`)
    } catch (err) {
      console.error(err)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        handleFile(e.dataTransfer.files?.[0])
      }}
      onClick={() => !uploading && inputRef.current?.click()}
      className={`
        relative border border-dashed rounded-xl p-10 sm:p-14 text-center cursor-pointer transition-all duration-200
        ${dragging 
          ? 'border-indigo-500 bg-indigo-500/5' 
          : 'border-slate-800 bg-slate-950/40 hover:bg-slate-950/80 hover:border-slate-700'}
        ${uploading ? 'cursor-not-allowed opacity-75' : ''}
      `}
    >
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
      
      <div className="flex flex-col items-center justify-center space-y-4">
        <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-400">
          {uploading ? (
            <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
          ) : (
            <UploadCloud className="w-8 h-8 text-slate-400" strokeWidth={1.5} />
          )}
        </div>
        
        <div className="space-y-1">
          <p className="text-sm font-semibold text-slate-200">
            {uploading ? 'Processing PDF Document…' : 'Upload Research PDF'}
          </p>
          <p className="text-xs text-slate-400 font-normal">
            {uploading 
              ? 'Parsing vector text, building TF-IDF index, and preparing spans' 
              : 'Drag & drop or click to choose file'}
          </p>
        </div>

        <div className="pt-1 flex items-center gap-1.5 text-[11px] font-mono text-slate-500">
          <FileText className="w-3 h-3 text-slate-500" />
          <span>PDF up to 50MB</span>
        </div>
      </div>
    </div>
  )
}
