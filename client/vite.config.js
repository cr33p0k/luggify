import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/geo': process.env.VITE_API_URL || 'http://localhost:8000',
      '/generate-packing-list': process.env.VITE_API_URL || 'http://localhost:8000',
    },
  },
});
