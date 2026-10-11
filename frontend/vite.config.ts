import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// VITE_BASE: path the app is served from ("/" by default; "/Nba_History/" for GitHub Pages).
// VITE_API_BASE: API origin when it isn't the same server (see src/api/client.ts).
export default defineConfig({
  base: process.env.VITE_BASE || '/',
  plugins: [react()],
  server: {
    // `npm run dev` forwards API calls to the FastAPI server on :8000
    proxy: { '/api': 'http://localhost:8000' },
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 700,
  },
  test: {
    environment: 'node',
  },
});
