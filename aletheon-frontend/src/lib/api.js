// Same-origin in Tier 1 delivery (FastAPI serves the built Next.js app),
// so a relative base URL works both in dev (proxied) and in production.
const BASE_URL = '/api'

export async function uploadDocument(file) {
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch(`${BASE_URL}/documents`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) throw new Error('Upload failed')
  const data = await res.json()
  return { documentId: data.document_id, ...data }
}

export async function getDocumentStatus(documentId) {
  const res = await fetch(`${BASE_URL}/documents/${documentId}/status`)
  if (!res.ok) throw new Error('Status check failed')
  const data = await res.json()
  return { ...data, documentId: data.document_id }
}

export async function getRecentDocuments() {
  const res = await fetch(`${BASE_URL}/documents`)
  if (!res.ok) throw new Error('Could not load recent documents')
  return res.json() // [{ documentId, name, fidelity }, ...]
}

export async function getResearchDNA(documentId) {
  const res = await fetch(`${BASE_URL}/documents/${documentId}/research-dna`)
  if (res.status === 202) return null // Still processing
  if (!res.ok) throw new Error('Could not load research DNA')
  return res.json() // { problem, gap, method, contribution }
}

export async function getContradictions(documentId) {
  const res = await fetch(`${BASE_URL}/documents/${documentId}/contradictions`)
  if (res.status === 202) return null
  if (!res.ok) throw new Error('Could not load contradictions')
  return res.json()
}

export async function getDependencyGraph(documentId) {
  const res = await fetch(`${BASE_URL}/documents/${documentId}/dependency-graph`)
  if (res.status === 202) return null
  if (!res.ok) throw new Error('Could not load dependency graph')
  return res.json()
}

export async function getSimilarPapers(documentId) {
  const res = await fetch(`${BASE_URL}/documents/${documentId}/recommendations/similar-papers`)
  if (res.status === 202) return null
  if (!res.ok) throw new Error('Could not load similar papers')
  return res.json()
}

export async function getMissingCitations(documentId) {
  const res = await fetch(`${BASE_URL}/documents/${documentId}/recommendations/missing-citations`)
  if (res.status === 202) return null
  if (!res.ok) throw new Error('Could not load missing citations')
  return res.json()
}
