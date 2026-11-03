import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import type { Tier } from '../api/types'
import { useBuilder } from '../builder/BuilderContext'
import { useTemplates } from '../builder/useTemplates'
import { BuildCard } from '../components/BuildCard'
import { useToast } from '../context/ToastContext'
import { TIER_LABEL } from '../lib/catalog'

const FILTERS: { value: Tier | 'all'; label: string; cls: string }[] = [
  { value: 'all', label: 'Toate', cls: 'text-white border-violet-400/40' },
  { value: 'low', label: TIER_LABEL.low, cls: 'text-white border-white/30' },
  { value: 'mid', label: TIER_LABEL.mid, cls: 'text-sky-300 border-sky-400/30' },
  { value: 'high', label: TIER_LABEL.high, cls: 'text-violet-300 border-violet-400/30' },
]

export function TemplatesPage() {
  const templates = useTemplates()
  const { replace } = useBuilder()
  const toast = useToast()
  const navigate = useNavigate()
  const [tier, setTier] = useState<Tier | 'all'>('all')
  const shown = templates?.filter((t) => tier === 'all' || t.template.tier === tier)

  return (
    <section className="space-y-4">
      <div className="slate-glow-card glow rounded-2xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-extrabold text-white">Șabloane</h2>
          <p className="text-xs text-slate-300">Configurații din catalogul nostru, cu prețuri de azi din magazine și compatibilitate verificată.</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {FILTERS.map((f) => (
            <button key={f.value} type="button" onClick={() => setTier(f.value)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition hover:scale-105 ${f.cls} ${tier === f.value ? 'bg-violet-400/25 ring-2 ring-violet-400/40' : 'bg-slate-900'}`}>
              {f.label}
            </button>
          ))}
        </div>
      </div>
      {!shown && <p className="text-sm text-slate-400">Se încarcă șabloanele…</p>}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {shown?.map((stats) => (
          <BuildCard key={stats.template.id} stats={stats} onLoad={() => {
            replace(stats.selection)
            toast({ title: 'Încărcat', message: `Șablonul „${stats.template.title}” a fost încărcat.`, tone: 'ok' })
            navigate('/manual')
          }} />
        ))}
      </div>
    </section>
  )
}
