import { Bot, WandSparkles } from 'lucide-react'
import { useCallback, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../api/client'
import type { AiAnswer } from '../api/types'
import { useBuilder } from '../builder/BuilderContext'
import { useTemplates } from '../builder/useTemplates'
import { AiModal } from '../components/AiModal'
import { BuildCard } from '../components/BuildCard'
import { useCurrency } from '../context/CurrencyContext'
import { useToast } from '../context/ToastContext'

type Brand = 'any' | 'AMD' | 'Intel'
const PRESETS = [
  { label: 'Buget', value: 30000, cls: 'bg-emerald-400/10 hover:bg-emerald-400/20 border-emerald-400/30 text-emerald-300' },
  { label: 'Mediu', value: 55000, cls: 'bg-sky-400/10 hover:bg-sky-400/20 border-sky-400/30 text-sky-300' },
  { label: 'High-End', value: 90000, cls: 'bg-violet-400/10 hover:bg-violet-400/20 border-violet-400/30 text-violet-300' },
  { label: 'Ultra', value: 120000, cls: 'bg-pink-400/10 hover:bg-pink-400/20 border-pink-400/30 text-pink-300' },
]

export function SmartPage() {
  const templates = useTemplates()
  const { replace } = useBuilder()
  const { code, format } = useCurrency()
  const toast = useToast()
  const navigate = useNavigate()
  const [budget, setBudget] = useState(55000)
  const [brand, setBrand] = useState<Brand>('any')
  const [aiAsk, setAiAsk] = useState<(() => Promise<AiAnswer>) | null>(null)

  // Until TOPSIS ranking exists: the most capable templates that fit the budget and CPU brand.
  const picks = useMemo(() => {
    if (!templates) return null
    const byBrand = templates.filter((t) => brand === 'any' || t.cpu.brand === brand)
    const fitting = byBrand.filter((t) => t.total <= budget).sort((a, b) => b.total - a.total)
    if (fitting.length) return { builds: fitting.slice(0, 3), over: false }
    return { builds: [...byBrand].sort((a, b) => a.total - b.total).slice(0, 3), over: true }
  }, [templates, budget, brand])

  const askAi = useCallback(() => setAiAsk(() => () => api.ai.budgetAdvice(budget, brand)), [budget, brand])

  return (
    <section className="space-y-8">
      <div className="slate-glow-card glow rounded-3xl p-6 sm:p-8 relative overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-2">
            <span className="px-3 py-1 rounded-full bg-violet-400/15 border border-violet-300/30 text-violet-200 text-xs font-semibold flex items-center gap-1.5 w-fit">
              <WandSparkles size={13} className="text-emerald-300" /> Recomandare inteligentă
            </span>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">Configurator inteligent PC</h1>
            <p className="text-slate-300 text-sm sm:text-base">
              Alege bugetul (afișat în <span className="text-violet-300 font-semibold">{code}</span>) și primește configurații compatibile, cu prețuri de azi.
            </p>
          </div>
          <button type="button" onClick={askAi}
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-400/30 to-violet-500/30 hover:from-emerald-400/40 hover:to-violet-500/40 border border-emerald-400/50 text-emerald-200 text-xs font-bold transition flex items-center gap-2 shrink-0">
            <Bot size={15} /> Întreabă Gemini AI
          </button>
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

          <div className="space-y-4 modern-sleek-card rounded-2xl p-6 flex flex-col justify-between">
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
            <p className="text-[11px] text-slate-400">
              Recomandările vin din șabloanele verificate. Clasamentul inteligent (TOPSIS) le va înlocui când e gata.
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-extrabold text-white">Variante recomandate</h2>
          {picks?.over && <span className="text-xs font-semibold text-amber-300">Nicio configurație nu încape în buget; iată cele mai accesibile.</span>}
        </div>
        {!picks && <p className="text-sm text-slate-400">Se calculează prețurile…</p>}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {picks?.builds.map((stats) => (
            <BuildCard key={stats.template.id} stats={stats} overBudget={stats.total > budget} action="Personalizează în Manual"
              onLoad={() => {
                replace(stats.selection)
                toast({ title: 'Configurație încărcată', message: 'Poți edita piesele în configuratorul manual.', tone: 'ok' })
                navigate('/manual')
              }} />
          ))}
        </div>
      </div>

      {aiAsk && (
        <AiModal title="Gemini AI: sfatul expertului pentru bugetul tău"
          loadingText={`Gemini AI analizează catalogul pentru un buget de ${format(budget)}...`}
          ask={aiAsk} onClose={() => setAiAsk(null)} />
      )}
    </section>
  )
}
