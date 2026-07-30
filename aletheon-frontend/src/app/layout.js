'use client'
import { Inter } from 'next/font/google'
import { Provider } from 'react-redux'
import { store } from '../store'
import './globals.css'
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'

const inter = Inter({ subsets: ['latin'] })

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className={`${inter.className} antialiased bg-[#FAFAFA] min-h-screen selection:bg-indigo-100 selection:text-indigo-900`}>
        <Provider store={store}>{children}</Provider>
      </body>
    </html>
  )
}
