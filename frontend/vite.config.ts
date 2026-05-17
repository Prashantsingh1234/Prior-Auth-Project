import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  optimizeDeps: {
    include: ['react', 'react-dom', 'react-router-dom', '@tanstack/react-query', 'zustand'],
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    target: 'esnext',
    minify: 'esbuild',
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/recharts') || id.includes('node_modules/d3-')) return 'charts'
          if (id.includes('node_modules/framer-motion'))                                return 'motion'
          if (id.includes('node_modules/lucide-react'))                                 return 'icons'
          if (id.includes('node_modules/@tanstack/react-table') ||
              id.includes('node_modules/@tanstack/react-virtual'))                      return 'tanstack-table'
          if (id.includes('node_modules/@tanstack/react-query'))                        return 'query'
          if (id.includes('node_modules/react-pdf') || id.includes('node_modules/pdfjs-dist')) return 'pdf'
          if (id.includes('node_modules/@radix-ui'))                                    return 'radix'
          if (id.includes('node_modules/zustand'))                                      return 'zustand'
          if (id.includes('node_modules/react') || id.includes('node_modules/react-dom') ||
              id.includes('node_modules/react-router-dom'))                             return 'vendor'
        },
      },
    },
  },
})
