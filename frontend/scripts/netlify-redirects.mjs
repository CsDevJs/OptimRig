// Netlify build step: proxy /api/* to the FastAPI backend at BACKEND_URL.
// Like the Vite dev proxy, it strips the /api prefix, so the browser stays on one
// origin and the backend needs no CORS setup.
import { writeFileSync } from 'node:fs'

const backend = (process.env.BACKEND_URL ?? '').trim().replace(/\/+$/, '')
if (!/^https?:\/\/[^/\s]+/.test(backend)) {
  console.error(
    'BACKEND_URL is not set (or not an http(s) URL). Set it in Netlify > Site configuration > ' +
      'Environment variables to the public URL of the FastAPI backend, e.g. https://api.example.com',
  )
  process.exit(1)
}

writeFileSync('dist/_redirects', `/api/*  ${backend}/:splat  200!\n`)
console.log(`dist/_redirects: /api/* -> ${backend}/:splat`)
