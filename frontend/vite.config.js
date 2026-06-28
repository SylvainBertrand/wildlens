import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server is reachable on the LAN (e.g. from shumai) and proxies /api to the
// FastAPI backend so the frontend can call relative URLs in dev and prod alike.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.WILDLENS_API || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
