import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  resolve: {
    // Root-relative so no Node types are needed; mirrors `paths` in tsconfig.
    alias: { '@': '/src' },
  },
  server: {
    host: true,
    port: 5173,
    // Bind mounts on Windows/Docker don't emit inotify events.
    watch: { usePolling: true, interval: 300 },
  },
});
