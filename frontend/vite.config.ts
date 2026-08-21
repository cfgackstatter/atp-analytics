// frontend/vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

const apiPort = process.env.DEV_API_PORT || '8000';
const apiTarget = `http://localhost:${apiPort}`;

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: Number(process.env.DEV_VITE_PORT) || 3000,
    strictPort: true,
    proxy: {
      '/players': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/rankings': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/admin': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/tournaments': {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
});
