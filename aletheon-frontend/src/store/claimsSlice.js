import { createSlice } from '@reduxjs/toolkit'

// Each message: { id, type: 'user'|'assistant', content: string | claim[] }
const claimsSlice = createSlice({
  name: 'claims',
  initialState: {
    messages: [],    // full chat history
    items: [],       // claims accumulating for the current streaming turn
    status: 'idle',  // idle | streaming | done | error
  },
  reducers: {
    streamStarted: (state, action) => {
      // action.payload = { question: string }
      state.items = []
      state.status = 'streaming'
      // Push the user's question as a message immediately
      state.messages.push({ id: Date.now(), type: 'user', content: action.payload.question })
    },
    claimReceived: (state, action) => {
      state.items.push(action.payload)
    },
    streamDone: (state) => {
      state.status = 'done'
      // Freeze the accumulated claims as an assistant message
      state.messages.push({ id: Date.now() + 1, type: 'assistant', claims: [...state.items] })
      state.items = []
    },
    streamErrored: (state) => {
      state.status = 'error'
      state.messages.push({ id: Date.now() + 1, type: 'assistant', claims: [], error: true })
      state.items = []
    },
    clearMessages: (state) => {
      state.messages = []
      state.items = []
      state.status = 'idle'
    },
  },
})

export const { streamStarted, claimReceived, streamDone, streamErrored, clearMessages } = claimsSlice.actions
export default claimsSlice.reducer
