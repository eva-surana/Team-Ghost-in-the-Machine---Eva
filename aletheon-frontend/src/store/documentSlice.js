import { createSlice } from '@reduxjs/toolkit'

const documentSlice = createSlice({
  name: 'document',
  initialState: {
    currentDocumentId: null,
    ingestionStatus: 'idle', // idle | parsing | ocr | embedding | extraction | ready | error
    fidelity: null, // { verified, partial, unsupported } percentage breakdown
    recentDocuments: [],
  },
  reducers: {
    documentUploaded: (state, action) => {
      state.currentDocumentId = action.payload.documentId
      state.ingestionStatus = 'parsing'
    },
    ingestionStatusUpdated: (state, action) => {
      state.ingestionStatus = action.payload
    },
    fidelityReceived: (state, action) => {
      state.fidelity = action.payload
    },
    recentDocumentsLoaded: (state, action) => {
      state.recentDocuments = action.payload
    },
  },
})

export const {
  documentUploaded,
  ingestionStatusUpdated,
  fidelityReceived,
  recentDocumentsLoaded,
} = documentSlice.actions
export default documentSlice.reducer
