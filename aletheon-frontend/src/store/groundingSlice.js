import { createSlice } from '@reduxjs/toolkit'

const groundingSlice = createSlice({
  name: 'grounding',
  initialState: {
    activeSpanId: null,
    pinnedSpanIds: [],
  },
  reducers: {
    setActiveSpan: (state, action) => {
      state.activeSpanId = action.payload
    },
    clearActiveSpan: (state) => {
      state.activeSpanId = null
    },
    pinSpan: (state, action) => {
      if (!state.pinnedSpanIds.includes(action.payload)) {
        state.pinnedSpanIds.push(action.payload)
      }
    },
    unpinSpan: (state, action) => {
      state.pinnedSpanIds = state.pinnedSpanIds.filter((id) => id !== action.payload)
    },
  },
})

export const { setActiveSpan, clearActiveSpan, pinSpan, unpinSpan } = groundingSlice.actions
export default groundingSlice.reducer
