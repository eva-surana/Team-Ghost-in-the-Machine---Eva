'use client'
import { useState, useRef, useEffect } from 'react'
import { useSelector } from 'react-redux'
import { Send, MessageSquare, AlertCircle, Search } from 'lucide-react'
import { useClaimStream } from '../lib/useClaimStream'
import GroundedClaimChip from './GroundedClaimChip'

export default function QAChatPanel({ documentId }) {
  const [question, setQuestion] = useState('')
  const messages = useSelector((state) => state.claims.messages)
  const streamingClaims = useSelector((state) => state.claims.items)
  const status = useSelector((state) => state.claims.status)
  const { ask } = useClaimStream()
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingClaims])

  function handleSubmit(e) {
    e.preventDefault()
    if (!question.trim() || status === 'streaming') return
    ask(documentId, question.trim())
    setQuestion('')
  }

  const isEmpty = messages.length === 0 && status === 'idle'

  return (
    <div className="flex flex-col h-full bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 bg-slate-950/80 flex-shrink-0">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-300">
            Document Q&amp;A
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-400 bg-slate-900 border border-slate-800 px-2 py-0.5 rounded">
          <span>Extractive Search</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 font-sans">
        {isEmpty && (
          <div className="h-full flex flex-col items-center justify-center text-center py-8 space-y-3">
            <div className="p-3 rounded-xl bg-slate-800/80 border border-slate-700/60 text-slate-400">
              <Search className="w-5 h-5" />
            </div>
            <div className="space-y-1 max-w-xs">
              <p className="text-xs font-semibold text-slate-200">Query Document Spans</p>
              <p className="text-[11px] text-slate-400">Answers are extracted verbatim from the PDF source</p>
            </div>
            <div className="flex flex-col gap-1.5 pt-2 w-full max-w-xs">
              {[
                'What is the proposed methodology?',
                'What dataset was used?',
                'What are the primary contributions?',
              ].map((hint) => (
                <button
                  key={hint}
                  onClick={() => setQuestion(hint)}
                  className="text-left text-[11px] text-slate-300 bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 hover:border-slate-700 hover:bg-slate-900 transition-colors"
                >
                  {hint}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.type === 'user' ? (
              <div className="max-w-[85%] bg-slate-800 border border-slate-700 text-slate-100 text-xs font-medium rounded-xl px-3.5 py-2.5 shadow-sm">
                {msg.content}
              </div>
            ) : (
              <div className="max-w-[98%] space-y-2 w-full">
                <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500">
                  Extracted Evidence Spans
                </div>

                {msg.error ? (
                  <div className="flex items-center gap-2 p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-400 text-xs">
                    <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                    Could not retrieve matching spans.
                  </div>
                ) : msg.claims.length === 0 ? (
                  <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg text-slate-400 text-xs font-mono">
                    No matching verified spans found for this query.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {msg.claims.map((claim, ci) => (
                      <GroundedClaimChip key={claim.claim_id ?? ci} claim={claim} />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {status === 'streaming' && (
          <div className="flex justify-start w-full">
            <div className="space-y-2 w-full">
              <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
                Retrieving &amp; Verifying Spans…
              </div>
              {streamingClaims.length > 0 ? (
                <div className="space-y-2">
                  {streamingClaims.map((claim, ci) => (
                    <GroundedClaimChip key={claim.claim_id ?? ci} claim={claim} />
                  ))}
                </div>
              ) : (
                <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-400 font-mono">
                  Searching TF-IDF sparse matrix…
                </div>
              )}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="p-3 border-t border-slate-800 bg-slate-950/90 flex-shrink-0">
        <form onSubmit={handleSubmit} className="relative">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(e) } }}
            placeholder="Search document text…"
            className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-3 pr-10 py-2 text-xs text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-slate-700 font-sans"
            disabled={status === 'streaming'}
          />
          <button
            type="submit"
            disabled={!question.trim() || status === 'streaming'}
            className="absolute right-1.5 top-1/2 -translate-y-1/2 p-1.5 rounded-md bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-30 disabled:bg-slate-800 disabled:text-slate-600 transition-colors"
          >
            <Send className="w-3 h-3" />
          </button>
        </form>
      </div>
    </div>
  )
}
