import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 3002,
    open: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5002',
        changeOrigin: true,
        secure: false
      }
    }
  }
})
