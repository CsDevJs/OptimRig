import { BrainCircuit, Briefcase, Clapperboard, Gamepad2, WandSparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../api/client'
import type { Purpose, Recommendations, Selection } from '../api/types'
import { useBuilder } from '../builder/BuilderContext'
import { RankedBuildCard } from '../components/RankedBuildCard'
import { useCurrency } from '../context/CurrencyContext'
import { useToast } from '../context/ToastContext'

type Brand = 'any' | 'AMD' | 'Intel'
const PURPOSES = [
  { id: 'gaming', label: 'Gaming / eSports', icon: Gamepad2 },
  { id: 'office', label: 'Office', icon: Briefcase },
  { id: 'workstation', label: 'Workstation / stație AI', icon: BrainCircuit },
  { id: 'editing', label: 'Editare video / foto', icon: Clapperboard },
] as const
const PURPOSE_KEY = 'pc-configurator-purpose'
const pct = (weight: number) => `${Math.round(weight * 100)}%`
const PRESETS = [
  { label: 'Buget', value: 30000, cls: 'bg-white/5 hover:bg-white/10 border-white/25 text-white' },
  { label: 'Mediu', value: 55000, cls: 'bg-sky-400/10 hover:bg-sky-400/20 border-sky-400/30 text-sky-300' },
  { label: 'High-End', value: 90000, cls: 'bg-violet-400/10 hover:bg-violet-400/20 border-violet-400/30 text-violet-300' },
  { label: 'Ultra', value: 120000, cls: 'bg-pink-400/10 hover:bg-pink-400/20 border-pink-400/30 text-pink-300' },
]

export function SmartPage() {
  const { replace } = useBuilder()
  const { code, format } = useCurrency()
  const toast = useToast()
  const navigate = useNavigate()
  const [budget, setBudget] = useState(55000)
  const [brand, setBrand] = useState<Brand>('any')
  const [purpose, setPurposeState] = useState<Purpose>(() => {
    try {
      const saved = localStorage.getItem(PURPOSE_KEY)
      return PURPOSES.some((p) => p.id === saved) ? (saved as Purpose) : 'gaming'
    } catch {
      return 'gaming'
    }
  })
  const setPurpose = (next: Purpose) => {
    setPurposeState(next)
    try {
      localStorage.setItem(PURPOSE_KEY, next)
    } catch {
      // Storage blocked: the choice lasts until the page is closed.
    }
  }

  // TOPSIS ranking of every compatible build within budget. Waits until the slider stops.
  const query = `${budget}|${purpose}|${brand}`
  const [answer, setAnswer] = useState<{ query: string; result?: Recommendations; error?: string } | null>(null)
  const loading = answer?.query !== query
  const result = answer?.result ?? null
  const error = loading ? null : (answer?.error ?? null)
  useEffect(() => {
    let active = true
    const timer = setTimeout(() => {
      api.recommend(budget, purpose, brand === 'any' ? null : brand)
        .then((r) => active && setAnswer({ query, result: r }))
        .catch((e: Error) => active && setAnswer({ query, error: e.message }))
    }, 400)
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [query, budget, purpose, brand])

  return (
    <section className="space-y-8">
      <div className="slate-glow-card glow rounded-3xl p-6 sm:p-8 relative overflow-hidden">
        <div className="space-y-2">
          <span className="px-3 py-1 rounded-full bg-violet-400/15 border border-violet-300/30 text-violet-200 text-xs font-semibold flex items-center gap-1.5 w-fit">
            <WandSparkles size={13} className="text-white" /> Recomandare inteligentă
          </span>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">Configurator inteligent PC</h1>
          <p className="text-slate-300 text-sm sm:text-base">
            Alege bugetul (afișat în <span className="text-violet-300 font-semibold">{code}</span>) și primește configurații compatibile, cu prețuri de azi.
          </p>
        </div>

        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-6 pt-6 border-t border-slate-800/80">
          <div className="space-y-4 modern-sleek-card rounded-2xl p-6">
            <div className="flex items-center justify-between">
              <label htmlFor="budget" className="text-xs font-bold uppercase tracking-wider text-slate-400">1. Buget țintă</label>
              <span className="text-xl font-extrabold font-mono text-violet-300">{format(budget)}</span>
            </div>
            <input id="budget" type="range" min={20000} max={130000} step={1000} value={budget}
              onChange={(e) => setBudget(Number(e.target.value))} className="w-full h-2" />
            <div className="grid grid-cols-4 gap-2 pt-2">
              {PRESETS.map((p) => (
                <button key={p.label} type="button" onClick={() => setBudget(p.value)}
                  className={`p-2 rounded-xl border text-left transition hover:scale-105 ${p.cls}`}>
                  <div className="text-[11px] font-bold">{p.label}</div>
                  <div className="text-[10px] text-slate-300 font-mono">{format(p.value)}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-4 modern-sleek-card rounded-2xl p-6">
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block mb-3">2. Brand CPU</span>
              <div className="grid grid-cols-3 gap-2">
                {(['any', 'AMD', 'Intel'] as Brand[]).map((b) => (
                  <button key={b} type="button" onClick={() => setBrand(b)}
                    className={`py-2.5 px-2 rounded-xl text-xs font-bold border transition hover:scale-105 ${brand === b ? 'border-violet-400/50 bg-violet-400/20 text-white' : 'border-slate-800 bg-slate-900 text-slate-300'}`}>
                    {b === 'any' ? 'Oricare' : b}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="md:col-span-2 space-y-4 modern-sleek-card rounded-2xl p-6">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block">3. Scopul PC-ului</span>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-2" role="radiogroup" aria-label="Scopul PC-ului">
              {PURPOSES.map(({ id, label, icon: Icon }) => (
                <button key={id} type="button" role="radio" aria-checked={purpose === id} onClick={() => setPurpose(id)}
                  className={`py-3 px-3 rounded-xl text-xs font-bold border transition hover:scale-105 flex items-center justify-center gap-2 text-center ${purpose === id ? 'border-violet-400/50 bg-violet-400/20 text-white' : 'border-slate-800 bg-slate-900 text-slate-300'}`}>
                  <Icon size={15} className="text-violet-300 shrink-0" /> {label}
                </button>
              ))}
            </div>
            <p className="text-[11px] text-slate-400">
              Scopul stabilește ponderile TOPSIS, cât contează procesorul față de placa video în performanță
              și cerințele minime: procesor, placă video, RAM, stocare, sursă și un cooler cu rezervă de răcire.
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-extrabold text-white">Variante recomandate</h2>
          {result && (
            <span className="text-[11px] text-slate-400">
              TOPSIS pe {result.alternatives.toLocaleString('ro-RO')} configurații compatibile · ponderi: preț {pct(result.weights.price)},
              performanță {pct(result.weights.performance)} (CPU {pct(result.performance_mix.cpu)} / GPU {pct(result.performance_mix.gpu)}),
              consum {pct(result.weights.power)}
            </span>
          )}
        </div>
        {loading && <p className="text-sm text-slate-400">Se calculează clasamentul…</p>}
        {error && <p className="text-sm text-red-300">{error}</p>}
        {!loading && result && !result.builds.length && (
          <p className="text-sm text-amber-300">Nicio configurație compatibilă care respectă cerințele acestui scop nu încape în buget. Mărește bugetul.</p>
        )}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {result?.builds.map((build) => (
            <RankedBuildCard key={build.rank} build={build}
              onLoad={() => {
                const selection: Selection = Object.fromEntries(Object.entries(build.components).filter(([, id]) => id !== null))
                replace(selection)
                toast({ title: 'Configurație încărcată', message: 'Poți edita piesele în configuratorul manual.', tone: 'ok' })
                navigate('/manual')
              }} />
          ))}
        </div>
      </div>
    </section>
  )
}
