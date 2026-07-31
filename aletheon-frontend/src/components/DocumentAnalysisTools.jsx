'use client'
import { useState } from 'react'
import {
  getContradictions,
  getDependencyGraph,
  getSimilarPapers,
  getMissingCitations,
} from '../lib/api'
import { AlertOctagon, GitMerge, FileSearch, BookmarkPlus, Loader2, ArrowRight } from 'lucide-react'

export default function DocumentAnalysisTools({ documentId }) {
  const [activeTool, setActiveTool] = useState(null)
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  async function handleAction(toolName, fetcher) {
    if (activeTool === toolName) {
      setActiveTool(null)
      setData(null)
      setError(null)
      return
    }

    setActiveTool(toolName)
    setLoading(true)
    setData(null)
    setError(null)

    async function poll() {
      try {
        const result = await fetcher(documentId)
        if (result) {
          setData(result)
          setLoading(false)
        } else {
          setTimeout(poll, 2000)
        }
      } catch (err) {
        console.error(`Failed to load ${toolName}`, err)
        setError(`Failed to load ${toolName}`)
        setLoading(false)
      }
    }

    poll()
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-[11px] font-bold uppercase tracking-widest text-slate-400">
          Advanced Diagnostic Tools
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <ToolButton
          label="Contradictions"
          icon={AlertOctagon}
          isActive={activeTool === 'contradictions'}
          isLoading={loading && activeTool === 'contradictions'}
          onClick={() => handleAction('contradictions', getContradictions)}
        />
        <ToolButton
          label="Claim Graph"
          icon={GitMerge}
          isActive={activeTool === 'graph'}
          isLoading={loading && activeTool === 'graph'}
          onClick={() => handleAction('graph', getDependencyGraph)}
        />
        <ToolButton
          label="Corpus Matches"
          icon={FileSearch}
          isActive={activeTool === 'similar'}
          isLoading={loading && activeTool === 'similar'}
          onClick={() => handleAction('similar', getSimilarPapers)}
        />
        <ToolButton
          label="Missing Citations"
          icon={BookmarkPlus}
          isActive={activeTool === 'citations'}
          isLoading={loading && activeTool === 'citations'}
          onClick={() => handleAction('citations', getMissingCitations)}
        />
      </div>

      {loading && (
        <div className="p-6 bg-slate-900/80 border border-slate-800 rounded-xl space-y-3">
          <div className="flex items-center gap-2 text-indigo-400 text-xs font-semibold">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Computing structural diagnostics…</span>
          </div>
          <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
            <div className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 w-2/3 animate-pulse" />
          </div>
        </div>
      )}

      {error && (
        <div className="p-4 bg-rose-500/10 text-rose-400 border border-rose-500/20 rounded-xl text-xs">
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

function ToolButton({ label, icon: Icon, isActive, isLoading, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-2.5 text-xs font-semibold rounded-xl transition-all duration-300 border flex items-center justify-between gap-2 ${
        isActive
          ? 'bg-indigo-500/20 border-indigo-500/50 text-indigo-300 shadow-lg shadow-indigo-500/10'
          : 'bg-slate-900/60 border-slate-800 text-slate-300 hover:bg-slate-800/80 hover:border-slate-700'
      }`}
    >
      <div className="flex items-center gap-2 truncate">
        {isLoading ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-400" />
        ) : (
          <Icon className="w-3.5 h-3.5 text-slate-400" />
        )}
        <span className="truncate">{label}</span>
      </div>
    </button>
  )
}

function ContradictionsResult({ data }) {
  if (!data.contradictions || data.contradictions.length === 0) {
    return (
      <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400 text-xs font-medium">
        ✓ No within-paper contradictions detected.
      </div>
    )
  }

  return (
    <div className="space-y-3 pt-2">
      <h3 className="text-xs font-bold text-slate-300">Found {data.contradictions.length} Contradictions</h3>
      {data.contradictions.map((c) => (
        <div key={c.pair_id} className="p-4 bg-slate-900/90 border border-slate-800 rounded-xl space-y-2.5">
          <div className="text-xs text-rose-300 bg-rose-500/10 p-2.5 rounded-lg border border-rose-500/20">
            <span className="font-bold uppercase tracking-wider text-[10px] text-rose-400 block mb-0.5">Claim A</span>
            "{c.claim_a.text}"
          </div>
          <div className="text-xs text-amber-300 bg-amber-500/10 p-2.5 rounded-lg border border-amber-500/20">
            <span className="font-bold uppercase tracking-wider text-[10px] text-amber-400 block mb-0.5">Claim B</span>
            "{c.claim_b.text}"
          </div>
          <p className="text-[11px] text-slate-400 italic">
            {c.explanation} ({Math.round(c.contradiction_confidence * 100)}% confidence)
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
      <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl text-slate-400 text-xs">
        No claim dependencies mapped.
      </div>
    )
  }

  return (
    <div className="space-y-3 pt-2">
      <h3 className="text-xs font-bold text-slate-300">Claim Dependency Graph</h3>
      <div className="p-4 bg-slate-900/90 border border-slate-800 rounded-xl space-y-3">
        <p className="text-xs text-slate-400">
          Mapped {data.claim_nodes.length} claims and {data.assumption_nodes.length} assumptions with {data.edges.length} graph edges.
        </p>
        <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
          {data.edges.map((edge, i) => {
            const fromNode = data.claim_nodes.find(n => n.claim_id === edge.from_claim_id) || data.assumption_nodes.find(n => n.assumption_id === edge.from_claim_id)
            const toNode = data.claim_nodes.find(n => n.claim_id === edge.to_claim_id) || data.assumption_nodes.find(n => n.assumption_id === edge.to_claim_id)

            if (!fromNode || !toNode) return null

            return (
              <div key={i} className="flex items-center text-xs p-2.5 bg-slate-950/80 rounded-lg border border-slate-800">
                <div className="flex-1 truncate text-slate-300 font-medium">{fromNode.text}</div>
                <div className="mx-2 text-indigo-400 font-bold text-[9px] uppercase tracking-wider bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                  {edge.relation.replace('_', ' ')}
                </div>
                <div className="flex-1 truncate text-slate-300 font-medium">{toNode.text}</div>
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
      <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl text-slate-400 text-xs">
        No similar papers in corpus.
      </div>
    )
  }

  return (
    <div className="space-y-3 pt-2">
      <h3 className="text-xs font-bold text-slate-300">Corpus Paper Matches</h3>
      <div className="space-y-2.5">
        {data.map((paper, i) => (
          <div key={i} className="p-3.5 bg-slate-900/90 border border-slate-800 rounded-xl hover:border-indigo-500/30 transition-all">
            <h4 className="text-xs font-bold text-slate-100 mb-1.5">{paper.title}</h4>
            <div className="flex items-center space-x-3">
              <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                {Math.round(paper.similarity_score * 100)}% Similarity
              </span>
              <span className="text-[11px] text-slate-400 truncate flex-1">
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
      <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400 text-xs font-medium">
        ✓ No un-cited claims identified.
      </div>
    )
  }

  return (
    <div className="space-y-3 pt-2">
      <h3 className="text-xs font-bold text-slate-300">Missing Citation Suggestions</h3>
      <div className="space-y-2.5">
        {data.map((cit, i) => (
          <div key={i} className="p-3.5 bg-slate-900/90 border border-slate-800 rounded-xl space-y-2">
            <p className="text-xs text-slate-300 italic border-l-2 border-indigo-400 pl-2.5">
              "{cit.claim_text}"
            </p>
            <div className="bg-slate-950/80 p-2.5 rounded-lg border border-slate-800">
              <p className="text-xs font-bold text-slate-200 mb-0.5">
                Suggested Paper: {cit.candidate_title}
              </p>
              <p className="text-[11px] text-slate-400">
                Rationale: {cit.rationale_span}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
