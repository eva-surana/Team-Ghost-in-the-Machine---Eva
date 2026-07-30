const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/documents`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Upload failed');
  }

  return response.json();
}

export async function getDocumentStatus(documentId) {
  const response = await fetch(`${API_BASE}/documents/${documentId}/status`);
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch status');
  }

  return response.json();
}

export function streamClaims(documentId, question) {
  const eventSource = new EventSource(
    `${API_BASE}/documents/${documentId}/claims?question=${encodeURIComponent(question)}`
  );

  return eventSource;
}

export async function getDocumentContent(documentId) {
  const response = await fetch(`${API_BASE}/documents/${documentId}/content`);
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch document content');
  }

  return response.json();
}

export async function getSpans(documentId) {
  const response = await fetch(`${API_BASE}/documents/${documentId}/spans`);
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch spans');
  }

  return response.json();
}

export async function fetchDocuments() {
  const response = await fetch(`${API_BASE}/documents`);
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch documents');
  }

  return response.json();
}