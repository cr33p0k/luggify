import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/geo': 'http://localhost:8000',
      '/generate-packing-list': 'http://localhost:8000',
    },
  },
});
