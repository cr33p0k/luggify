import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/geo': 'https://luggify.onrender.com',
      '/generate-packing-list': 'https://luggify.onrender.com',
    },
  },
});
