import { Check, ChevronDown, X } from 'lucide-react'
import { useEffect, useRef } from 'react'

import type { Category, Component, SpecValue } from '../api/types'
import { CATEGORY_INFO, cheapestOffer, ORDER } from '../lib/catalog'
import { PartLabel } from './PartLabel'
import { PriceTag } from './PriceTag'

interface Props {
  category: Category
  options: Component[]
  /** IDs that AC-3 says still fit; null = not filtered (auto-compat off or still loading). */
  allowed: Set<number> | null
  loadingAllowed: boolean
  selected: Component | null
  specs: Map<number, Record<string, SpecValue> | null>
  severity: 'error' | 'warning' | null
  open: boolean
  onToggle: () => void
  onClose: () => void
  onPick: (id: number) => void
  onClear: () => void
}

export function CategoryRow(props: Props) {
  const { category, options, allowed, loadingAllowed, selected, specs, severity, open, onToggle, onClose, onPick, onClear } = props
  const { title, short, icon: Icon, accent } = CATEGORY_INFO[category]
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => !box.current?.contains(event.target as Node) && onClose()
    const esc = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', esc)
    }
  }, [open, onClose])

  const shown = allowed ? options.filter((o) => allowed.has(o.id)) : options
  const hidden = options.length - shown.length
  const border = severity === 'error' ? 'border-red-500/70' : severity === 'warning' ? 'border-amber-400/50' : ''

  return (
    <div ref={box}
      className={`slate-glow-card glow rounded-xl p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 ${open ? 'category-row-active' : 'z-10'} ${border}`}>
      <div className="flex items-center gap-2 shrink-0">
        <div className="w-7 h-7 rounded-lg bg-slate-900 border border-slate-700 flex items-center justify-center">
          <Icon size={14} className={accent} />
        </div>
        <span className="text-xs font-bold text-white">{ORDER.indexOf(category) + 1}. {title}</span>
      </div>

      <div className="relative w-full sm:w-[400px] lg:w-[470px] min-w-0">
        <button type="button" onClick={onToggle} aria-expanded={open}
          className="manual-custom-dropdown-btn w-full px-3.5 py-2 rounded-xl flex items-center justify-between gap-3 text-left">
          {selected ? (
            <>
              <PartLabel category={category} component={selected} specs={specs.get(selected.id) ?? (specs.has(selected.id) ? null : undefined)} />
              {/* On phones the crossed-out price would squeeze the name; the % badge still shows the sale. */}
              <span className="shrink-0 max-sm:[&_s]:hidden"><PriceTag offer={cheapestOffer(selected)} /></span>
            </>
          ) : (
            <span className="text-xs text-slate-400 py-1.5">Alege {short}…</span>
          )}
          <ChevronDown size={13} className={`text-violet-300 shrink-0 transition-transform duration-300 ${open ? 'rotate-180' : ''}`} />
        </button>

        {open && (
          <div className="liquid-glass-dropdown rounded-2xl p-2.5 space-y-1.5" role="listbox" aria-label={title}>
            <button type="button" onClick={onClear}
              className="w-full px-3.5 py-2 rounded-xl flex items-center gap-2 text-left text-xs text-slate-300 hover:bg-white/10 transition">
              <X size={13} className="text-slate-400" /> Fără {short}
            </button>
            {loadingAllowed && <p className="px-3 py-2 text-[11px] text-slate-400">Se verifică compatibilitatea cu piesele alese…</p>}
            {!loadingAllowed && shown.length === 0 && (
              <p className="px-3 py-2 text-[11px] text-amber-300">Nicio piesă din această categorie nu se potrivește cu restul configurației.</p>
            )}
            {!loadingAllowed && shown.map((c) => {
              const isSelected = selected?.id === c.id
              const stores = c.offers.filter((o) => o.availability === 'in_stock').length
              return (
                <button key={c.id} type="button" role="option" aria-selected={isSelected} onClick={() => onPick(c.id)}
                  className={`w-full px-3.5 py-2.5 rounded-xl flex items-center justify-between gap-3 text-left transition ${isSelected ? 'bg-violet-400/30 border border-violet-300/60 shadow-md' : 'hover:bg-white/10 border border-transparent'}`}>
                  <PartLabel category={category} component={c} specs={specs.has(c.id) ? specs.get(c.id) : undefined} />
                  <span className="flex flex-col items-end shrink-0 gap-0.5">
                    <PriceTag offer={cheapestOffer(c)} />
                    <span className="text-[10px] text-slate-400">{stores ? `${stores} ${stores === 1 ? 'magazin' : 'magazine'} în stoc` : 'nu e în stoc'}</span>
                  </span>
                  {isSelected && <Check size={15} className="text-emerald-300 shrink-0" />}
                </button>
              )
            })}
            {!loadingAllowed && hidden > 0 && (
              <p className="px-3 pt-1 text-[10px] text-slate-400">
                {hidden} {hidden === 1 ? 'piesă incompatibilă ascunsă' : 'piese incompatibile ascunse'} de verificarea AC-3. Dezactivează „Compatibilitate Auto” ca să le vezi.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
