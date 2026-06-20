import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Backend CORS is configured for http://localhost:3000
    port: 3000,
    strictPort: true,
  },
})
