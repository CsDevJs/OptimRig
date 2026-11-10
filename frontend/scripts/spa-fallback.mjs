// After `vite build`: dist/404.html is a copy of the app. Static hosts (Vercel, GitHub
// Pages) serve it for any path that isn't a file, so links like /manual and page
// reloads open the app, and React Router shows the right page.
import { copyFileSync } from 'node:fs'

copyFileSync('dist/index.html', 'dist/404.html')
