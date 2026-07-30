'use client'
import { useState, useRef, useEffect } from 'react'
import { useSelector, useDispatch } from 'react-redux'
import { Send, MessageSquare, Bot, AlertCircle } from 'lucide-react'
import { useClaimStream } from '../lib/useClaimStream'
import GroundedClaimChip from './GroundedClaimChip'

export default function QAChatPanel({ documentId }) {
  const [question, setQuestion] = useState('')
  const messages = useSelector((state) => state.claims.messages)
  const streamingClaims = useSelector((state) => state.claims.items)
  const status = useSelector((state) => state.claims.status)
  const { ask } = useClaimStream()
  const bottomRef = useRef(null)

  // Auto-scroll to bottom whenever messages or streaming claims change
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
    <div className="flex flex-col h-full bg-white/70 backdrop-blur-sm rounded-xl border border-white/60 shadow-sm overflow-hidden m-2">
      {/* Panel label */}
      <div className="flex items-center gap-2 px-5 py-3 border-b border-gray-100 flex-shrink-0 bg-white/60">
        <MessageSquare className="w-3.5 h-3.5 text-indigo-400" />
        <span className="text-[11px] font-bold uppercase tracking-widest text-gray-500">Q&amp;A</span>
      </div>

      {/* Chat messages */}
      <div className="flex-1 overflow-y-auto px-4 py-5 space-y-4">
        {isEmpty && (
          <div className="h-full flex flex-col items-center justify-center text-center py-12 space-y-3">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-indigo-50 to-violet-50 border border-indigo-100 flex items-center justify-center">
              <MessageSquare className="w-5 h-5 text-indigo-300" />
            </div>
            <div className="space-y-1">
              <p className="text-sm font-semibold text-gray-700">Ask about this document</p>
              <p className="text-xs text-gray-400">Answers are grounded directly in the source PDF</p>
            </div>
            <div className="flex flex-wrap justify-center gap-2 pt-2 max-w-[220px]">
              {['What is the main finding?', 'What method was used?', 'What are the limitations?'].map((hint) => (
                <button
                  key={hint}
                  onClick={() => setQuestion(hint)}
                  className="text-[11px] text-indigo-500 bg-indigo-50 border border-indigo-100 rounded-full px-3 py-1 hover:bg-indigo-100 transition-colors"
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
              <div className="max-w-[80%] bg-gradient-to-br from-indigo-500 to-violet-600 text-white text-sm font-medium rounded-2xl rounded-br-md px-4 py-3 shadow-sm shadow-indigo-200">
                {msg.content}
              </div>
            ) : (
              <div className="max-w-[95%] space-y-2">
                {/* Bot icon */}
                <div className="flex items-center gap-1.5 mb-1">
                  <div className="w-5 h-5 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center flex-shrink-0">
                    <Bot className="w-3 h-3 text-white" />
                  </div>
                  <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Aletheon</span>
                </div>

                {msg.error ? (
                  <div className="flex items-center gap-2 p-3 bg-rose-50 border border-rose-100 rounded-xl text-rose-600 text-xs">
                    <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                    Could not retrieve an answer. Please try again.
                  </div>
                ) : msg.claims.length === 0 ? (
                  <div className="p-3 bg-gray-50 border border-gray-100 rounded-xl text-gray-500 text-xs">
                    No grounded spans found for this question.
                  </div>
                ) : (
                  <div className="space-y-1.5 bg-white/80 rounded-2xl rounded-tl-md border border-gray-100 p-3 shadow-sm">
                    {msg.claims.map((claim, ci) => (
                      <GroundedClaimChip key={claim.claim_id ?? ci} claim={claim} />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {/* Streaming: show live user message already pushed, now show typing indicator */}
        {status === 'streaming' && (
          <div className="flex justify-start">
            <div className="space-y-2">
              <div className="flex items-center gap-1.5">
                <div className="w-5 h-5 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center">
                  <Bot className="w-3 h-3 text-white" />
                </div>
                <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Aletheon</span>
              </div>
              {streamingClaims.length > 0 ? (
                <div className="space-y-1.5 bg-white/80 rounded-2xl rounded-tl-md border border-gray-100 p-3 shadow-sm max-w-[95%]">
                  {streamingClaims.map((claim, ci) => (
                    <GroundedClaimChip key={claim.claim_id ?? ci} claim={claim} />
                  ))}
                </div>
              ) : (
                <div className="flex items-center gap-1.5 px-4 py-3 bg-white border border-gray-100 rounded-2xl rounded-tl-md shadow-sm w-fit">
                  <span className="w-1.5 h-1.5 bg-indigo-300 rounded-full animate-bounce [animation-delay:0ms]" />
                  <span className="w-1.5 h-1.5 bg-indigo-300 rounded-full animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 bg-indigo-300 rounded-full animate-bounce [animation-delay:300ms]" />
                </div>
              )}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-4 pb-4 pt-3 border-t border-gray-100 flex-shrink-0 bg-white/80 backdrop-blur-md">
        <form onSubmit={handleSubmit} className="relative group">
          <div className="absolute -inset-0.5 bg-gradient-to-r from-indigo-200 to-violet-200 rounded-2xl blur opacity-0 group-focus-within:opacity-100 transition duration-500 pointer-events-none" />
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(e) } }}
            placeholder="Ask about this document…"
            className="relative w-full bg-white border border-gray-200 rounded-xl pl-4 pr-12 py-3 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-indigo-300 focus:ring-1 focus:ring-indigo-100 transition-all shadow-sm resize-none"
            disabled={status === 'streaming'}
          />
          <button
            type="submit"
            disabled={!question.trim() || status === 'streaming'}
            className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 rounded-lg bg-indigo-500 text-white hover:bg-indigo-600 disabled:opacity-30 disabled:bg-gray-300 disabled:text-gray-400 transition-all duration-200 shadow-sm"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </form>
      </div>
    </div>
  )
}
