'use client'
import { useRef, useState } from 'react'
import { useDispatch } from 'react-redux'
import { useRouter } from 'next/navigation'
import { UploadCloud, Loader2 } from 'lucide-react'
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
        relative overflow-hidden border-[3px] border-dashed rounded-3xl p-16 text-center cursor-pointer transition-all duration-500 ease-out
        ${dragging 
          ? 'border-indigo-500 bg-indigo-50/30 scale-[1.02] shadow-[0_0_40px_-10px_rgba(99,102,241,0.3)]' 
          : 'border-slate-200 bg-white/50 hover:bg-white/80 hover:border-indigo-300 hover:shadow-lg'}
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
      
      <div className="flex flex-col items-center justify-center space-y-6">
        <div className={`
          relative p-5 rounded-full transition-all duration-500
          ${dragging ? 'bg-indigo-100 text-indigo-600 scale-110' : 'bg-slate-50 text-slate-400'}
        `}>
          {dragging && (
            <div className="absolute inset-0 rounded-full animate-ping bg-indigo-200 opacity-20" />
          )}
          {uploading ? (
            <Loader2 className="w-10 h-10 animate-spin text-indigo-600" />
          ) : (
            <UploadCloud className="w-10 h-10 transition-transform duration-500" strokeWidth={1.5} />
          )}
        </div>
        
        <div className="space-y-1">
          <p className="text-lg font-semibold text-slate-900 tracking-tight">
            {uploading ? 'Processing Document...' : 'Drop a PDF to verify'}
          </p>
          <p className="text-sm text-slate-500 font-medium">
            {uploading ? 'Please wait while we prepare your file' : 'or click to browse from your computer'}
          </p>
        </div>
      </div>
    </div>
  )
}
