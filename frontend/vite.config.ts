import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5175, // 与 ai_crawl 前端(5173)错开
    proxy: {
      '/api': {
        // 后端端口可用环境变量覆盖（默认 8000），便于临时错开端口调试
        target: `http://localhost:${process.env.ASKBASE_API_PORT || 8000}`,
        changeOrigin: true,
      },
    },
  },
})
