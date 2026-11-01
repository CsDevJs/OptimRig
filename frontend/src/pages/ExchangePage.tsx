import { ArrowUpRight, Calculator, ChevronDown, Earth, Globe, Search, Star, Zap } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'

import { Flag } from '../components/Flag'
import { useCurrency } from '../context/CurrencyContext'
import { useToast } from '../context/ToastContext'
import { CURRENCIES, CURRENCY_CODES, groupThousands, POPULAR, RATES_NOTE, REGIONS, type Region } from '../lib/currencies'

type Preset = 'POPULAR' | 'CONVENIENT' | 'EXPENSIVE' | 'ALL'
const PRESETS: { id: Preset; label: string; icon: ReactNode }[] = [
  { id: 'POPULAR', label: 'Valute populare', icon: <Star size={11} className="text-amber-300" /> },
  { id: 'CONVENIENT', label: 'Peste 10 lei', icon: <Zap size={11} className="text-emerald-300" /> },
  { id: 'EXPENSIVE', label: 'Peste 20 lei', icon: <ArrowUpRight size={11} className="text-pink-300" /> },
  { id: 'ALL', label: 'Toate (A–Z)', icon: <Globe size={11} className="text-violet-200" /> },
]

function useOutside(open: boolean, close: () => void) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const handler = (event: MouseEvent) => !ref.current?.contains(event.target as Node) && close()
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open, close])
  return ref
}

export function ExchangePage() {
  const { code: active, setCode } = useCurrency()
  const toast = useToast()
  const [amount, setAmount] = useState(25000)
  const [from, setFrom] = useState('MDL')
  const [fromOpen, setFromOpen] = useState(false)
  const [fromQuery, setFromQuery] = useState('')
  const [region, setRegion] = useState<Region | 'ALL'>('ALL')
  const [regionOpen, setRegionOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [preset, setPreset] = useState<Preset>('ALL')
  const fromRef = useOutside(fromOpen, () => setFromOpen(false))
  const regionRef = useOutside(regionOpen, () => setRegionOpen(false))

  const amountMdl = amount * (CURRENCIES[from]?.mdl ?? 1)
  const q = search.toLowerCase()
  const results = CURRENCY_CODES.filter((c) => {
    const info = CURRENCIES[c]
    if (region !== 'ALL' && info.region !== region) return false
    if (q && !c.toLowerCase().includes(q) && !info.label.toLowerCase().includes(q)) return false
    if (preset === 'POPULAR') return POPULAR.includes(c)
    if (preset === 'CONVENIENT') return info.mdl > 10
    if (preset === 'EXPENSIVE') return info.mdl > 20
    return true
  })
  const fq = fromQuery.toLowerCase()

  return (
    <section className="space-y-4">
      <div className="slate-glow-card glow rounded-2xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-extrabold text-white">Exchange</h2>
          <p className="text-xs text-slate-300">Convertor rapid. Apasă pe o monedă ca să vezi toate prețurile site-ului în ea.</p>
        </div>
        <span className="text-[11px] font-mono px-2.5 py-1 rounded-lg bg-violet-400/15 text-violet-200 border border-violet-400/30">
          Activ: {active} ({CURRENCIES[active].symbol})
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-5 slate-glow-card glow rounded-2xl p-4 space-y-3 relative z-20">
          <h3 className="text-sm font-bold text-white flex items-center gap-2"><Calculator size={15} className="text-violet-300" /> Calculator valutar</h3>
          <label className="block">
            <span className="text-[11px] text-slate-400 block mb-1">Sumă</span>
            <input type="number" min={0} value={amount} onChange={(e) => setAmount(Number(e.target.value) || 0)}
              className="liquid-glass-input w-full px-3.5 py-2.5 rounded-xl text-white font-mono font-bold text-sm" />
          </label>
          <div ref={fromRef} className="relative">
            <span className="text-[11px] text-slate-400 block mb-1">Monedă sursă</span>
            <button type="button" onClick={() => setFromOpen((v) => !v)} aria-expanded={fromOpen}
              className="manual-custom-dropdown-btn w-full px-3.5 py-2.5 rounded-xl flex items-center justify-between text-left">
              <span className="flex items-center gap-2.5 min-w-0">
                <Flag code={from} /><span className="font-mono font-bold text-xs text-violet-300">{from}</span>
                <span className="text-xs text-white truncate">— {CURRENCIES[from].label} ({CURRENCIES[from].symbol})</span>
              </span>
              <ChevronDown size={12} className={`text-violet-300 shrink-0 transition-transform ${fromOpen ? 'rotate-180' : ''}`} />
            </button>
            {fromOpen && (
              <div className="liquid-glass-dropdown rounded-2xl p-2.5 space-y-2">
                <label className="relative block">
                  <Search size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input autoFocus value={fromQuery} onChange={(e) => setFromQuery(e.target.value)} placeholder="Caută monedă..."
                    className="liquid-glass-input w-full pl-8 pr-2.5 py-1.5 rounded-xl text-xs text-white placeholder-slate-400" />
                </label>
                <div className="max-h-56 overflow-y-auto space-y-1 pr-1">
                  {CURRENCY_CODES.filter((c) => !fq || c.toLowerCase().includes(fq) || CURRENCIES[c].label.toLowerCase().includes(fq)).map((c) => (
                    <button key={c} type="button" onClick={() => { setFrom(c); setFromOpen(false) }}
                      className={`w-full px-3 py-2 rounded-xl flex items-center justify-between text-left transition ${c === from ? 'bg-violet-400/30 text-white border border-violet-300/60' : 'hover:bg-white/10 text-slate-200'}`}>
                      <span className="flex items-center gap-2 min-w-0">
                        <Flag code={c} /><span className="font-mono font-bold text-xs text-violet-300">{c}</span><span className="text-xs truncate">{CURRENCIES[c].label}</span>
                      </span>
                      <span className="text-[11px] font-mono text-slate-400 ml-2 shrink-0">{CURRENCIES[c].symbol}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="flex gap-2 items-center">
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Caută valută..."
              className="liquid-glass-input flex-1 min-w-0 px-3.5 py-2 rounded-xl text-xs text-white placeholder-slate-400" />
            <div ref={regionRef} className="relative shrink-0 w-[150px]">
              <button type="button" onClick={() => setRegionOpen((v) => !v)} aria-expanded={regionOpen}
                className="manual-custom-dropdown-btn w-full px-3 py-2 rounded-xl flex items-center justify-between text-left text-xs">
                <span className="font-semibold text-slate-200 truncate">{region === 'ALL' ? 'Toate' : region}</span>
                <ChevronDown size={12} className={`text-violet-300 shrink-0 ml-1.5 transition-transform ${regionOpen ? 'rotate-180' : ''}`} />
              </button>
              {regionOpen && (
                <div className="liquid-glass-dropdown rounded-2xl p-2 space-y-1 !left-auto right-0 w-[220px]">
                  {(['ALL', ...REGIONS] as const).map((r) => (
                    <button key={r} type="button" onClick={() => { setRegion(r); setRegionOpen(false) }}
                      className={`w-full px-3 py-2 rounded-xl flex items-center justify-between text-left text-xs transition ${region === r ? 'bg-violet-400/30 text-white border border-violet-300/60' : 'hover:bg-white/10 text-slate-200'}`}>
                      <span>{r === 'ALL' ? 'Toate regiunile' : r}</span>
                      {r === 'ALL' && <Earth size={12} className="text-violet-300" />}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="pt-2 border-t border-slate-800 space-y-2">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider font-bold block">Filtre prestabilite</span>
            <div className="grid grid-cols-2 gap-2">
              {PRESETS.map((p) => (
                <button key={p.id} type="button" onClick={() => setPreset(p.id)}
                  className={`liquid-filter-btn px-3 py-2 rounded-xl text-[11px] text-left flex items-center gap-2 ${preset === p.id ? 'active' : 'text-slate-200 font-medium'}`}>
                  {p.icon} {p.label}
                </button>
              ))}
            </div>
          </div>
          <p className="text-[10px] text-slate-500">{RATES_NOTE}</p>
        </div>

        <div className="lg:col-span-7 slate-glow-card rounded-2xl p-4 space-y-3 overflow-hidden">
          <h3 className="text-sm font-bold text-white">
            {groupThousands(amount)} {CURRENCIES[from].symbol} în {results.length} {results.length === 1 ? 'monedă' : 'monede'}
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 max-h-[420px] overflow-y-auto p-1.5">
            {results.map((c) => (
              <button key={c} type="button"
                onClick={() => { setCode(c); toast({ title: 'Monedă schimbată', message: `Prețurile se afișează acum în ${c}.`, tone: 'ok' }) }}
                className={`currency-card-compact p-2.5 rounded-xl text-left flex flex-col gap-1 ${c === active ? 'currency-card-active' : ''}`}>
                <span className="flex items-center justify-between gap-1">
                  <span className="flex items-center gap-1.5"><Flag code={c} /><span className="font-mono font-bold text-xs text-violet-300">{c}</span></span>
                  <span className="text-[9px] text-slate-400 truncate max-w-[90px]">{CURRENCIES[c].label}</span>
                </span>
                <span className="font-mono text-xs font-bold text-white truncate">
                  {groupThousands(amountMdl / CURRENCIES[c].mdl)} {CURRENCIES[c].symbol}
                </span>
              </button>
            ))}
            {results.length === 0 && <p className="col-span-full text-xs text-slate-400 py-6 text-center">Nicio monedă pentru aceste filtre.</p>}
          </div>
        </div>
      </div>
    </section>
  )
}
