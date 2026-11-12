import { Code, ShieldHalf } from 'lucide-react'

const FOUNDERS = [
  { name: 'Buza Alin', role: 'Front-End Developer & UI/UX Specialist', ring: 'border-violet-400/60', text: 'text-violet-300' },
  { name: 'Grosu Vladislav', role: 'Database Developer & Architecture Lead', ring: 'border-sky-400/60', text: 'text-sky-300' },
  { name: 'Borta Adrian', role: 'Back-End Developer & Security Architect', ring: 'border-pink-400/60', text: 'text-pink-300' },
]

const TECH = [
  ['React + TypeScript', 'bg-violet-400/15 border-violet-400/30 text-violet-200'],
  ['Vite & Tailwind CSS', 'bg-sky-400/15 border-sky-400/30 text-sky-200'],
  ['FastAPI (Python)', 'bg-pink-400/15 border-pink-400/30 text-pink-200'],
  ['PostgreSQL', 'bg-violet-400/15 border-violet-400/30 text-violet-200'],
  ['AC-3 · TOPSIS · Min-Cost Max-Flow', 'bg-sky-400/15 border-sky-400/30 text-sky-200'],
]

function FounderCard({ name, role, ring, text }: (typeof FOUNDERS)[number]) {
  const initials = name.split(' ').map((w) => w[0]).join('')
  return (
    <div className="modern-sleek-card glow rounded-2xl p-6 text-center space-y-4 flex flex-col justify-between">
      <div className="space-y-4">
        <div className={`w-32 h-32 mx-auto rounded-2xl border-2 ${ring} bg-slate-900 flex items-center justify-center`}>
          <span className={`text-4xl font-extrabold ${text}`}>{initials}</span>
        </div>
        <div>
          <h3 className="text-base font-extrabold text-white">{name}</h3>
          <p className={`text-xs font-medium ${text}`}>{role}</p>
        </div>
      </div>
      <p className="text-xs text-slate-400 pt-3 border-t border-slate-800">Student UTM • Securitate Informațională (Anul II)</p>
    </div>
  )
}

export function FoundersPage() {
  return (
    <section className="space-y-6">
      <div className="slate-glow-card glow rounded-2xl p-5">
        <h2 className="text-lg font-extrabold text-white">Fondatorii site-ului & echipa UTM</h2>
        <p className="text-xs text-slate-300">Studenți UTM, Securitate Informațională (Anul II)</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {FOUNDERS.map((f) => <FounderCard key={f.name} {...f} />)}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4">
        <div className="slate-glow-card glow rounded-2xl p-6 space-y-3">
          <h3 className="text-sm font-extrabold text-white flex items-center gap-2"><ShieldHalf size={15} className="text-violet-300" /> Despre proiectul academic</h3>
          <p className="text-xs text-slate-300 leading-relaxed">
            Platformă dezvoltată la Universitatea Tehnică a Moldovei (UTM) pentru configurarea și optimizarea asamblării
            calculatoarelor: verificarea compatibilității componentelor (AC-3), clasarea configurațiilor (TOPSIS) și alegerea
            magazinelor cu costul total minim (Min-Cost Max-Flow), cu prețuri reale din magazinele din Moldova.
          </p>
        </div>
        <div className="slate-glow-card glow rounded-2xl p-6 space-y-3">
          <h3 className="text-sm font-extrabold text-white flex items-center gap-2"><Code size={15} className="text-sky-300" /> Tehnologii utilizate</h3>
          <div className="flex flex-wrap gap-2 pt-1">
            {TECH.map(([label, cls]) => <span key={label} className={`px-2.5 py-1 rounded-lg border text-xs font-mono font-bold ${cls}`}>{label}</span>)}
          </div>
        </div>
      </div>
    </section>
  )
}
