import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // Bind mounts on Windows/Docker don't emit inotify events.
    watch: { usePolling: true, interval: 300 },
  },
});
