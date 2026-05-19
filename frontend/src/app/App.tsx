import { BrowserRouter } from 'react-router-dom'
import { AppRouter } from './router'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from './queryClient'
import { Toaster } from 'react-hot-toast'

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRouter />
      </BrowserRouter>
      <Toaster position="top-right" toastOptions={{ duration: 3500 }} />
    </QueryClientProvider>
  )
}
