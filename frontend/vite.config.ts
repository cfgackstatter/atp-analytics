// frontend/vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/players': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/rankings': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/admin': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/tournaments': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
