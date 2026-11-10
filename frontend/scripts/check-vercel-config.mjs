// Vercel build step: stop the deploy if vercel.json still points /api at the
// placeholder instead of your backend's address.
import { readFileSync } from 'node:fs'

const config = JSON.parse(readFileSync(new URL('../vercel.json', import.meta.url), 'utf8'))
const api = config.rewrites?.find((r) => r.source === '/api/:path*')
if (!api || !/^https?:\/\/[^/\s]+/.test(api.destination) || api.destination.includes('YOUR-NGROK-DOMAIN')) {
  console.error(
    'frontend/vercel.json: set the /api/:path* rewrite destination to your backend, e.g. ' +
      'https://your-name.ngrok-free.app/:path* (see "Vercel" in frontend/README.md).',
  )
  process.exit(1)
}
console.log(`vercel.json: /api/* -> ${api.destination}`)
