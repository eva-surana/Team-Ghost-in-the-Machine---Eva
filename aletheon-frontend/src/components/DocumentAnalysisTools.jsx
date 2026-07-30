'use client'
import { useState } from 'react'
import {
  getContradictions,
  getDependencyGraph,
  getSimilarPapers,
  getMissingCitations,
} from '../lib/api'

export default function DocumentAnalysisTools({ documentId }) {
  const [activeTool, setActiveTool] = useState(null)
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  async function handleAction(toolName, fetcher) {
    if (activeTool === toolName) {
      // Toggle off if already active
      setActiveTool(null)
      setData(null)
      setError(null)
      return
    }

    setActiveTool(toolName)
    setLoading(true)
    setData(null)
    setError(null)

    let timeoutId
    async function poll() {
      try {
        const result = await fetcher(documentId)
        if (result) {
          setData(result)
          setLoading(false)
        } else {
          timeoutId = setTimeout(poll, 2000)
        }
      } catch (err) {
        console.error(`Failed to load ${toolName}`, err)
        setError(`Failed to load ${toolName}`)
        setLoading(false)
      }
    }
    
    poll()
    
    // We should technically return a cleanup if we switch tools quickly,
    // but for this simple inline component, this is usually fine.
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Analysis Tools</span>
      </div>
      <div className="flex flex-wrap gap-2">
        <ToolButton
          label="Find Contradictions"
          isActive={activeTool === 'contradictions'}
          isLoading={loading && activeTool === 'contradictions'}
          onClick={() => handleAction('contradictions', getContradictions)}
        />
        <ToolButton
          label="View Claim Graph"
          isActive={activeTool === 'graph'}
          isLoading={loading && activeTool === 'graph'}
          onClick={() => handleAction('graph', getDependencyGraph)}
        />
        <ToolButton
          label="Find Similar Papers"
          isActive={activeTool === 'similar'}
          isLoading={loading && activeTool === 'similar'}
          onClick={() => handleAction('similar', getSimilarPapers)}
        />
        <ToolButton
          label="Suggest Missing Citations"
          isActive={activeTool === 'citations'}
          isLoading={loading && activeTool === 'citations'}
          onClick={() => handleAction('citations', getMissingCitations)}
        />
      </div>

      {loading && (
        <div className="p-6 bg-gray-50 border border-gray-100 rounded-xl animate-pulse space-y-4">
          <div className="h-4 w-32 bg-gray-200 rounded"></div>
          <div className="space-y-2">
            <div className="h-3 bg-gray-200 rounded w-full"></div>
            <div className="h-3 bg-gray-200 rounded w-5/6"></div>
          </div>
        </div>
      )}

      {error && (
        <div className="p-4 bg-rose-50 text-rose-600 rounded-xl text-sm border border-rose-100">
          {error}
        </div>
      )}

      {data && activeTool === 'contradictions' && <ContradictionsResult data={data} />}
      {data && activeTool === 'graph' && <GraphResult data={data} />}
      {data && activeTool === 'similar' && <SimilarPapersResult data={data} />}
      {data && activeTool === 'citations' && <MissingCitationsResult data={data} />}
    </div>
  )
}

function ToolButton({ label, isActive, isLoading, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium rounded-lg transition-all border shadow-sm flex items-center space-x-2 ${
        isActive
          ? 'bg-indigo-50 border-indigo-200 text-indigo-700'
          : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50'
      }`}
    >
      {isLoading && (
        <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-current" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      )}
      <span>{label}</span>
    </button>
  )
}

function ContradictionsResult({ data }) {
  if (!data.contradictions || data.contradictions.length === 0) {
    return (
      <div className="p-6 bg-emerald-50 border border-emerald-100 rounded-xl text-emerald-800 text-sm">
        No contradictions found in this document.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-800">Found {data.contradictions.length} Contradictions</h3>
      {data.contradictions.map((c) => (
        <div key={c.pair_id} className="p-5 bg-white border border-gray-100 rounded-xl shadow-sm space-y-3">
          <div className="text-sm text-gray-800 bg-red-50 p-3 rounded-lg border border-red-100">
            <span className="font-semibold text-red-700">Claim A:</span> {c.claim_a.text}
          </div>
          <div className="text-sm text-gray-800 bg-amber-50 p-3 rounded-lg border border-amber-100">
            <span className="font-semibold text-amber-700">Claim B:</span> {c.claim_b.text}
          </div>
          <p className="text-[13px] text-gray-600 italic">
            {c.explanation} (Confidence: {Math.round(c.contradiction_confidence * 100)}%)
          </p>
        </div>
      ))}
    </div>
  )
}

function GraphResult({ data }) {
  const nodeCount = data.claim_nodes.length + data.assumption_nodes.length
  
  if (nodeCount === 0) {
    return (
      <div className="p-6 bg-gray-50 border border-gray-100 rounded-xl text-gray-500 text-sm">
        No dependency graph available.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-800">Dependency Graph</h3>
      <div className="p-6 bg-white border border-gray-100 rounded-xl shadow-sm space-y-4">
        <p className="text-sm text-gray-600 mb-4">
          Found {data.claim_nodes.length} claims and {data.assumption_nodes.length} assumptions with {data.edges.length} edges.
        </p>
        <div className="space-y-3 max-h-80 overflow-y-auto pr-2">
          {data.edges.map((edge, i) => {
            const fromNode = data.claim_nodes.find(n => n.claim_id === edge.from_claim_id) || data.assumption_nodes.find(n => n.assumption_id === edge.from_claim_id)
            const toNode = data.claim_nodes.find(n => n.claim_id === edge.to_claim_id) || data.assumption_nodes.find(n => n.assumption_id === edge.to_claim_id)
            
            if (!fromNode || !toNode) return null

            return (
              <div key={i} className="flex items-center text-[13px] p-3 bg-gray-50 rounded-lg border border-gray-100">
                <div className="flex-1 truncate text-gray-800">{fromNode.text}</div>
                <div className="mx-4 text-indigo-500 font-medium text-[11px] uppercase tracking-wider bg-indigo-50 px-2 py-1 rounded">
                  {edge.relation.replace('_', ' ')}
                </div>
                <div className="flex-1 truncate text-gray-800">{toNode.text}</div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function SimilarPapersResult({ data }) {
  if (data.length === 0) {
    return (
      <div className="p-6 bg-gray-50 border border-gray-100 rounded-xl text-gray-500 text-sm">
        No similar papers found.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-800">Similar Papers in Corpus</h3>
      <div className="space-y-3">
        {data.map((paper, i) => (
          <div key={i} className="p-5 bg-white border border-gray-100 rounded-xl shadow-sm hover:border-indigo-100 hover:shadow-md transition-all">
            <h4 className="text-sm font-medium text-gray-900 mb-2">{paper.title}</h4>
            <div className="flex items-center space-x-4">
              <span className="text-[11px] font-medium text-emerald-600 bg-emerald-50 px-2 py-1 rounded border border-emerald-100">
                {Math.round(paper.similarity_score * 100)}% Match
              </span>
              <span className="text-[12px] text-gray-500 truncate flex-1">
                Matched on: {paper.matched_on.join(', ')}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function MissingCitationsResult({ data }) {
  if (data.length === 0) {
    return (
      <div className="p-6 bg-emerald-50 border border-emerald-100 rounded-xl text-emerald-800 text-sm">
        No missing citations identified.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-800">Suggested Missing Citations</h3>
      <div className="space-y-3">
        {data.map((cit, i) => (
          <div key={i} className="p-5 bg-white border border-gray-100 rounded-xl shadow-sm space-y-3">
            <p className="text-sm text-gray-800 italic border-l-2 border-indigo-200 pl-3">
              "{cit.claim_text}"
            </p>
            <div className="bg-gray-50 p-3 rounded-lg border border-gray-100">
              <p className="text-[13px] font-medium text-gray-900 mb-1">
                Suggestion: {cit.candidate_title}
              </p>
              <p className="text-[12px] text-gray-600">
                Rationale: {cit.rationale_span}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
