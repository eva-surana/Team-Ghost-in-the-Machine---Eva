import { useDispatch, useSelector } from 'react-redux';
import { useCallback, useRef, useEffect } from 'react';
import { 
  selectCurrentDocument, 
  selectClaims, 
  selectClaimsLoading, 
  selectClaimsError,
  selectUploadedFile,
  selectDocumentStatus,
  selectDocumentError,
  setCurrentDocument,
  clearClaims,
  addClaimChunk,
} from '@/store/slices/documentSlice';

export function useDocuments() {
  const dispatch = useDispatch();
  
  const currentDocument = useSelector(selectCurrentDocument);
  const claims = useSelector(selectClaims);
  const claimsLoading = useSelector(selectClaimsLoading);
  const claimsError = useSelector(selectClaimsError);

  const selectDocument = useCallback((document) => {
    dispatch(setCurrentDocument(document));
  }, [dispatch]);

  const clearClaimsAction = useCallback(() => {
    dispatch(clearClaims());
  }, [dispatch]);

  const addClaimAction = useCallback((claim) => {
    dispatch(addClaimChunk(claim));
  }, [dispatch]);

  return {
    currentDocument,
    claims,
    claimsLoading,
    claimsError,
    selectDocument,
    clearClaims: clearClaimsAction,
    addClaim: addClaimAction,
  };
}

export function useStreamClaims() {
  const dispatch = useDispatch();
  const eventSourceRef = useRef(null);
  const claimsRef = useRef([]);

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const startStream = useCallback(async (documentId, question) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    claimsRef.current = [];
    dispatch(clearClaims());

    try {
      const response = await fetch(`/api/claims/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ document_id: documentId, question }),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to start stream' }));
        throw new Error(error.detail || 'Failed to start claim stream');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              return;
            }
            try {
              const claim = JSON.parse(data);
              claimsRef.current.push(claim);
              dispatch(addClaimChunk(claim));
            } catch (e) {
              console.warn('Failed to parse claim:', data);
            }
          }
        }
      }
    } catch (error) {
      console.error('Stream error:', error);
    }
  }, [dispatch]);

  const cancelStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  return { startStream, cancelStream };
}

export function useDocumentUpload() {
  const dispatch = useDispatch();
  const uploadedFile = useSelector(selectUploadedFile);
  const uploadStatus = useSelector(selectDocumentStatus);
  const uploadError = useSelector(selectDocumentError);

  return {
    uploadedFile,
    uploadStatus,
    uploadError,
  };
}