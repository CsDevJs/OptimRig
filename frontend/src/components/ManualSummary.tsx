import { CircleAlert, CircleCheck, CloudUpload, ExternalLink, Info, LoaderCircle, Stethoscope, Store, TriangleAlert } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import type { Category, CompatibilityResult, Component, PurchasePlan, Selection } from '../api/types'
import { useCurrency } from '../context/CurrencyContext'
import { CATEGORY_INFO, cheapestOffer, componentName, ORDER } from '../lib/catalog'

const STATUS = {
  compatible: { label: 'Compatibil', cls: 'bg-emerald-400/20 text-emerald-300' },
  incompatible: { label: 'Incompatibil', cls: 'bg-red-500/20 text-red-300' },
  incomplete: { label: 'Incomplet', cls: 'bg-sky-400/20 text-sky-300' },
  undetermined: { label: 'De verificat', cls: 'bg-violet-400/20 text-violet-300' },
} as const

interface Props {
  selection: Selection
  byId: Map<number, Component>
  compatibility: CompatibilityResult | null
  plan: PurchasePlan | null
  psuWatts: number | null
  checking: boolean
  buildName: string | null
  loggedIn: boolean
  onSave: (name: string, asNew: boolean) => Promise<void>
}

export function ManualSummary({ selection, byId, compatibility, plan, psuWatts, checking, buildName, loggedIn, onSave }: Props) {
  const { format } = useCurrency()
  const [name, setName] = useState(buildName ?? '')
  const [saving, setSaving] = useState(false)
  const count = Object.keys(selection).length
  const status = compatibility ? STATUS[compatibility.status] : null
  const errors = compatibility?.issues.filter((i) => i.severity === 'error') ?? []
  const warnings = compatibility?.issues.filter((i) => i.severity === 'warning') ?? []
  const power = compatibility?.estimated_power_w ?? 0
  const recommended = compatibility?.recommended_psu_w ?? 0
  const blocked = compatibility?.status === 'incompatible'

  const save = async (event: FormEvent, asNew: boolean) => {
    event.preventDefault()
    setSaving(true)
    try {
      await onSave(name.trim() || 'Build personalizat', asNew)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="slate-glow-card rounded-2xl p-4 space-y-3">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
        <h3 className="text-sm font-extrabold text-white">Sumar configurație</h3>
        {count > 0 && (checking || !status
          ? <LoaderCircle size={14} className="animate-spin text-violet-300" />
          : <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold ${status.cls}`}>{status.label}</span>)}
      </div>

      <div className="bg-slate-950/70 rounded-xl p-3 border border-slate-800 space-y-1">
        <span className="text-[10px] text-slate-400 block">Preț total (cel mai mic, în stoc)</span>
        <div className="text-2xl font-extrabold font-mono text-white">{plan ? format(plan.total_mdl) : format(0)}</div>
        {plan && plan.unplanned.length > 0 && (
          <p className="text-[10px] text-amber-300">
            Nu e în stoc nicăieri: {plan.unplanned.map((u) => CATEGORY_INFO[u.category].short).join(', ')} (nu intră în total).
          </p>
        )}
      </div>

      <div className="space-y-1.5 text-xs">
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-slate-400">Consum estimat:</span>
          <span className="font-mono font-bold text-slate-200">{power} W{psuWatts ? ` / ${psuWatts} W` : ''}</span>
        </div>
        <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden border border-slate-800">
          <div className={`h-full transition-all duration-500 bg-gradient-to-r ${psuWatts && psuWatts < recommended ? 'from-amber-400 to-red-400' : 'from-emerald-400 to-violet-400'}`}
            style={{ width: `${psuWatts ? Math.min(100, Math.round((power / psuWatts) * 100)) : 0}%` }} />
        </div>
        {count > 0 && <p className="text-[10px] text-slate-500">Sursă recomandată: minim {recommended} W (consum de vârf + 20% sau recomandarea producătorului GPU).</p>}
      </div>

      <div className="space-y-2.5 pt-2 border-t border-slate-800">
        <div className="text-[11px] font-bold text-violet-300 uppercase tracking-wider flex items-center gap-1.5">
          <Stethoscope size={13} /> Recomandări & diagnostic
        </div>
        {count === 0 && <p className="text-[11px] text-slate-400">Alege un procesor pentru a începe. Fiecare piesă e verificată cu cele deja alese.</p>}
        {errors.length > 0 && (
          <div className="p-3 rounded-xl bg-red-950/60 border border-red-500/80 text-red-200 space-y-1.5">
            <div className="flex items-center gap-2 font-bold text-xs text-red-300"><TriangleAlert size={14} /> Erori de compatibilitate</div>
            {errors.map((i) => <div key={i.code + i.component_ids} className="text-[11px] font-medium flex gap-1.5"><CircleAlert size={12} className="shrink-0 mt-0.5" />{i.message}</div>)}
          </div>
        )}
        {compatibility && compatibility.missing_categories.length > 0 && (
          <div className="p-2.5 rounded-xl bg-sky-950/40 border border-sky-500/40 text-sky-200 text-[11px] flex gap-2">
            <Info size={13} className="shrink-0 mt-0.5" />
            Lipsesc: {compatibility.missing_categories.map((c: Category) => CATEGORY_INFO[c].short).join(', ')}
          </div>
        )}
        {warnings.map((i) => (
          <div key={i.code + i.component_ids} className="p-2.5 rounded-xl bg-amber-950/30 border border-amber-500/40 text-amber-200 text-[11px] flex gap-2">
            <TriangleAlert size={13} className="shrink-0 mt-0.5" />{i.message}
          </div>
        ))}
        {compatibility?.status === 'compatible' && (
          <div className="p-2.5 rounded-xl bg-emerald-950/40 border border-emerald-500/40 text-emerald-300 text-[11px] flex items-center gap-2">
            <CircleCheck size={13} /> Toate componentele sunt compatibile!
          </div>
        )}
      </div>

      {count > 0 && (
        <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1 text-[11px] border-t border-slate-800 pt-2">
          {ORDER.filter((c) => selection[c]).map((c) => {
            const part = byId.get(selection[c]!)
            const offer = part ? cheapestOffer(part) : null
            return (
              <div key={c} className="flex justify-between gap-2 border-b border-slate-800/40 py-1">
                <span className="text-slate-300 truncate">{part ? componentName(part) : '…'}</span>
                <span className="font-mono text-violet-300 font-bold shrink-0">{offer ? format(offer.price_mdl) : '—'}</span>
              </div>
            )
          })}
        </div>
      )}

      {plan && plan.stores.length > 0 && (
        <div className="space-y-1.5 pt-2 border-t border-slate-800">
          <div className="text-[11px] font-bold text-sky-300 uppercase tracking-wider flex items-center gap-1.5">
            <Store size={13} /> Unde cumperi (Min-Cost Max-Flow)
          </div>
          {plan.stores.map((s) => (
            <details key={s.store.id} className="rounded-xl bg-slate-950/60 border border-slate-800 group">
              <summary className="px-3 py-2 flex items-center justify-between gap-2 cursor-pointer list-none text-xs">
                <span className="font-bold text-white">{s.store.name}</span>
                <span className="text-[10px] text-slate-400">{s.part_count} {s.part_count === 1 ? 'piesă' : 'piese'}</span>
                <span className="font-mono font-bold text-violet-300">{format(s.subtotal_mdl)}</span>
              </summary>
              <ul className="px-3 pb-2 space-y-1">
                {plan.items.filter((i) => i.store.id === s.store.id).map((i) => (
                  <li key={i.category} className="flex justify-between gap-2 text-[11px]">
                    <a href={i.url} target="_blank" rel="noreferrer" className="text-slate-300 hover:text-white truncate inline-flex items-center gap-1">
                      {i.component_name} <ExternalLink size={10} className="shrink-0" />
                    </a>
                    <span className="font-mono text-slate-200 shrink-0">{format(i.price_mdl)}</span>
                  </li>
                ))}
              </ul>
            </details>
          ))}
        </div>
      )}

      <form className="space-y-2 pt-2 border-t border-slate-800" onSubmit={(e) => save(e, false)}>
        <input value={name} onChange={(e) => setName(e.target.value)} maxLength={100} placeholder="Numele build-ului..."
          className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-violet-400" />
        <button type="submit" disabled={saving || blocked || count === 0}
          title={blocked ? 'Rezolvă erorile de compatibilitate înainte de salvare' : undefined}
          className="w-full py-2 px-3 rounded-xl bg-gradient-to-r from-violet-400 to-sky-400 text-slate-950 font-bold text-xs shadow-md transition hover:scale-[1.03] flex items-center justify-center gap-1.5 disabled:from-slate-800 disabled:to-slate-800 disabled:text-slate-500 disabled:hover:scale-100">
          <CloudUpload size={14} /> {buildName ? 'Salvează modificările' : loggedIn ? 'Salvează în cont' : 'Autentifică-te pentru a salva'}
        </button>
        {buildName && (
          <button type="button" disabled={saving || blocked} onClick={(e) => save(e, true)}
            className="w-full py-1.5 px-3 rounded-xl border border-violet-400/40 text-violet-200 text-xs font-bold hover:bg-violet-400/10 transition disabled:opacity-50">
            Salvează ca build nou
          </button>
        )}
      </form>
    </div>
  )
}
