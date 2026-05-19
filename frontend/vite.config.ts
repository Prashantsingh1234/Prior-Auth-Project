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
    headers: {
      'X-Content-Type-Options':  'nosniff',
      'X-Frame-Options':         'DENY',
      'X-XSS-Protection':        '1; mode=block',
      'Referrer-Policy':         'strict-origin-when-cross-origin',
      'Permissions-Policy':      'camera=(), microphone=(), geolocation=()',
      'Cross-Origin-Opener-Policy':   'same-origin',
      'Cross-Origin-Resource-Policy': 'same-origin',
    },
    proxy: {
      '/api': {
        // Use IPv4 explicitly to avoid Windows/Node IPv6 localhost resolution issues (ECONNREFUSED ::1).
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        timeout: 120_000,
        proxyTimeout: 120_000,
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
