import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import babel from '@rolldown/plugin-babel'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    babel({ presets: [reactCompilerPreset()] })
  ],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8787',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
        timeout: 0,
        proxyTimeout: 0,
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            const type = proxyRes.headers['content-type'] ?? ''
            if (!type.includes('text/event-stream')) {
              return
            }
            proxyRes.headers['cache-control'] = 'no-cache'
            proxyRes.headers['connection'] = 'keep-alive'
            delete proxyRes.headers['content-encoding']
          })
        },
      },
    },
  },
})
