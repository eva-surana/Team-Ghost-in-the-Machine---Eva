'use client'
import { useDispatch } from 'react-redux'
import { streamStarted, claimReceived, streamDone, streamErrored } from '../store/claimsSlice'

// Manual SSE parser: EventSource doesn't support POST bodies, so we read
// the fetch response body as a stream and split it on SSE message boundaries.
export function useClaimStream() {
  const dispatch = useDispatch()

  async function ask(documentId, question) {
    dispatch(streamStarted({ question }))

    try {
      const res = await fetch(`/api/documents/${documentId}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      if (!res.ok || !res.body) throw new Error('Stream failed to start')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const messages = buffer.split('\n\n')
        buffer = messages.pop() ?? '' // keep incomplete chunk for next read

        for (const raw of messages) {
          if (!raw.trim()) continue
          const eventLine = raw.split('\n').find((l) => l.startsWith('event:'))
          const dataLine = raw.split('\n').find((l) => l.startsWith('data:'))
          const eventType = eventLine?.replace('event:', '').trim()
          const data = dataLine ? JSON.parse(dataLine.replace('data:', '').trim()) : null

          if (eventType === 'claim' && data) dispatch(claimReceived(data))
          // eventType === 'status' can drive a progress indicator if you add one
        }
      }
      dispatch(streamDone())
    } catch {
      dispatch(streamErrored())
    }
  }

  return { ask }
}
