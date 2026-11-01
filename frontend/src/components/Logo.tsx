import { Cpu } from 'lucide-react'
import { Link } from 'react-router-dom'

/** The logo from the first frontend: gradient chip mark + "PC Configurator". */
export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2.5 shrink-0 group" aria-label="PC Configurator, pagina principală">
      <span className="brand-mark transition group-hover:scale-105"><Cpu size={19} /></span>
      <span className="text-sm sm:text-base font-extrabold tracking-tight text-white">PC Configurator</span>
    </Link>
  )
}
