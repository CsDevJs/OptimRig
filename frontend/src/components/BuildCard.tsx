import { CircleCheck, Cpu, Gpu, LoaderCircle, TriangleAlert } from 'lucide-react'

import type { TemplateStats } from '../builder/useTemplates'
import { useCurrency } from '../context/CurrencyContext'
import { componentName, TIER_LABEL } from '../lib/catalog'

const TIER_CLASS = {
  low: 'bg-white/10 text-white border-white/30',
  mid: 'bg-sky-400/15 text-sky-300 border-sky-400/30',
  high: 'bg-violet-400/15 text-violet-300 border-violet-400/30',
} as const

export function BuildCard({ stats, overBudget, onLoad, action = 'Încarcă în Manual' }: {
  stats: TemplateStats
  overBudget?: boolean
  onLoad: () => void
  action?: string
}) {
  const { format } = useCurrency()
  const { template, total, compatibility, cpu, gpu, missingStock } = stats
  const status = compatibility?.status
  return (
    <article className="modern-sleek-card glow rounded-2xl p-4 flex flex-col justify-between gap-3">
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold border ${TIER_CLASS[template.tier]}`}>{TIER_LABEL[template.tier]}</span>
          <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-slate-900 border border-slate-700 text-violet-300">{template.usage}</span>
        </div>
        <h3 className="text-sm font-extrabold text-white">{template.title}</h3>
        <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[9px] text-slate-400 block">Preț azi (cel mai mic)</span>
            <span className="text-lg font-extrabold font-mono text-white">{format(total)}</span>
          </div>
          {overBudget && <span className="text-[10px] font-bold text-amber-300">peste buget</span>}
        </div>
        <div className="text-[11px] text-slate-300 space-y-1">
          <div className="flex items-center gap-1.5 truncate"><Cpu size={12} className="text-violet-300 shrink-0" /> {componentName(cpu)}</div>
          <div className="flex items-center gap-1.5 truncate"><Gpu size={12} className="text-pink-300 shrink-0" /> {componentName(gpu)}</div>
        </div>
        <div className="text-[11px] flex items-center gap-1.5">
          {!compatibility && <><LoaderCircle size={12} className="animate-spin text-slate-400" /><span className="text-slate-400">Se verifică compatibilitatea…</span></>}
          {status === 'compatible' && <><CircleCheck size={12} className="text-emerald-300" /><span className="text-emerald-300">Compatibil (verificat live)</span></>}
          {status === 'undetermined' && <><TriangleAlert size={12} className="text-sky-300" /><span className="text-sky-300">Compatibil; montajul radiatorului de verificat</span></>}
          {(status === 'incompatible' || status === 'incomplete') && <><TriangleAlert size={12} className="text-red-300" /><span className="text-red-300">Necesită ajustări</span></>}
        </div>
        {missingStock > 0 && <p className="text-[10px] text-amber-300">{missingStock} {missingStock === 1 ? 'piesă nu e' : 'piese nu sunt'} în stoc acum.</p>}
      </div>
      <button type="button" onClick={onLoad}
        className="w-full py-2 px-3 rounded-xl bg-violet-400/20 hover:bg-violet-400/30 border border-violet-400/40 text-violet-200 font-bold text-xs transition hover:scale-[1.02]">
        {action}
      </button>
    </article>
  )
}
