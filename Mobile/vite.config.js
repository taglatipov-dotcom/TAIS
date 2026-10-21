import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Сборка кладётся в dist — Capacitor копирует её в Android-проект (cap sync).
// base './' — в приложении страницы открываются не с корня сайта.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: './',
  // всё приложение — один файл из папки приложения, размер не важен
  build: { outDir: 'dist', emptyOutDir: true, chunkSizeWarningLimit: 4000 },
  // веса по умолчанию берутся из ../Library/Веса элементов.csv
  server: { fs: { allow: ['..'] } },
})
