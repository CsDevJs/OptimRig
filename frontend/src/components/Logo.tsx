import { Cpu } from 'lucide-react'
import { Link } from 'react-router-dom'

/** OptimRig logo: outlined chip in the accent colour + "Optim" (white) "Rig" (accent). */
export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 shrink-0 group" aria-label="OptimRig, pagina principală">
      <span className="brand-mark transition group-hover:scale-105"><Cpu size={24} strokeWidth={2} /></span>
      <span className="text-base sm:text-lg font-extrabold tracking-tight text-white">
        Optim<span className="text-violet-400">Rig</span>
      </span>
    </Link>
  )
}
