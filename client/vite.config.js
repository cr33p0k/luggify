import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  const apiUrl = env.VITE_API_URL || 'http://localhost:8000';
  const apiProxyTarget = env.VITE_PROXY_API_URL || (apiUrl === '/api' ? 'http://localhost:8000' : apiUrl);

  return {
    plugins: [react()],
    server: {
      allowedHosts: [
        '.trycloudflare.com',
      ],
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
        '/geo': apiProxyTarget,
        '/generate-packing-list': apiProxyTarget,
      },
    },
  };
});
