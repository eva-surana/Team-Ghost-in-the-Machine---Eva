'use client'
import { useEffect, useRef } from 'react'
import { useDispatch } from 'react-redux'
import { getDocumentStatus } from './api'
import { ingestionStatusUpdated, fidelityReceived } from '../store/documentSlice'

const TERMINAL_STATES = ['completed', 'failed', 'ready', 'error']

// Polls GET /documents/{id}/status, backing off as the job runs longer,
// until a terminal state (ready/error) is reached.
export function useDocumentStatus(documentId) {
  const dispatch = useDispatch()
  const intervalRef = useRef(2000)

  useEffect(() => {
    if (!documentId) return
    let cancelled = false
    let timeoutId

    async function poll() {
      try {
        const data = await getDocumentStatus(documentId)
        if (cancelled) return
        dispatch(ingestionStatusUpdated(data.status))
        if (data.fidelity) dispatch(fidelityReceived(data.fidelity))

        if (!TERMINAL_STATES.includes(data.status)) {
          intervalRef.current = Math.min(intervalRef.current * 1.5, 10000)
          timeoutId = setTimeout(poll, intervalRef.current)
        }
      } catch {
        if (!cancelled) dispatch(ingestionStatusUpdated('error'))
      }
    }

    poll()
    return () => {
      cancelled = true
      clearTimeout(timeoutId)
    }
  }, [documentId, dispatch])
}
