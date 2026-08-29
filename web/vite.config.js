import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In dev the API runs separately on :8000 (CORS is open there).
// In prod the FastAPI app serves web/dist, so same-origin '' works.
export default defineConfig({
  plugins: [react()],
  build: { outDir: 'dist' },
})
