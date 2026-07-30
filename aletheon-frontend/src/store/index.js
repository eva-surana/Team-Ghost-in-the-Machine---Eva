import { configureStore } from '@reduxjs/toolkit'
import groundingReducer from './groundingSlice'
import claimsReducer from './claimsSlice'
import documentReducer from './documentSlice'

export const store = configureStore({
  reducer: {
    grounding: groundingReducer,
    claims: claimsReducer,
    document: documentReducer,
  },
})